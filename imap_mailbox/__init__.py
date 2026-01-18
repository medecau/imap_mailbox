"""
.. include:: README.md
"""

import datetime
import email
import email.header
import imaplib
import logging
import mailbox
import os
import re
import time

__all__ = ["IMAPMailbox", "IMAPMessage"]

MESSAGE_HEAD_RE = re.compile(r"(\d+) \(([^\s]+) {(\d+)}$")
FOLDER_DATA_RE = re.compile(r"\(([^)]+)\) \"([^\"]+)\" \"?([^\"]+)\"?$")


log = logging.getLogger(__name__)
log.setLevel(getattr(logging, os.getenv("LOG_LEVEL", "INFO")))


def handle_response(response):
    """Handle the response from the IMAP server"""
    status, data = response
    if status != "OK":
        raise Exception(data[0])

    return data


def change_time(time, weeks=0, days=0, hours=0, minutes=0, seconds=0):
    """Change the time by a given amount of days, hours, minutes and seconds"""
    return time + datetime.timedelta(
        weeks=weeks, days=days, hours=hours, minutes=minutes, seconds=seconds
    )


def imap_date(time):
    """Convert a datetime object to an IMAP date string"""
    return time.strftime("%d-%b-%Y")


def imap_date_range(start, end):
    """Create an IMAP date range string for use in a search query"""
    return f"(SINCE {imap_date(start)} BEFORE {imap_date(end)})"


class IMAPMessage(mailbox.Message):
    """A Mailbox Message class that uses an IMAPClient object to fetch the message

    Supports lazy loading: messages can be created with headers only, and the full
    body is fetched transparently when accessed.
    """

    def __init__(self, message=None, uid=None, mailbox_ref=None):
        """Create a new IMAPMessage

        Args:
            message: Email message bytes or Message object
            uid: Message UID for lazy loading (optional)
            mailbox_ref: Reference to IMAPMailbox for lazy loading (optional)
        """
        super().__init__(message)
        self._uid = uid
        self._mailbox_ref = mailbox_ref
        self._body_loaded = mailbox_ref is None  # If no mailbox ref, body is already loaded

    @classmethod
    def from_uid(cls, uid, mailbox, headers_only=False):
        """Create a new message from a UID

        Args:
            uid: Message UID
            mailbox: IMAPMailbox instance
            headers_only: If True, fetch only headers for lazy loading
        """
        if headers_only:
            # Fetch headers only, store reference for lazy body loading
            _, body = next(mailbox.fetch(uid, "RFC822.HEADER"))
            msg = cls(body, uid=uid, mailbox_ref=mailbox)
            return msg
        else:
            # Fetch full message immediately
            _, body = next(mailbox.fetch(uid, "RFC822"))
            return cls(body, uid=uid)

    @property
    def uid(self):
        """Get the message UID"""
        return self._uid

    def _ensure_body_loaded(self):
        """Ensure the full message body is loaded

        If the message was created with headers_only=True, this will fetch
        the full message from the IMAP server.

        Raises:
            RuntimeError: If the IMAP connection is closed
        """
        if self._body_loaded:
            return

        if self._mailbox_ref is None:
            raise RuntimeError("Cannot load body: IMAP connection is closed")

        # Fetch the full message
        _, body = next(self._mailbox_ref.fetch(self._uid, "RFC822"))

        # Parse the full message
        full_msg = email.message_from_bytes(body)

        # Update our payload from the parsed message
        self._payload = full_msg._payload

        # Clear the mailbox reference to allow garbage collection
        self._mailbox_ref = None
        self._body_loaded = True

    def __getitem__(self, name: str):
        """Get a message header

        This method overrides the default implementation of accessing a message headers.
        The header is decoded using the email.header.decode_header method. This allows
        for the retrieval of headers that contain non-ASCII characters.
        """
        original_header = super().__getitem__(name)

        if original_header is None:
            return None

        decoded_pairs = email.header.decode_header(original_header)
        decoded_chunks = []
        for data, charset in decoded_pairs:
            if isinstance(data, str):
                decoded_chunks.append(data)
            elif charset is None:
                decoded_chunks.append(data.decode())
            elif charset == "unknown-8bit":
                decoded_chunks.append(data.decode("utf-8", "replace"))
            else:
                decoded_chunks.append(data.decode(charset, "replace"))

        return " ".join(decoded_chunks)

    # Override body-accessing methods to ensure body is loaded

    def get_payload(self, *args, **kwargs):
        """Get the message payload, ensuring body is loaded"""
        self._ensure_body_loaded()
        return super().get_payload(*args, **kwargs)

    def is_multipart(self):
        """Check if message is multipart, ensuring body is loaded"""
        self._ensure_body_loaded()
        return super().is_multipart()

    def walk(self):
        """Walk the message tree, ensuring body is loaded"""
        self._ensure_body_loaded()
        return super().walk()

    def as_string(self, *args, **kwargs):
        """Return message as string, ensuring body is loaded"""
        self._ensure_body_loaded()
        return super().as_string(*args, **kwargs)

    def as_bytes(self, *args, **kwargs):
        """Return message as bytes, ensuring body is loaded"""
        self._ensure_body_loaded()
        return super().as_bytes(*args, **kwargs)

    def set_payload(self, *args, **kwargs):
        """Set the message payload, ensuring body is loaded"""
        self._ensure_body_loaded()
        return super().set_payload(*args, **kwargs)

    def attach(self, *args, **kwargs):
        """Attach a payload, ensuring body is loaded"""
        self._ensure_body_loaded()
        return super().attach(*args, **kwargs)


