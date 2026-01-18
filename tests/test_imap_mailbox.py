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
            assert messages
            # All should be IMAPMessage instances
            assert all(isinstance(msg, IMAPMessage) for msg in messages)
            assert all(msg.uid is not None for msg in messages)

    def test_keys_returns_uids(self, imap_connection):
        """Test that keys() returns UID strings."""
        with imap_connection as mb:
            keys = mb.keys()
            assert isinstance(keys, list)
            assert len(keys) > 0
            # All should be strings
            assert all(isinstance(key, str) for key in keys)
            # UIDs should be numeric strings
            assert all(key.isdigit() for key in keys)

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
            assert items
            assert all(isinstance(uid, str) for uid, msg in items)
            assert all(isinstance(msg, IMAPMessage) for uid, msg in items)
            assert all(msg.uid == uid for uid, msg in items)


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
            assert parts

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
            assert folders
            # Each folder should be a tuple: (flags, delimiter, folder, display_name)
            assert all(len(folder) == 4 for folder in folders)
            assert all(isinstance(folder[0], str) for folder in folders)  # flags
            assert all(isinstance(folder[1], str) for folder in folders)  # delimiter
            assert all(isinstance(folder[2], str) for folder in folders)  # folder_name
            assert all(isinstance(folder[3], str) for folder in folders)  # display_name

    def test_select_folder(self, imap_connection):
        """Test selecting a different folder."""
        with imap_connection as mb:
            # Get list of folders
            folders = list(mb.list_folders())
            folder_names = [f[2] for f in folders]

            # Select the first non-INBOX folder if available
            non_inbox = next((f for f in folder_names if f != "INBOX"), None)
            assert non_inbox is not None, "No non-INBOX folder available for testing"
            mb.select(non_inbox)
            assert mb.current_folder == non_inbox
            # Should be able to get keys from the new folder
            keys = mb.keys()
            assert isinstance(keys, list)


