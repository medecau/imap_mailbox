import imaplib
import mailbox
import os
import re
import time
import email.header

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
            else:
                decoded_chunks.append(data.decode(charset))

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

    def connect(self):
        """Connect to the IMAP server"""
        self.__m = imaplib.IMAP4_SSL(self.host)
        self.__m.login(self.user, self.password)

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

    def fetch(self, uids, what):
        messages = handle_response(self.__m.fetch(uids, what))

        for head, body in messages:
            uid, what, size = MESSAGE_HEAD_RE.match(head.decode()).groups()
            if size != str(len(body)):
                raise Exception("Size mismatch")

    def add(self, message, folder) -> str:
        """Add a message to the mailbox"""

        self.__m.append(
            folder,
            "",
            imaplib.Time2Internaldate(time.time()),
            message.as_bytes(),
        )

    def discard(self, key: str) -> None:
        """Remove a message from the mailbox"""

        self.__m.store(key, "+FLAGS", "\\Deleted")
        self.__m.expunge()

    def search(self, query) -> list:
        """Search for messages matching the query"""

        data = handle_response(self.__m.search(None, query))

        return data[0].decode().split()

    def find(self, text) -> list:
        """Find messages that contain the specified string in the message body or subject

        Returns:
            list: A list of message UIDs
        """

        data = handle_response(self.__m.search(None, "TEXT", text))

        return data[0].decode().split()

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

    def get_folder(self, folder):
        self.__m.select(folder)
        return self
