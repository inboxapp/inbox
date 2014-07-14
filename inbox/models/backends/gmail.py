from sqlalchemy import Column, Integer, String, ForeignKey

from inbox.models.backends.imap import ImapAccount
from datetime import datetime, timedelta

from inbox.log import get_logger
log = get_logger()


class GmailAccount(ImapAccount):
    PROVIDER = 'gmail'

    id = Column(Integer, ForeignKey(ImapAccount.id, ondelete='CASCADE'),
                primary_key=True)

    __mapper_args__ = {'polymorphic_identity': 'gmailaccount'}

    refresh_token = Column(String(512))  # Secret
    scope = Column(String(512))
    access_type = Column(String(64))
    family_name = Column(String(256))
    given_name = Column(String(256))
    name = Column(String(256))
    gender = Column(String(16))
    g_id = Column(String(32))  # `id`
    g_id_token = Column(String(1024))  # `id_token`
    g_user_id = Column(String(32))  # `user_id`
    link = Column(String(256))
    locale = Column(String(8))
    picture = Column(String(1024))
    home_domain = Column(String(256))

    @property
    def access_token(self):
        ''' If token is expired or does not exist, then fetch new'''
        from inbox.oauth import new_token, validate_token

        if not hasattr(self, '_access_token') or not self._access_token or \
                datetime.utcnow() > self._token_expiry:
            new_tok, expires_in_seconds = new_token(self.refresh_token)
            new_expiry = datetime.utcnow() + timedelta(seconds=expires_in_seconds)

            if not validate_token(new_tok):
                return None

            self._access_token, self._token_expiry = new_tok, new_expiry
        return self._access_token

    @property
    def sender_name(self):
        return self.name or ''