class TestMailboxInterface:
    """Tests for mailbox.Mailbox interface compliance."""

    def test_iterkeys_returns_iterator(self, imap_connection):
        """Test that iterkeys() returns an iterator."""
        with imap_connection as mb:
            result = mb.iterkeys()
            assert hasattr(result, "__iter__")
            assert hasattr(result, "__next__")

    def test_iterkeys_matches_keys(self, imap_connection):
        """Test that iterkeys() yields same values as keys()."""
        with imap_connection as mb:
            assert list(mb.iterkeys()) == mb.keys()

    def test_contains_existing_key(self, imap_connection):
        """Test that __contains__ returns True for existing keys."""
        with imap_connection as mb:
            key = mb.keys()[0]
            assert key in mb

    def test_contains_nonexistent_key(self, imap_connection):
        """Test that __contains__ returns False for nonexistent keys."""
        with imap_connection as mb:
            assert "99999999" not in mb

    def test_get_bytes_returns_bytes(self, imap_connection):
        """Test that get_bytes() returns bytes."""
        with imap_connection as mb:
            key = mb.keys()[0]
            result = mb.get_bytes(key)
            assert isinstance(result, bytes)
            assert len(result) > 0

    def test_get_bytes_nonexistent_raises(self, imap_connection):
        """Test that get_bytes() raises KeyError for nonexistent keys."""
        with imap_connection as mb:
            import pytest

            with pytest.raises(KeyError):
                mb.get_bytes("99999999")

    def test_get_file_returns_file_like(self, imap_connection):
        """Test that get_file() returns a file-like object."""
        with imap_connection as mb:
            key = mb.keys()[0]
            with mb.get_file(key) as f:
                content = f.read()
                assert isinstance(content, bytes)

    def test_get_file_matches_get_bytes(self, imap_connection):
        """Test that get_file() content matches get_bytes()."""
        with imap_connection as mb:
            key = mb.keys()[0]
            assert mb.get_file(key).read() == mb.get_bytes(key)

    def test_get_message_returns_imap_message(self, imap_connection):
        """Test that get_message() returns an IMAPMessage."""
        with imap_connection as mb:
            key = mb.keys()[0]
            msg = mb.get_message(key)
            assert isinstance(msg, IMAPMessage)
            assert msg.uid == key

    def test_get_message_nonexistent_raises(self, imap_connection):
        """Test that get_message() raises KeyError for nonexistent keys."""
        with imap_connection as mb:
            import pytest

            with pytest.raises(KeyError):
                mb.get_message("99999999")

    def test_getitem_returns_message(self, imap_connection):
        """Test that __getitem__ returns an IMAPMessage."""
        with imap_connection as mb:
            key = mb.keys()[0]
            msg = mb[key]
            assert isinstance(msg, IMAPMessage)

    def test_getitem_nonexistent_raises(self, imap_connection):
        """Test that __getitem__ raises KeyError for nonexistent keys."""
        with imap_connection as mb:
            import pytest

            with pytest.raises(KeyError):
                _ = mb["99999999"]

    def test_get_with_default(self, imap_connection):
        """Test that get() returns default for nonexistent keys."""
        with imap_connection as mb:
            result = mb.get("99999999", "default")
            assert result == "default"

    def test_get_string_returns_string(self, imap_connection):
        """Test that get_string() returns a string."""
        with imap_connection as mb:
            key = mb.keys()[0]
            result = mb.get_string(key)
            assert isinstance(result, str)

    def test_remove_deletes_message(self, imap_connection, sample_message):
        """Test that remove() deletes a message."""
        with imap_connection as mb:
            mb.add(sample_message)
            key = mb.keys()[-1]
            mb.remove(key)
            assert key not in mb

    def test_remove_nonexistent_raises(self, imap_connection):
        """Test that remove() raises KeyError for nonexistent keys."""
        with imap_connection as mb:
            import pytest

            with pytest.raises(KeyError):
                mb.remove("99999999")

    def test_discard_nonexistent_silent(self, imap_connection):
        """Test that discard() doesn't raise for nonexistent keys."""
        with imap_connection as mb:
            mb.discard("99999999")  # Should not raise

    def test_delitem_removes_message(self, imap_connection, sample_message):
        """Test that __delitem__ removes a message."""
        with imap_connection as mb:
            mb.add(sample_message)
            key = mb.keys()[-1]
            del mb[key]
            assert key not in mb

    def test_setitem_replaces_message(self, imap_connection, sample_message):
        """Test that __setitem__ replaces a message."""
        with imap_connection as mb:
            mb.add(sample_message)
            key = mb.keys()[-1]
            count_before = len(mb)

            import email.message

            new_msg = email.message.EmailMessage()
            new_msg["Subject"] = "Replaced"
            new_msg["From"] = "new@example.com"
            new_msg.set_content("New body")

            mb[key] = new_msg
            # Count should stay same (delete + add)
            assert len(mb) == count_before

    def test_setitem_nonexistent_raises(self, imap_connection, sample_message):
        """Test that __setitem__ raises KeyError for nonexistent keys."""
        with imap_connection as mb:
            import pytest

            with pytest.raises(KeyError):
                mb["99999999"] = sample_message

    def test_flush_succeeds(self, imap_connection):
        """Test that flush() succeeds without error."""
        with imap_connection as mb:
            mb.flush()  # Should not raise

    def test_lock_succeeds(self, imap_connection):
        """Test that lock() succeeds without error."""
        with imap_connection as mb:
            mb.lock()  # Should not raise

    def test_unlock_succeeds(self, imap_connection):
        """Test that unlock() succeeds without error."""
        with imap_connection as mb:
            mb.unlock()  # Should not raise

    def test_close_disconnects(self, imap_connection):
        """Test that close() disconnects from the server."""
        imap_connection.connect()
        imap_connection.close()
        # Connection should be closed

    def test_pop_returns_and_removes(self, imap_connection, sample_message):
        """Test that pop() returns message and removes it."""
        with imap_connection as mb:
            mb.add(sample_message)
            key = mb.keys()[-1]
            msg = mb.pop(key)
            assert isinstance(msg, IMAPMessage)
            assert key not in mb

    def test_pop_default(self, imap_connection):
        """Test that pop() returns default for nonexistent keys."""
        with imap_connection as mb:
            result = mb.pop("99999999", "default")
            assert result == "default"

    def test_popitem(self, imap_connection):
        """Test that popitem() returns and removes an item."""
        with imap_connection as mb:
            count_before = len(mb)
            key, msg = mb.popitem()
            assert len(mb) == count_before - 1

    def test_clear(self, imap_connection, sample_message):
        """Test that clear() removes all messages."""
        with imap_connection as mb:
            mb.add(sample_message)
            mb.add(sample_message)
            mb.clear()
            assert len(mb) == 0

    def test_itervalues(self, imap_connection):
        """Test that itervalues() returns IMAPMessage instances."""
        with imap_connection as mb:
            assert all(isinstance(msg, IMAPMessage) for msg in mb.itervalues())

    def test_iteritems(self, imap_connection):
        """Test that iteritems() returns (key, IMAPMessage) tuples."""
        with imap_connection as mb:
            assert all(isinstance(key, str) for key, msg in mb.iteritems())
            # Need to consume iteritems again since it's an iterator
            assert all(isinstance(msg, IMAPMessage) for key, msg in mb.iteritems())
