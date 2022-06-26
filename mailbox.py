import functools
import os
import time
from collections import defaultdict, namedtuple
from contextlib import contextmanager
from typing import Mapping, Sequence

from imapclient import IMAPClient


def normbytes(val: bytes) -> str:
    return val.decode("ascii") if isinstance(val, bytes) else val


def normalise_keys(mapping):
    return {normbytes(k): normalise_keys(v) for k, v in mapping.items()}


def normalise_items(seq):
    return tuple(map(normbytes, seqj))


def normalise_response(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        res = func(*args, **kwargs)
        if isinstance(res, Mapping):
            return normalise_keys(res)
        elif isinstance(res, Sequence):
            return normalise_items(res)
        return res

    return wrapper


class Client:
    __pass_through_methods = {
        "fetch",
        "folder_exists",
        "folder_status",
        "move",
        "noop",
        "search",
        "select_folder",
        "unselect_folder",
    }

    def __init__(self, client):
        self.__clt = client
        self.__refresh_flag_lookup()

    @classmethod
    def login(cls, host, user, password):
        client = IMAPClient(host, use_uid=True, timeout=5)
        client.normalise_times = False
        client.login(user, password)
        return cls(client)

    def list_folders(self, folder="/"):
        """List folders as a sequence of (flags, name) tuples"""
        yield from (
            (normalise_keys(flags), name)
            for flags, _, name in self.__clt.list_folders(folder)
        )

    def get_folders_for(self, flag):
        """Return folder name for a given flag"""
        return self.__flag_lut[flag.lower()]

    def __refresh_flag_lookup(self):
        flag_lut = defaultdict(list)
        for _ in self.list_folders():
            flags, name = _
            for flag in flags:
                flag_lut[flag.lower()].append(name)
        self.__flag_lut = flag_lut

    def __getattr__(self, name):
        if name in self.__pass_through_methods:
            attr = getattr(self.__clt, name)
            if callable(attr):
                return normalise_response(attr)
            return getattr(self.__clt, name)
        raise AttributeError(name)


class Message:
    def __init__(self, client, uid):
        self.__clt = client
        self.__id = uid

    @property
    def id(self):
        return self.__id

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} "{self.__id}">'

    @functools.cached_property
    def envelope(self):
        resp = self.__clt.fetch([self.__id], ["ENVELOPE"])

        return resp[self.__id]["ENVELOPE"]


class Folder:
    def __init__(self, client, name):
        self.__clt = client
        self.__name = name

    @property
    def name(self):
        self.__name

    @contextmanager
    def selected(self):
        self.__clt.select_folder(self.__name)
        yield
        self.__clt.unselect_folder()

    def __iter__(self):
        yield from self.search("ALL")

    def __len__(self):
        st = self.__clt.folder_status(self.__name, ["MESSAGES"])
        return st["MESSAGES"]

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} "{self.__name}">'

    def search(self, criteria):
        yield from (
            Message(self.__clt, uid) for uid in self.__clt.search(criteria=criteria)
        )

    def move(self, message, folder):
        self.__clt.move(message.id, folder.name)


class MailBox:
    def __init__(self, client: Client):
        self.__clt = client

    def __getitem__(self, name):
        if self.__clt.folder_exists(name):
            return Folder(self.__clt, name)
        else:
            raise KeyError(name)

    def __iter__(self):
        yield from self.__clt.list_folders("/")

    @classmethod
    def connect(cls, host, user, password):
        clt = Client(host, user, password)
        return cls(clt)

    def folder_lookup(self, query):
        folders = self.__clt.get_folders_for(query)
        if folders:
            return folders

        folders = self.__clt.list_folders("/")
        return [name for _, name in folders if query in name]


# mailbox = MailBox.connect(
#     "imap.gmail.com",
#     os.environ.get("IMAP_USER"),
#     os.environ.get("IMAP_PASSWORD"),
# )

# print(mailbox["inbox"])
# print(len(mailbox["inbox"]))


# print(mailbox.folder_lookup("\\all"))
# print(mailbox.folder_lookup("\\drafts"))
# print(mailbox.folder_lookup("\\sent"))
# print(mailbox.folder_lookup("\\flagged"))
# print(mailbox.folder_lookup("\\trash"))
# print(mailbox.folder_lookup("\\junk"))


# time.sleep(1)
# inbox = mailbox["inbox"]
# spam = mailbox.folder_lookup("\\junk")[0]
# with inbox.selected():
#     messages = tuple(inbox.search(["FROM", "instagram.com"]))
#     for msg in messages:
#         print(msg.envelope.keys())
#         print(msg.envelope["SUBJECT"])
#         # inbox.move(msg, spam)
#         time.sleep(1)
#         break


# mailbox.inbox

# select_info = server.select_folder("INBOX")
# print("%d messages in INBOX" % select_info[b"EXISTS"])
# # 34 messages in INBOX

# messages = server.search(["FROM", "nike.com"])
# # print("%d messages from our best friend" % len(messages))
# # 5 messages from our best friend

# for msgid, data in server.fetch(messages, ["ENVELOPE"]).items():
#     envelope = data[b"ENVELOPE"]
#     print(
#         'ID #%d: "%s" received %s' % (msgid, envelope.subject.decode(), envelope.date)
#     )


# server.logout()
