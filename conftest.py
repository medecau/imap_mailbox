import os

import pytest
from imapclient import IMAPClient

from . import mailbox

IMAP_HOST = "imap.gmail.com"
IMAP_USER = os.environ.get("IMAP_USER")
IMAP_PASS = os.environ.get("IMAP_PASSWORD")


@pytest.fixture(scope="session")
def imap_client():
    client = IMAPClient(IMAP_HOST, use_uid=True, timeout=5)
    client.normalise_times = False
    client.login(IMAP_USER, IMAP_PASS)
    yield client
    client.logout()


@pytest.fixture(scope="session")
def client(imap_client):
    yield mailbox.Client(imap_client)
