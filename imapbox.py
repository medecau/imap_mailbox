import datetime
import email.header
import imaplib
import mailbox
import re
import time

__all__ = ["IMAPMailbox", "IMAPMessage"]

MESSAGE_HEAD_RE = re.compile(r"(\d+) \(([^\s]+) {(\d+)}$")
FOLDER_DATA_RE = re.compile(r"\(([^)]+)\) \"([^\"]+)\" \"([^\"]+)\"$")


def handle_response(response):
    """Handle the response from the IMAP server"""
    status, data = response
    if status != "OK":
        raise Exception(data[0])

    return data


def parse_folder_data(data):
    """Parse the folder data on a folder list call"""

    # use regex to parse the folder data
    flags, delimiter, folder_name = FOLDER_DATA_RE.match(data.decode()).groups()

    return flags, delimiter, folder_name


def imap_time_range(start, end):
    return "(SINCE {:%d-%b-%Y} BEFORE {:%d-%b-%Y})".format(start, end)


class IMAPMessage(mailbox.Message):
    """A Mailbox Message class that uses an IMAPClient object to fetch the message"""

    @classmethod
    def from_uid(cls, uid, mailbox):
        """Create a new message from a UID"""

        # fetch the message from the mailbox
        uid, body = next(mailbox.fetch(uid, "RFC822"))
        return cls(body)

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

        # decode_chunks = (pair[0] for pair in decoded_pairs)

        return " ".join(decoded_chunks)


class IMAPMessageHeadersOnly(IMAPMessage):
    """A Mailbox Message class that uses an IMAPClient object to fetch the message"""

    @classmethod
    def from_uid(cls, uid, mailbox):
        """Create a new message from a UID"""

        # fetch headers only message from the mailbox
        uid, body = next(mailbox.fetch(uid, "RFC822.HEADER"))
        return cls(body)


