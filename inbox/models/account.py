from datetime import datetime

from sqlalchemy import (Column, Integer, String, DateTime, Boolean, ForeignKey,
                        Enum)
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import true, false

from inbox.sqlalchemy_ext.util import JSON, MutableDict
from inbox.util.file import Lock

from inbox.models.mixins import HasPublicID, HasEmailAddress
from inbox.models.base import MailSyncBase
from inbox.models.folder import Folder
from inbox.models.calendar import Calendar
from inbox.providers import provider_info


class Account(MailSyncBase, HasPublicID, HasEmailAddress):
    @property
    def provider(self):
        """ A constant, unique lowercase identifier for the account provider
        (e.g., 'gmail', 'eas'). Subclasses should override this.

        We prefix provider folders with this string when we expose them as
        tags through the API. E.g., a 'jobs' folder/label on a Gmail
        backend is exposed as 'gmail-jobs'. Any value returned here
        should also be in Tag.RESERVED_PROVIDER_NAMES.

        """
        raise NotImplementedError

    @property
    def auth_handler(self):
        from inbox.auth.base import handler_from_provider
        return handler_from_provider(self.provider)

    @property
    def provider_info(self):
        return provider_info(self.provider, self.email_address)

    def verify(self):
        """ Verify that the account is still valid."""
        raise NotImplementedError

    @property
    def thread_cls(self):
        from inbox.models.thread import Thread
        return Thread

    # The default phrase used when sending mail from this account.
    name = Column(String(256), nullable=False, server_default='')

    # If True, throttle initial sync to reduce resource load
    throttled = Column(Boolean, server_default=false())

    # local flags & data
    save_raw_messages = Column(Boolean, server_default=true())

    # if True we sync contacts/events
    # NOTE: these columns are meaningless for EAS accounts
    sync_contacts = Column(Boolean, nullable=False, default=False)
    sync_events = Column(Boolean, nullable=False, default=False)

    last_synced_contacts = Column(DateTime, nullable=True)
    last_synced_events = Column(DateTime, nullable=True)

    # Folder mappings for the data we sync back to the account backend.  All
    # account backends will not provide all of these. This may mean that Inbox
    # creates some folders on the remote backend, for example to provide
    # "archive" functionality on non-Gmail remotes.
    inbox_folder_id = Column(Integer,
                             ForeignKey(Folder.id, ondelete='SET NULL'),
                             nullable=True)
    inbox_folder = relationship('Folder', post_update=True,
                                foreign_keys=[inbox_folder_id])
    sent_folder_id = Column(Integer,
                            ForeignKey(Folder.id, ondelete='SET NULL'),
                            nullable=True)
    sent_folder = relationship('Folder', post_update=True,
                               foreign_keys=[sent_folder_id])

    drafts_folder_id = Column(Integer,
                              ForeignKey(Folder.id, ondelete='SET NULL'),
                              nullable=True)
    drafts_folder = relationship('Folder', post_update=True,
                                 foreign_keys=[drafts_folder_id])

    spam_folder_id = Column(Integer,
                            ForeignKey(Folder.id, ondelete='SET NULL'),
                            nullable=True)
    spam_folder = relationship('Folder', post_update=True,
                               foreign_keys=[spam_folder_id])

    trash_folder_id = Column(Integer,
                             ForeignKey(Folder.id, ondelete='SET NULL'),
                             nullable=True)
    trash_folder = relationship('Folder', post_update=True,
                                foreign_keys=[trash_folder_id])

    archive_folder_id = Column(Integer,
                               ForeignKey(Folder.id, ondelete='SET NULL'),
                               nullable=True)
    archive_folder = relationship('Folder', post_update=True,
                                  foreign_keys=[archive_folder_id])

    all_folder_id = Column(Integer,
                           ForeignKey(Folder.id, ondelete='SET NULL'),
                           nullable=True)
    all_folder = relationship('Folder', post_update=True,
                              foreign_keys=[all_folder_id])

    starred_folder_id = Column(Integer,
                               ForeignKey(Folder.id, ondelete='SET NULL'),
                               nullable=True)
    starred_folder = relationship('Folder', post_update=True,
                                  foreign_keys=[starred_folder_id])

    important_folder_id = Column(Integer,
                                 ForeignKey(Folder.id, ondelete='SET NULL'),
                                 nullable=True)
    important_folder = relationship('Folder', post_update=True,
                                    foreign_keys=[important_folder_id])

    emailed_events_calendar_id = Column(Integer,
                                        ForeignKey('calendar.id',
                                                   ondelete='SET NULL',
                                                   use_alter=True,
                                                   name='emailed_events_cal'),
                                        nullable=True)

    _emailed_events_calendar = relationship(
        'Calendar', post_update=True,
        foreign_keys=[emailed_events_calendar_id])

    def create_emailed_events_calendar(self):
        if not self._emailed_events_calendar:
            calname = "Emailed events"
            cal = Calendar(namespace=self.namespace,
                           description=calname,
                           uid='inbox',
                           name=calname,
                           read_only=True)
            self._emailed_events_calendar = cal

    @property
    def emailed_events_calendar(self):
        self.create_emailed_events_calendar()
        return self._emailed_events_calendar

    @emailed_events_calendar.setter
    def emailed_events_calendar(self, cal):
        self._emailed_events_calendar = cal

    sync_host = Column(String(255), nullable=True)

    # current state of this account
    state = Column(Enum('live', 'down', 'invalid', name='account_state'), nullable=True)

    @property
    def sync_enabled(self):
        return self.sync_should_run

    sync_state = Column(Enum('running', 'stopped', 'killed',
                             'invalid', 'connerror', name='sync_state'),
                        nullable=True)

    # Based on account status, should the sync be running?
    # This is set to false if:
    #  - Account credentials are invalid (see mark_invalid())
    #  - External factors no longer require this account to sync
    # The value of this bit should always equal the AND value of all its
    # folders and heartbeats.
    sync_should_run = Column(Boolean, server_default=true())

    _sync_status = Column(MutableDict.as_mutable(JSON), default={},
                          nullable=True)

    @property
    def sync_status(self):
        d = dict(id=self.id,
                 email=self.email_address,
                 provider=self.provider,
                 is_enabled=self.sync_enabled,
                 state=self.sync_state,
                 sync_host=self.sync_host)
        d.update(self._sync_status or {})

        return d

    @property
    def sync_error(self):
        return self._sync_status.get('sync_error')

    def update_sync_error(self, error=None):
        self._sync_status['sync_error'] = error

    def sync_started(self):
        """ Record transition to started state. Should be called after the
            sync is actually started, not when the request to start it is made.
        """
        current_time = datetime.utcnow()

        # Never run before (vs restarting stopped/killed)
        if self.sync_state is None and (
                not self._sync_status or
                self._sync_status.get('sync_end_time') is None):
            self._sync_status['original_start_time'] = current_time

        self._sync_status['sync_start_time'] = current_time
        self._sync_status['sync_end_time'] = None
        self._sync_status['sync_error'] = None

        self.sync_state = 'running'

    def enable_sync(self, sync_host=None):
        """ Tell the monitor that this account should be syncing. """
        self.sync_should_run = True
        if sync_host is not None:
            self.sync_host = sync_host

    def disable_sync(self, reason=None):
        """ Tell the monitor that this account should stop syncing. """
        self.sync_should_run = False
        if reason:
            self._sync_status['sync_disabled_reason'] = reason

    def mark_invalid(self, reason='invalid credentials'):
        """ In the event that the credentials for this account are invalid,
            update the status and sync flag accordingly. Should only be called
            after trying to re-authorize / get new token.
        """
        self.disable_sync(reason)
        self.sync_state = 'invalid'

    def sync_stopped(self, reason=None):
        """ Record transition to stopped state. Should be called after the
            sync is actually stopped, not when the request to stop it is made.
        """
        if self.sync_state == 'running':
            self.sync_state = 'stopped'
        self.sync_host = None
        self._sync_status['sync_end_time'] = datetime.utcnow()

    def kill_sync(self, error=None):
        # Don't disable sync: syncs are not killed on purpose.
        self.sync_state = 'killed'
        self._sync_status['sync_end_time'] = datetime.utcnow()
        self._sync_status['sync_error'] = error

    @classmethod
    def _get_lock_object(cls, account_id, lock_for=dict()):
        """ Make sure we only create one lock per account per process.

        (Default args are initialized at import time, so `lock_for` acts as a
        module-level memory cache.)
        """
        return lock_for.setdefault(account_id,
                                   Lock(cls._sync_lockfile_name(account_id),
                                        block=False))

    @classmethod
    def _sync_lockfile_name(cls, account_id):
        return "/var/lock/inbox_sync/{}.lock".format(account_id)

    @property
    def _sync_lock(self):
        return self._get_lock_object(self.id)

    def sync_lock(self):
        """ Prevent mailsync for this account from running more than once. """
        self._sync_lock.acquire()

    def sync_unlock(self):
        self._sync_lock.release()

    @property
    def is_killed(self):
        return self.sync_state == 'killed'

    @property
    def is_running(self):
        return self.sync_state == 'running'

    @property
    def is_sync_locked(self):
        return self._sync_lock.locked()

    def __init__(self, *args, **kwargs):
        MailSyncBase.__init__(self, *args, **kwargs)

        # Note: SQLAlchemy calls an object's constructor only when
        # it's created, not on subsequent db reads
        # (http://docs.sqlalchemy.org/en/rel_0_9/orm/constructors.html)
        # so it's safe to call a method that creates a calendar here.
        self.create_emailed_events_calendar()

    discriminator = Column('type', String(16))
    __mapper_args__ = {'polymorphic_identity': 'account',
                       'polymorphic_on': discriminator}