class IMAPMailbox(mailbox.Mailbox):
    """A Mailbox class that uses an IMAPClient object as the backend"""

    def __init__(self, host, user, password, folder="INBOX", port=993, security="SSL"):
        """Create a new IMAPMailbox object"""
        self.host = host
        self.user = user
        self.password = password
        self.__folder = folder
        self.__security = security
        self.__port = port

    def connect(self):
        """Connect to the IMAP server"""
        if self.__security == "SSL":
            log.info("Connecting to IMAP server using SSL")
            self.__m = imaplib.IMAP4_SSL(self.host, self.__port)
        elif self.__security == "STARTTLS":
            log.info("Connecting to IMAP server using STARTTLS")
            self.__m = imaplib.IMAP4(self.host, self.__port)
            self.__m.starttls()
        elif self.__security == "PLAIN":
            log.info("Connecting to IMAP server without encryption (insecure)")
            self.__m = imaplib.IMAP4(self.host, self.__port)
        else:
            raise ValueError("Invalid security type")
        self.__m.login(self.user, self.password)
        self.select(self.__folder)

    def disconnect(self):
        """Disconnect from the IMAP server"""

        log.info("Disconnecting from IMAP server")
        self.__m.close()
        self.__m.logout()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()

    def __iter__(self):
        """Iterate over all messages in the mailbox"""
        data = handle_response(self.__m.search(None, "ALL"))
        for uid in data[0].decode().split():
            yield IMAPMessage.from_uid(uid, self, headers_only=True)

    def values(self):
        yield from iter(self)

    def keys(self) -> list[str]:
        """Get a list of all message UIDs in the mailbox"""
        data = handle_response(self.__m.search(None, "ALL"))
        return data[0].decode().split()

    def items(self):
        """Iterate over all messages as (uid, message) tuples"""
        data = handle_response(self.__m.search(None, "ALL"))
        for uid in data[0].decode().split():
            msg = IMAPMessage.from_uid(uid, self, headers_only=True)
            yield uid, msg

    @property
    def capability(self):
        """Get the server capabilities"""
        return handle_response(self.__m.capability())[0].decode()

    def add(self, message):
        """Add a message to the mailbox"""

        self.__m.append(
            self.current_folder,
            "",
            imaplib.Time2Internaldate(time.time()),
            message.as_bytes(),
        )

    def copy(self, messageset: bytes, folder: str) -> None:
        """Copy a message to a different folder"""

        self.__m.copy(messageset, folder)

    def move(self, messageset: bytes, folder: str) -> None:
        """Move a message to a different folder"""

        self.__m._simple_command("MOVE", messageset, folder)

    def discard(self, messageset: bytes) -> None:
        """Mark messages for deletion"""

        self.__m.store(messageset, "+FLAGS", "\\Deleted")

    def remove(self, messageset: bytes) -> None:
        """Remove messages from the mailbox"""

        self.discard(messageset)
        self.__m.expunge()

    def __delitem__(self, key: str) -> None:
        raise NotImplementedError("Use discard() instead")

    def __len__(self) -> int:
        return len(self.keys())

    def fetch(self, messageset: bytes, what):
        """Fetch messages from the mailbox"""

        messages = handle_response(self.__m.fetch(messageset, what))[::2]

        for head, body in messages:
            uid, what, size = MESSAGE_HEAD_RE.match(head.decode()).groups()
            if size != str(len(body)):
                raise Exception("Size mismatch")

            yield uid, body

    def __expand_search_macros(self, query) -> str:
        """Expand search macros in the query."""

        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)

        week_start = today - datetime.timedelta(days=today.weekday())
        last_week_start = week_start - datetime.timedelta(days=7)

        month_start = datetime.date(today.year, today.month, 1)
        year_start = datetime.date(today.year, 1, 1)

        if today.month == 1:  # January
            # last month is December of the previous year
            last_month_start = datetime.date(today.year - 1, 12, 1)
        else:
            last_month_start = datetime.date(today.year, today.month - 1, 1)

        last_year_start = datetime.date(today.year - 1, 1, 1)

        q = query
        q = q.replace("FIND", "TEXT")

        q = q.replace("TODAY", f"ON {imap_date(today)}")
        q = q.replace("YESTERDAY", f"ON {imap_date(yesterday)}")

        q = q.replace("THISWEEK", f"SINCE {imap_date(week_start)}")
        q = q.replace("THISMONTH", f"SINCE {imap_date(month_start)}")
        q = q.replace("THISYEAR", f"SINCE {imap_date(year_start)}")

        q = q.replace("LASTWEEK", imap_date_range(last_week_start, week_start))
        q = q.replace("LASTMONTH", imap_date_range(last_month_start, month_start))
        q = q.replace("LASTYEAR", imap_date_range(last_year_start, year_start))

        # shortcuts
        q = q.replace("PASTDAY", "PAST1DAY")
        q = q.replace("PASTWEEK", "PAST1WEEK")
        q = q.replace("PASTMONTH", "PAST1MONTH")
        q = q.replace("PASTYEAR", "PAST1YEAR")

        # use regex to match the PASTXDAYS macro
        q = re.sub(
            r"PAST(\d+)DAYS?",
            lambda m: f"SINCE {imap_date(change_time(today, days=-int(m.group(1))))}",
            q,
        )

        # use regex to match the PASTXWEEKS macro
        q = re.sub(
            r"PAST(\d+)WEEKS?",
            lambda m: f"SINCE {imap_date(change_time(today, weeks=-int(m.group(1))))}",
            q,
        )

        # use regex to match the PASTXMONTHS macro
        q = re.sub(
            r"PAST(\d+)MONTHS?",
            lambda m: f"SINCE {imap_date(change_time(today, days=-int(m.group(1)) * 30))}",
            q,
        )

        # use regex to match the PASTXYEARS macro
        q = re.sub(
            r"PAST(\d+)YEARS?",
            lambda m: f"SINCE {imap_date(change_time(today, days=-int(m.group(1)) * 365))}",
            q,
        )

        return q

    def search(self, query):
        """Search for messages matching the query

        We support extra search macros in the search query in addition to
        the standard IMAP search macros.

        One search macro is FIND <text>, which is an alias for TEXT.
        The rest of the macros deal with date ranges.

        The date range macros are expanded to the appropriate date range and
        are relative to the current date.
        Example: TODAY expands to ON <date>, where <date> is today's date.

        Note that some of these macros will expand to multiple search terms.
        Expansions that result in multiple search terms are wrapped in parentheses.
        Example: LASTWEEK expands to (SINCE <date1> BEFORE <date2>).

        The following extra macros are supported:


        - FIND <text> - alias for TEXT, searches the message headers and body

        Current period:
        - TODAY - messages from today
        - THISWEEK - messages since the start of the week, Monday to Sunday
        - THISMONTH - messages since the start of the month
        - THISYEAR - messages since the start of the year

        Previous period:
        - YESTERDAY - messages from yesterday
        - LASTWEEK - messages from the week before
        - LASTMONTH - messages from the month before
        - LASTYEAR - messages from the year before

        Periods starting from now:

        _These are just shortcuts_
        - PASTDAY - messages from the past 1 day, same as PAST1DAY
        - PASTWEEK - messages from the past 1 week, same as PAST1WEEK
        - PASTMONTH - messages from the past 30 days, same as PAST1MONTH
        - PASTYEAR - messages from the past 365 days, same as PAST1YEAR

        _These are pattern matching macros_
        - PASTXDAYS - messages from the past X days
        - PASTXWEEKS - messages from the past X weeks
        - PASTXMONTHS - messages from the past X * 30 days
        - PASTXYEARS - messages from the past X * 365 days

        These macros can be combined with other search macros, and can be
        negated with NOT. For example, to search and archive or delete messages with a short
        relevance period, you can use `NOT PAST3DAYS`, use `NOT PAST3MONTHS` to search for
        messages older than a quarter, or use `NOT PAST2YEAR` to search for messages older than
        two years.

        _The `NOT` modifier is very useful for mailbox maintenance_

        _There are no options for hours, because the range seletion does not have time of day precision._

        Returns:
            bytes: A comma-separated list of message UIDs
        """

        expanded_query = self.__expand_search_macros(query)
        data = handle_response(self.__m.search(None, expanded_query))
        num_results = len(data[0].split(b" "))

        log.info(f"Searching for messages matching: {query}")
        if expanded_query != query:
            log.info(f"Expanded search query to: {expanded_query}")
        log.info(f"Found {num_results} results")

        return data[0].replace(b" ", b",")

    def list_folders(self) -> tuple:
        """List all folders in the mailbox

        Returns:
            tuple: A tuple of flags, delimiter, folder name, and folder display name
        """

        folders_data = handle_response(self.__m.list())
        for data in folders_data:
            flags, delimiter, folder = FOLDER_DATA_RE.match(data.decode()).groups()
            display_name = folder.split(delimiter)[-1]
            yield (flags, delimiter, folder, display_name)

    @property
    def current_folder(self):
        """Get the currently selected folder"""
        return self.__folder

    def select(self, folder):
        """Select a folder"""
        self.__folder = folder
        self.__m.select(folder)
        return self
