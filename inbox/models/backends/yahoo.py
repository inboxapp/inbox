from sqlalchemy import Column, Integer, String, ForeignKey

from inbox.models.backends.imap import ImapAccount


class YahooAccount(ImapAccount):
    PROVIDER = 'yahoo'

    id = Column(Integer, ForeignKey(ImapAccount.id, ondelete='CASCADE'),
                primary_key=True)

    password = Column(String(256))

    __mapper_args__ = {'polymorphic_identity': 'yahooaccount'}
