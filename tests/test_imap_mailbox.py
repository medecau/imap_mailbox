"""Integration tests for IMAPMailbox using pymap test server."""

from imap_mailbox import IMAPMessage


def test_smoke():
    """Basic smoke test."""
    import imap_mailbox

    assert hasattr(imap_mailbox, "IMAPMailbox")


class TestIMAPMailboxConnection:
    """Tests for basic connection lifecycle."""

    def test_connect_and_disconnect(self, imap_connection):
        """Test basic connect and disconnect operations."""
        imap_connection.connect()
        assert imap_connection._IMAPMailbox__m is not None
        imap_connection.disconnect()

    def test_context_manager(self, imap_connection):
        """Test using IMAPMailbox as a context manager."""
        with imap_connection as mb:
            assert mb._IMAPMailbox__m is not None
            # Should be connected and able to get keys
            keys = mb.keys()
            assert isinstance(keys, list)


class TestIMAPMailboxIteration:
    """Tests for iterating over messages in the mailbox."""

    def test_iter_messages(self, imap_connection):
        """Test that iterating returns IMAPMessage instances."""
        with imap_connection as mb:
            messages = list(mb)
            # Demo data should have some messages
            assert len(messages) > 0
            # All should be IMAPMessage instances
            for msg in messages:
                assert isinstance(msg, IMAPMessage)
                assert msg.uid is not None

    def test_keys_returns_uids(self, imap_connection):
        """Test that keys() returns UID strings."""
        with imap_connection as mb:
            keys = mb.keys()
            assert isinstance(keys, list)
            assert len(keys) > 0
            # All should be strings
            for key in keys:
                assert isinstance(key, str)
                # UIDs should be numeric strings
                assert key.isdigit()

    def test_len_returns_message_count(self, imap_connection):
        """Test that __len__ returns the correct message count."""
        with imap_connection as mb:
            length = len(mb)
            keys = mb.keys()
            assert length == len(keys)
            assert length > 0  # Demo data should have messages

    def test_items_returns_uid_message_pairs(self, imap_connection):
        """Test that items() returns (uid, IMAPMessage) tuples."""
        with imap_connection as mb:
            items = list(mb.items())
            assert len(items) > 0
            for uid, msg in items:
                assert isinstance(uid, str)
                assert isinstance(msg, IMAPMessage)
                assert msg.uid == uid


class TestIMAPMessageLazyLoading:
    """Tests for lazy loading of message bodies."""

    def test_message_headers_available_immediately(self, imap_connection):
        """Test that headers are available without fetching the body."""
        with imap_connection as mb:
            msg = next(iter(mb))
            # Headers should be available
            subject = msg["Subject"]
            assert subject is not None
            # Body should not be loaded yet
            assert not msg._body_loaded

    def test_message_body_lazy_loaded(self, imap_connection):
        """Test that get_payload() triggers body loading."""
        with imap_connection as mb:
            msg = next(iter(mb))
            assert not msg._body_loaded
            # Accessing payload should trigger body load
            payload = msg.get_payload()
            assert msg._body_loaded
            assert payload is not None

    def test_message_walk_triggers_body_load(self, imap_connection):
        """Test that walk() triggers body loading."""
        with imap_connection as mb:
            msg = next(iter(mb))
            assert not msg._body_loaded
            # Walking the message should trigger body load
            parts = list(msg.walk())
            assert msg._body_loaded
            assert len(parts) > 0

    def test_message_as_string_triggers_body_load(self, imap_connection):
        """Test that as_string() triggers body loading."""
        with imap_connection as mb:
            msg = next(iter(mb))
            assert not msg._body_loaded
            # Converting to string should trigger body load
            msg_str = msg.as_string()
            assert msg._body_loaded
            assert len(msg_str) > 0


class TestIMAPMailboxFolders:
    """Tests for folder operations."""

    def test_list_folders(self, imap_connection):
        """Test listing folders."""
        with imap_connection as mb:
            folders = list(mb.list_folders())
            assert len(folders) > 0
            # Each folder should be a tuple: (flags, delimiter, folder, display_name)
            for folder in folders:
                assert len(folder) == 4
                flags, delimiter, folder_name, display_name = folder
                assert isinstance(flags, str)
                assert isinstance(delimiter, str)
                assert isinstance(folder_name, str)
                assert isinstance(display_name, str)

    def test_select_folder(self, imap_connection):
        """Test selecting a different folder."""
        with imap_connection as mb:
            # Get list of folders
            folders = list(mb.list_folders())
            folder_names = [f[2] for f in folders]

            # Select the first non-INBOX folder if available
            for folder_name in folder_names:
                if folder_name != "INBOX":
                    mb.select(folder_name)
                    assert mb.current_folder == folder_name
                    # Should be able to get keys from the new folder
                    keys = mb.keys()
                    assert isinstance(keys, list)
                    break
