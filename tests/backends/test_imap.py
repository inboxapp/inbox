""" Tests IMAP backend functionality """
import pytest

from tests.util.base import config
config()

from inbox.models.backends.imap import ImapAccount
from inbox.models.backends.yahoo import YahooAccount
from inbox.models.backends.gmail import GmailAccount



def test_backend_provider(config, db):
    """Tests whether the PROVIDER variable is set correctly for IMAP backends"""
    assert ImapAccount().provider == 'imap'
    assert GmailAccount().provider == 'gmail'
    assert YahooAccount().provider == 'yahoo'

def test_gmail_access_token(config, db):
    gmail_account = db.session.query(GmailAccount).one()
    access_token = gmail_account.access_token

    #Assert we actually got an access_token back
    assert access_token is not None

    #Assert token value stays the same after consecutive calls to property
    assert access_token == gmail_account.access_token
