*Please note that `imapbox` is still under active development and will be subject to significant changes.*

```python
import imapbox

# connect to the IMAP server
with imapbox.IMAPMailbox('imap.example.com', 'username', 'password') as mailbox:
    
    # search messages from vip@example.com
    uids = mailbox.search('FROM', 'vip@example.com')
    
    # move the messages to the 'VIP' folder
    mailbox.move(uids, 'VIP')
```

This module provides a subclass of `mailbox.Mailbox` that allows you to interact with an IMAP server. It is designed to be a drop-in replacement for the standard library `mailbox` module.

# Installation

Install the latest version from PyPI:

```bash
pip install imapbox
```

# Examples

## Iterate over messages in a folder

```python
import imapbox

# connect to the IMAP server
with imapbox.IMAPMailbox('imap.example.com', 'username', 'password') as mailbox:
    
    # select the INBOX folder
    mailbox.select('INBOX')
    
    # iterate over messages in the folder
    for message in mailbox:
        print(f"From: {message['From']}")
        print(f"Subject: {message['Subject']}")
```

## Delete messages from a noisy sender

```python
import imapbox

with imapbox.IMAPMailbox('imap.example.com', 'username', 'password') as mailbox:
    
    # search messages from
    uids = mailbox.search('FROM', 'spammer@example.com')

    # delete the messages
    mailbox.delete(uids)
```

## Delete GitHub messages older than two years

```python
import imapbox

with imapbox.IMAPMailbox('imap.example.com', 'username', 'password') as mailbox:
    
    # search messages older than two years from github.com
    uids = mailbox.search('NOT PAST2YEARS FROM github.com')
    
    # delete the messages
    mailbox.delete(uids)
```

# Contribution

Help improve imapbox by reporting any issues or suggestions on our issue tracker at [github.com/medecau/imapbox/issues](https://github.com/medecau/imapbox/issues).

Get involved with the development, check out the source code at [github.com/medecau/imapbox](https://github.com/medecau/imapbox).