from abc import ABCMeta, abstractmethod
from imapclient import IMAPClient
from inbox.basicauth import ConnectionError, TransientConnectionError
from inbox.providers import providers
from inbox.basicauth import NotSupportedError
from inbox.log import get_logger
log = get_logger()


def handler_from_provider(provider_name):
    """Return an authentication handler for the given provider.

    Parameters
    ----------
    provider_name : str
        Name of the email provider (e.g. inbox/providers.py) OR of the provider
        module's PROVIDER constant

        (XXX: interface terribleness!)

    Returns
    -------
    An object that implements the AuthHandler interface.
    """
    from inbox.auth import module_registry
    auth_mod = module_registry.get(provider_name)

    if auth_mod is None:
        # Try to get a generic provider
        info = providers.get(provider_name, None)
        if info:
            provider_type = info.get('type', None)
            if provider_type:
                auth_mod = module_registry.get('generic')

    if auth_mod is None:
        raise NotSupportedError('Inbox does not support the email provider.')

    auth_handler_class = getattr(auth_mod, auth_mod.AUTH_HANDLER_CLS)
    auth_handler = auth_handler_class(provider_name=provider_name)
    return auth_handler


class AuthHandler(object):
    __metaclass__ = ABCMeta

    def __init__(self, provider_name):
        self.provider_name = provider_name

    def connect_to_imap(self, imap_endpoint):
        host, port, is_secure = imap_endpoint
        try:
            conn = IMAPClient(host, port=port, use_uid=True, ssl=(port == 993))
            if is_secure and port != 993:
                # Raises an exception if TLS can't be established
                conn._imap.starttls()
        except IMAPClient.AbortError as e:
            log.error('account_connect_failed',
                      account_id=account_id,
                      email=email,
                      host=host,
                      port=port,
                      error="[ALERT] Can't connect to host - may be transient")
            raise TransientConnectionError(str(e))
        except(IMAPClient.Error, gaierror, socket_error) as e:
            log.error('account_connect_failed',
                      account_id=account_id,
                      email=email,
                      host=host,
                      port=port,
                      error='[ALERT] (Failure): {0}'.format(str(e)))
            raise ConnectionError(str(e))

        conn.debug = False
        return conn

    # optional
    def connect_account(self, email, secret, imap_endpoint):
        """Return an authenticated IMAPClient instance for the given
        credentials.

        This is an optional interface, which is only needed for accounts that
        are synced using IMAP.
        """
        raise NotImplementedError

    @abstractmethod
    def create_account(self, db_session, email_address, response):
        raise NotImplementedError

    @abstractmethod
    def verify_account(self, account):
        raise NotImplementedError

    @abstractmethod
    def interactive_auth(self, email_address=None):
        raise NotImplementedError
