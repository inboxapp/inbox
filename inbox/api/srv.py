import socket
from flask import Flask, request, jsonify, make_response, g
from flask.ext.restful import reqparse
from werkzeug.exceptions import default_exceptions, HTTPException
from sqlalchemy.orm.exc import NoResultFound

from inbox.api.kellogs import APIEncoder
from nylas.logging import get_logger
from inbox.models import Namespace, Account
from inbox.models.session import global_session_scope, session_scope
from inbox.api.validation import (bounded_str, ValidatableArgument,
                                  strict_parse_args, limit)
from inbox.api.validation import valid_public_id

from inbox.util.url import provider_from_address
from inbox.auth.base import handler_from_provider
from inbox.models.backends.gmail import GmailAccount

from imapclient import IMAPClient
from inbox.auth.generic import create_imap_connection
from inbox.basicauth import (ConnectionError, NotSupportedError,
                             SSLNotSupportedError, OAuthError)
from inbox.sendmail.smtp.postel import SMTPConnection

from ns_api import app as ns_api
from ns_api import DEFAULT_LIMIT

from inbox.webhooks.gpush_notifications import app as webhooks_api


app = Flask(__name__)
# Handle both /endpoint and /endpoint/ without redirecting.
# Note that we need to set this *before* registering the blueprint.
app.url_map.strict_slashes = False


def default_json_error(ex):
    """ Exception -> flask JSON responder """
    logger = get_logger()
    logger.error('Uncaught error thrown by Flask/Werkzeug', exc_info=ex)
    response = jsonify(message=str(ex), type='api_error')
    response.status_code = (ex.code
                            if isinstance(ex, HTTPException)
                            else 500)
    return response

# Patch all error handlers in werkzeug
for code in default_exceptions.iterkeys():
    app.error_handler_spec[None][code] = default_json_error


@app.before_request
def auth():
    """ Check for account ID on all non-root URLS """
    if request.path in ('/accounts', '/accounts/', '/') \
            or request.path.startswith('/new_user') \
            or request.path.startswith('/w/'):
        return

    if not request.authorization or not request.authorization.username:

        AUTH_ERROR_MSG = ("Could not verify access credential.", 401,
                          {'WWW-Authenticate': 'Basic realm="API '
                              'Access Token Required"'})

        auth_header = request.headers.get('Authorization', None)

        if not auth_header:
            return make_response(AUTH_ERROR_MSG)

        parts = auth_header.split()

        if (len(parts) != 2 or parts[0].lower() != 'bearer' or not parts[1]):
            return make_response(AUTH_ERROR_MSG)
        namespace_public_id = parts[1]

    else:
        namespace_public_id = request.authorization.username

    with global_session_scope() as db_session:
        try:
            valid_public_id(namespace_public_id)
            namespace = db_session.query(Namespace) \
                .filter(Namespace.public_id == namespace_public_id).one()
            g.namespace_id = namespace.id
            g.account_id = namespace.account.id
        except NoResultFound:
            return make_response((
                "Could not verify access credential.", 401,
                {'WWW-Authenticate': 'Basic realm="API '
                 'Access Token Required"'}))


@app.after_request
def finish(response):
    origin = request.headers.get('origin')
    if origin:  # means it's just a regular request
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Headers'] = \
            'Authorization,Content-Type'
        response.headers['Access-Control-Allow-Methods'] = \
            'GET,PUT,POST,DELETE,OPTIONS,PATCH'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response


@app.route('/accounts/')
def ns_all():
    """ Return all namespaces """
    # We do this outside the blueprint to support the case of an empty
    # public_id.  However, this means the before_request isn't run, so we need
    # to make our own session.
    with global_session_scope() as db_session:
        parser = reqparse.RequestParser(argument_class=ValidatableArgument)
        parser.add_argument('limit', default=DEFAULT_LIMIT, type=limit,
                            location='args')
        parser.add_argument('offset', default=0, type=int, location='args')
        parser.add_argument('email_address', type=bounded_str, location='args')
        args = strict_parse_args(parser, request.args)

        query = db_session.query(Namespace)
        if args['email_address']:
            query = query.join(Account)
            query = query.filter_by(email_address=args['email_address'])

        query = query.limit(args['limit'])
        if args['offset']:
            query = query.offset(args['offset'])

        namespaces = query.all()
        encoder = APIEncoder()
        return encoder.jsonify(namespaces)


