import hypothesis.strategies as hs
from hypothesis import given

from . import mailbox

ascii_characters = hs.characters(max_codepoint=128)


@given(ascii_characters)
def test_normbytes(chars):
    result = mailbox.normbytes(chars)

    assert isinstance(result, str)


@given(hs.dictionaries(ascii_characters, hs.text()))
def test_normalise_keys(obj):
    result = mailbox.normalise_keys(obj)

    all_keys_are_str_type = all(isinstance(k, str) for k in result.keys())

    assert all_keys_are_str_type
    assert isinstance(result, dict)


def test_client_login():
    client = mailbox.Client.login(IMAP_HOST, IMAP_USER, IMAP_PASS)
    resp = client.noop()

    assert resp[0] == b"Success"


def test_client_noop(client):
    resp = client.noop()

    assert resp[0] == b"Success"


def test_client_list_folders(client, data_regression):
    folders = tuple(client.list_folders())

    data_regression.check(folders)


def test_client_get_folders_for(client, data_regression):
    folders = client.get_folders_for("\\junk")

    data_regression.check(folders)