class IMAPMailbox(mailbox.Mailbox):
    """A Mailbox class that uses an IMAPClient object as the backend"""

    def __init__(self, host, user, password, folder="INBOX"):
        """Create a new IMAPMailbox object"""
        self.host = host
        self.user = user
        self.password = password
        self.__folder = folder

    def connect(self):
        """Connect to the IMAP server"""
        self.__m = imaplib.IMAP4_SSL(self.host)
        self.__m.login(self.user, self.password)
        self.select(self.__folder)

    def disconnect(self):
        """Disconnect from the IMAP server"""
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
            yield IMAPMessageHeadersOnly.from_uid(uid, self)

    def values(self):
        yield from self.__iter__()

    def keys(self) -> list[str]:
        """Get a list of all message UIDs in the mailbox"""
        data = handle_response(self.__m.search(None, "ALL"))
        return data[0].decode().split()

    def items(self):
        """Iterate over all messages in the mailbox"""
        uids = ",".join(self.keys()).encode()
        return self.fetch(uids, "RFC822")

    @property
    def capability(self):
        """Get the server capabilities"""
        return handle_response(self.__m.capability())[0].decode()

    def add(self, message, folder) -> str:
        """Add a message to the mailbox"""

        self.__m.append(
            folder,
            "",
            imaplib.Time2Internaldate(time.time()),
            message.as_bytes(),
        )

    def copy(self, messageset: bytes, folder: str) -> None:
        """Copy a message to a different folder"""

        self.__m.copy(messageset, folder)

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

        q = q.replace("TODAY", "ON {:%d-%b-%Y}".format(today))
        q = q.replace("YESTERDAY", "ON {:%d-%b-%Y}".format(yesterday))

        q = q.replace("THISWEEK", "SINCE {:%d-%b-%Y}".format(week_start))
        q = q.replace("THISMONTH", "SINCE {:%d-%b-%Y}".format(month_start))
        q = q.replace("THISYEAR", "SINCE {:%d-%b-%Y}".format(year_start))

        q = q.replace("LASTWEEK", imap_time_range(last_week_start, week_start))
        q = q.replace("LASTMONTH", imap_time_range(last_month_start, month_start))
        q = q.replace("LASTYEAR", imap_time_range(last_year_start, year_start))

        # 3 days
        three_days_ago = today - datetime.timedelta(days=3)
        q = q.replace("PAST3DAYS", "SINCE {:%d-%b-%Y}".format(three_days_ago))

        # 7 days
        seven_days_ago = today - datetime.timedelta(days=7)
        q = q.replace("PAST7DAYS", "SINCE {:%d-%b-%Y}".format(seven_days_ago))

        # 14 days
        fourteen_days_ago = today - datetime.timedelta(days=14)
        q = q.replace("PAST14DAYS", "SINCE {:%d-%b-%Y}".format(fourteen_days_ago))

        # 30 days
        thirty_days_ago = today - datetime.timedelta(days=30)
        q = q.replace("PAST30DAYS", "SINCE {:%d-%b-%Y}".format(thirty_days_ago))

        # 60 days
        sixty_days_ago = today - datetime.timedelta(days=60)
        q = q.replace("PAST60DAYS", "SINCE {:%d-%b-%Y}".format(sixty_days_ago))

        # 90 days
        ninety_days_ago = today - datetime.timedelta(days=90)
        q = q.replace("PAST90DAYS", "SINCE {:%d-%b-%Y}".format(ninety_days_ago))

        # 180 days
        half_year_ago = today - datetime.timedelta(days=180)
        q = q.replace("PASTHALFYEAR", "PAST180DAYS")
        q = q.replace("PAST180DAYS", "SINCE {:%d-%b-%Y}".format(half_year_ago))

        # 365 days
        a_year_ago = today - datetime.timedelta(days=365)
        q = q.replace("PASTYEAR", "PAST365DAYS")
        q = q.replace("PAST365DAYS", "SINCE {:%d-%b-%Y}".format(a_year_ago))

        # 730 days - 2 years
        two_years_ago = today - datetime.timedelta(days=730)
        q = q.replace("PAST2YEARS", "PAST730DAYS")
        q = q.replace("PAST730DAYS", "SINCE {:%d-%b-%Y}".format(two_years_ago))

        return q

    def search(self, query) -> list:
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

        FIND <text> - alias for TEXT, searches the message headers and body

        TODAY - messages from today
        YESTERDAY - messages from yesterday
        THISWEEK - messages since the start of the week, Monday to Sunday
        LASTWEEK - messages from the week before
        THISMONTH - messages since the start of the month
        LASTMONTH - messages from the month before
        THISYEAR - messages since the start of the year
        LASTYEAR - messages from the year before

        PAST7DAYS - messages from the past 7 days
        PAST14DAYS - messages from the past 14 days
        PAST30DAYS - messages from the past 30 days
        PAST60DAYS - messages from the past 60 days
        PAST90DAYS - messages from the past 90 days
        PAST180DAYS - messages from the past 180 days
        PAST365DAYS - messages from the past 365 days
        PASTYEAR - same as PAST365DAYS
        PAST730DAYS - messages from the past 730 days, or 2 years
        PAST2YEARS - same as PAST730DAYS

        These macros can be combined with other search macros, and can be
        negated with NOT. For example, to get messages that are older than
        7 days, use NOT PAST7DAYS.

        Returns:
            bytes: A comma-separated list of message UIDs
        """

        expanded_query = self.__expand_search_macros(query)
        if expanded_query != query:
            print(f"Query expanded to: {expanded_query}")
        data = handle_response(self.__m.search(None, expanded_query))

        return data[0].replace(b" ", b",")

    def list_folders(self) -> tuple:
        """List all folders in the mailbox

        Returns:
            tuple: A tuple of flags, delimiter, folder name, and folder display name
        """

        folders_data = handle_response(self.__m.list())
        for data in folders_data:
            flags, delimiter, folder = parse_folder_data(data)
            display_name = folder.split(delimiter)[-1]
            yield (flags, delimiter, folder, display_name)

        return

    @property
    def current_folder(self):
        """Get the currently selected folder"""
        return self.__folder

    def select(self, folder):
        """Select a folder"""
        self.__folder = folder
        self.__m.select(folder)
        return self
