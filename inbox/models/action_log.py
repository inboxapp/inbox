from inbox.config import get_db_info
from sqlalchemy import Column, Integer, Text, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship

from inbox.sqlalchemy_ext.util import JSON
from inbox.models.base import MailSyncBase
from inbox.models.namespace import Namespace

if get_db_info()['engine'] == 'mysql':
    TEXT_TYPE = Text(40)
else:
    TEXT_TYPE = Text

ADD_TAG_ACTIONS = {
    'inbox': 'unarchive',
    'archive': 'archive',
    'starred': 'star',
    'unread': 'mark_unread',
    'spam': 'mark_spam',
    'trash': 'mark_trash'
}

REMOVE_TAG_ACTIONS = {
    'inbox': 'archive',
    'archive': 'unarchive',
    'starred': 'unstar',
    'unread': 'mark_read',
    'spam': 'unmark_spam',
    'trash': 'unmark_trash'
}


class ActionError(Exception):
    def __init__(self, error, namespace_id):
        self.error = error
        self.namespace_id = namespace_id

    def __str__(self):
        return 'Error {0} for namespace_id {1}'.format(
            self.error, self.namespace_id)


def schedule_action_for_tag(tag_public_id, thread, db_session, tag_added):
    if tag_added:
        action = ADD_TAG_ACTIONS.get(tag_public_id)
    else:
        action = REMOVE_TAG_ACTIONS.get(tag_public_id)
    if action is not None:
        schedule_action(action, thread, thread.namespace_id, db_session)


def schedule_action(func_name, record, namespace_id, db_session, **kwargs):
    # Ensure that the record's id is non-null
    db_session.flush()

    # Ensure account is valid
    account = db_session.query(Namespace).get(namespace_id).account

    if account.sync_state == 'invalid':
        raise ActionError(error=403, namespace_id=namespace_id)

    log_entry = ActionLog(
        action=func_name,
        table_name=record.__tablename__,
        record_id=record.id,
        namespace_id=namespace_id,
        extra_args=kwargs)
    db_session.add(log_entry)


class ActionLog(MailSyncBase):
    namespace_id = Column(ForeignKey(Namespace.id, ondelete='CASCADE'),
                          nullable=False,
                          index=True)
    namespace = relationship('Namespace')

    action = Column(TEXT_TYPE, nullable=False)
    record_id = Column(Integer, nullable=False)
    table_name = Column(TEXT_TYPE, nullable=False)
    status = Column(Enum('pending', 'successful', 'failed', name='action_status'),
                    server_default='pending')
    retries = Column(Integer, server_default='0', nullable=False)

    extra_args = Column(JSON, nullable=True)

Index('ix_actionlog_status_retries', ActionLog.status, ActionLog.retries)
