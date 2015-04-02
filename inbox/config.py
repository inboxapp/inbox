import errno
import os
import yaml
from urllib import quote_plus as urlquote


__all__ = ['config', 'engine_uri', 'db_uri']


class ConfigError(Exception):
    def __init__(self, error=None, help=None):
        self.error = error or ''
        self.help = help or \
            'Run `sudo cp etc/config-dev.json /etc/inboxapp/config.json` and '\
            'retry.'

    def __str__(self):
        return '{0} {1}'.format(self.error, self.help)


class Configuration(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)

    def get_required(self, key):
        if key not in self:
            raise ConfigError('Missing config value for {0}.'.format(key))

        return self[key]


def _update_config_from_env(config):
    """Update a config dictionary from configuration files specified in the
    environment.

    The environment variable `INBOX_CFG_PATH` contains a list of .json or .yml
    paths separated by colons.  The files are read in reverse order, so that
    the settings specified in the leftmost configuration files take precedence.
    (This is to emulate the behavior of the unix PATH variable, but the current
    implementation always reads all config files.)

    The following paths will always be appended:

    If `INBOX_ENV` is 'prod':
      /etc/inboxapp/secrets.yml:/etc/inboxapp/config.json

    If `INBOX_ENV` is 'test':
      {srcdir}/etc/secrets-test.yml:{srcdir}/etc/config-test.yml

    If `INBOX_ENV` is 'dev':
      {srcdir}/etc/secrets-dev.yml:{srcdir}/etc/config-dev.yml

    Missing files in the path will be ignored.
    """

    srcdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')

    if 'INBOX_ENV' in os.environ:
        assert os.environ['INBOX_ENV'] in ('dev', 'test', 'prod'), \
            "INBOX_ENV must be either 'dev', 'test', or 'prod'"
        env = os.environ['INBOX_ENV']
    else:
        env = 'prod'

    if env == 'prod':
        base_cfg_path = [
            '/etc/inboxapp/secrets.yml',
            '/etc/inboxapp/config.json',
        ]
    else:
        v = {'env': env, 'srcdir': srcdir}
        base_cfg_path = [
            '{srcdir}/etc/secrets-{env}.yml'.format(**v),
            '{srcdir}/etc/config-{env}.json'.format(**v),
        ]

    if 'INBOX_CFG_PATH' in os.environ:
        cfg_path = os.environ.get('INBOX_CFG_PATH', '').split(os.path.pathsep)
        cfg_path = list(p.strip() for p in cfg_path if p.strip())
    else:
        cfg_path = []

    path = cfg_path + base_cfg_path

    for filename in reversed(path):
        try:
            f = open(filename)
        except (IOError, OSError) as e:
            if e.errno != errno.ENOENT:
                raise
        else:
            with f:
                # this also parses json, which is a subset of yaml
                config.update(yaml.safe_load(f))


def _get_local_feature_flags(config):
    if os.environ.get('FEATURE_FLAGS') is not None:
        flags = os.environ.get('FEATURE_FLAGS').split()
    else:
        flags = config.get('FEATURE_FLAGS', '').split()
    config['FEATURE_FLAGS'] = flags

config = Configuration()
_update_config_from_env(config)
_get_local_feature_flags(config)

if not ('MYSQL_PASSWORD' in config or 'DB_PASSWORD' in config):
    raise Exception(
        'Missing secrets config file? Run `sudo cp etc/secrets-dev.yml '
        '/etc/inboxapp/secrets.yml` and retry')

def get_db_info(database=None):
    info = {
        'user': config.get('DB_USER') or config.get('MYSQL_USER'),
        'password': config.get('DB_PASSWORD') or config.get('MYSQL_PASSWORD'),
        'host': config.get('DB_HOST') or config.get('MYSQL_HOSTNAME'),
        'port': str(config.get('DB_PORT') or config.get('MYSQL_PORT')),
        'name': database or '',
        'engine': config.get('DB_ENGINE') or 'mysql',

    }

    # So we can use docker links to dynamically attach containerized databases
    # https://docs.docker.com/userguide/dockerlinks/#environment-variables
    if info['engine'] == 'mysql':
        info['host'] = os.getenv("MYSQL_PORT_3306_TCP_ADDR", info['host'])
        info['port'] = os.getenv("MYSQL_PORT_3306_TCP_PORT", info['port'])
    return info


def engine_uri(database=None):
    """ By default doesn't include the specific database. """

    info = get_db_info(database)
    if info['engine'] == 'mysql':
        uri_template = 'mysql+pymysql://{username}:{password}@{host}' \
                       ':{port}/{database}?charset=utf8mb4'
    elif info['engine'] == 'postgres':
        uri_template = 'postgresql://{user}:{password}@{host}:{port}/{name}'

    return uri_template.format(**{k: urlquote(v) for k, v in info.items()})


def db_uri():
    database = config.get('MYSQL_DATABASE') or config.get("DB_NAME")
    return engine_uri(database)
