"""pytest configuration and fixtures for IMAP testing with pymap."""

import socket
import subprocess
import time

import pytest

from imap_mailbox import IMAPMailbox


def find_free_port():
    """Find a free TCP port for the test server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def wait_for_port(host, port, timeout=10):
    """Wait for a port to become available."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, port))
                return True
        except OSError:
            time.sleep(0.1)
    return False


@pytest.fixture(scope="session")
def pymap_port():
    """Provide a free port for the pymap server."""
    return find_free_port()


@pytest.fixture(scope="session")
def pymap_server(pymap_port):
    """Start a pymap IMAP server with demo data for testing.

    The server runs with:
    - Demo credentials: demouser / demopass
    - Demo mailboxes: INBOX, Sent, Trash with sample messages
    - Insecure login allowed (PLAIN auth over unencrypted connection)
    """
    # Start pymap server
    proc = subprocess.Popen(
        [
            "pymap",
            "--host",
            "127.0.0.1",
            "--port",
            str(pymap_port),
            "--no-tls",
            "dict",
            "--demo-data",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to be ready
    if not wait_for_port("127.0.0.1", pymap_port, timeout=10):
        proc.terminate()
        proc.wait()
        raise RuntimeError("pymap server failed to start")

    yield {
        "host": "127.0.0.1",
        "port": pymap_port,
        "user": "demouser",
        "password": "demopass",
    }

    # Cleanup
    proc.terminate()
    proc.wait()


@pytest.fixture
def imap_connection(pymap_server):
    """Provide an IMAPMailbox instance configured for the test server.

    Returns an unconnected IMAPMailbox instance. Tests should use it as a
    context manager or call connect()/disconnect() manually.
    """
    return IMAPMailbox(
        host=pymap_server["host"],
        port=pymap_server["port"],
        user=pymap_server["user"],
        password=pymap_server["password"],
        security="PLAIN",
    )


@pytest.fixture
def sample_message():
    """Provide a sample email message for testing."""
    import email.message

    msg = email.message.EmailMessage()
    msg["Subject"] = "Test Message"
    msg["From"] = "test@example.com"
    msg["To"] = "recipient@example.com"
    msg.set_content("This is a test message body.")
    return msg