@app.route('/new_user/', methods=['POST'])
def add_new_user():
    response = {}
    encoder = APIEncoder()

    data = request.get_json(force=True)
    email_address = data.get('email_address')
    password = data.get('password')
    auth_details = data.get('auth_details')
    reauth = data.get('reauth')
    target = data.get('target', 0)

    if not email_address:
        response['error'] = 'Missing key - "email_address"!'
        return encoder.jsonify(response)

    shard_id = target << 48

    with session_scope(shard_id) as db_session:
        account = db_session.query(Account).filter_by(
            email_address=email_address).first()
        if account is not None and not reauth:
            response['error'] = 'Already have this account!'
            return encoder.jsonify(response)

        auth_info = {}
        provider = provider_from_address(email_address)
        if 'gmail' in provider:
            auth_handler = handler_from_provider(provider)
            response['oauth_url'] = auth_handler.get_oauth_url(email_address)
            response['links'] = {'confirm_url': request.url + '/confirm_oauth'}
            namespace = Namespace()
            account = GmailAccount(namespace=namespace)
            account.sync_should_run = False
            account.refresh_token = '_placeholder_'
            account.email_address = email_address
        else:
            if not password:
                response['error'] = 'Missing key - "password"!'
                return encoder.jsonify(response)
            auth_info['email'] = email_address
            auth_info['password'] = password
            if provider != 'unknown':
                auth_handler = handler_from_provider(provider)
                auth_info['provider'] = provider
                try:
                    if reauth:
                        account = auth_handler.update_account(account, auth_info)
                    else:
                        account = auth_handler.create_account(email_address, auth_info)
                except Exception as e:
                    response['error'] = e.msg
            else:
                auth_info['provider'] = 'custom'
                auth_handler = handler_from_provider('custom')
                if not auth_details:
                    auth_info.update(try_fill_config_data(email_address, password))
                else:
                    auth_info.update(auth_details)
                try:
                    if reauth:
                        account = auth_handler.update_account(account, auth_info)
                    else:
                        account = auth_handler.create_account(email_address, auth_info)
                except Exception as e:
                    response['error'] = str(e)
            try:
                auth_handler.verify_account(account)
                response['data'] = 'OK. Authenticated account for {}'.format(email_address)
            except Exception as e:
                response['error'] = str(e)
        db_session.add(account)
        db_session.commit()
    return encoder.jsonify(response)


def try_fill_config_data(email_address, password):
    response = {}
    subdomains = ['mail.', 'imap.', 'smtp.', '']
    domain = email_address.split('@')[1].lower()
    smtp_port = 587
    imap_port = 993
    log = get_logger()

    for imap_host in [subdomain + domain for subdomain in subdomains]:
        try:
            create_imap_connection(imap_host, imap_port, True, use_timeout=10)
            response['imap_server_host'] = imap_host
            response['imap_server_port'] = imap_port
            break
        except SSLNotSupportedError:
            create_imap_connection(imap_host, imap_port, False, use_timeout=10)
            response['imap_server_host'] = imap_host
            response['imap_server_port'] = imap_port
            response['ssl_required'] = False
            break
        except (IMAPClient.Error, socket.error):
            continue
    if 'imap_server_host' not in response:
        raise ConnectionError('IMAP connection failed. Check your password. '
                              'If error persists try provide connection details')
    for smtp_host in [subdomain + domain for subdomain in subdomains]:
        try:
            with SMTPConnection(0, email_address, email_address, 'password', password,
                                (smtp_host, smtp_port), True, log):
                response['smtp_server_host'] = smtp_host
                response['smtp_server_port'] = smtp_port
                break
        except:
            continue
    if 'smtp_server_host' not in response:
        raise ConnectionError('SMTP connection failed. Check your password. '
                              'If error persists try provide connection details')
    return response


@app.route('/new_user/confirm_oauth/', methods=['POST'])
def confim_oauth_user():
    response = {}
    encoder = APIEncoder()
    data = request.get_json(force=True)
    email_address = data.get('email_address')
    token = data.get('token')
    target = data.get('target', 0)

    if not email_address:
        response['error'] = 'Missing key - "email_address"!'
        return encoder.jsonify(response)
    if not token:
        response['error'] = 'Missing key - "token"!'
        return encoder.jsonify(response)

    shard_id = target << 48

    with session_scope(shard_id) as db_session:
        account = db_session.query(Account).filter_by(
            email_address=email_address).first()
        if account is None:
            response['error'] = 'Don\'t have this account!'
            return encoder.jsonify(response)
        auth_info = {}
        provider = provider_from_address(email_address)
        auth_info['provider'] = provider
        auth_handler = handler_from_provider(provider)
        try:
            auth_response = auth_handler._get_authenticated_user(token)
            auth_response['contacts'] = True
            auth_response['events'] = True
            auth_info.update(auth_response)
        except OAuthError:
            response['error'] = "Invalid authorization code, try again..."
            return encoder.jsonify(response)
        account = auth_handler.update_account(account, auth_info)
        try:
            if auth_handler.verify_account(account):
                db_session.add(account)
                db_session.commit()
                response['data'] = 'OK. Authenticated account for {}'.format(email_address)
        except NotSupportedError as e:
            response['error'] = str(e)
            return encoder.jsonify(response)
    return encoder.jsonify(response)


@app.route('/logout')
def logout():
    """ Utility function used to force browsers to reset cached HTTP Basic Auth
        credentials """
    return make_response((
        "<meta http-equiv='refresh' content='0; url=/''>.",
        401,
        {'WWW-Authenticate': 'Basic realm="API Access Token Required"'}))


app.register_blueprint(ns_api)
app.register_blueprint(webhooks_api)  # /w/...
