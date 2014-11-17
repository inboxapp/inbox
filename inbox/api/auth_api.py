import os
import json
import base64

from datetime import datetime
from flask import request, g, Blueprint, make_response, Response
from flask import jsonify as flask_jsonify
from flask.ext.restful import reqparse
from sqlalchemy import asc, or_, func
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm import subqueryload

from inbox.models import (Account, Message, Block, Part, Thread, Namespace,
                          Tag, Contact, Calendar, Event, Participant,
                          Transaction)
from inbox.api.kellogs import APIEncoder
from inbox.api import filtering
from inbox.api.validation import (InputError, get_tags, get_attachments,
                                  get_calendar, get_thread, get_recipients,
                                  valid_public_id, valid_event,
                                  valid_event_update, timestamp, boolean,
                                  bounded_str, view, strict_parse_args, limit,
                                  valid_event_action, valid_rsvp,
                                  ValidatableArgument,
                                  validate_draft_recipients)
from inbox import events, contacts, sendmail
from inbox.log import get_logger
from inbox.models.constants import MAX_INDEXABLE_LENGTH
from inbox.models.action_log import schedule_action, ActionError
from inbox.models.session import InboxSession, session_scope
from inbox.search.adaptor import NamespaceSearchEngine, SearchEngineError
from inbox.transactions import delta_sync

from inbox.util.url import provider_from_address
from inbox.auth import handler_from_provider
from inbox.basicauth import NotSupportedError

from err import err

from inbox.ignition import main_engine
engine = main_engine()


app = Blueprint(
    'auth_api',
    __name__,
    url_prefix='/auth')


@app.before_request
def start():
    g.db_session = InboxSession(engine)
    g.log = get_logger()
    g.parser = reqparse.RequestParser(argument_class=ValidatableArgument)
    g.encoder = APIEncoder()



@app.after_request
def finish(response):
    if response.status_code == 200:
        g.db_session.commit()
    g.db_session.close()
    return response


@app.errorhandler(NotImplementedError)
def handle_not_implemented_error(error):
    response = flask_jsonify(message="API endpoint not yet implemented.",
                             type='api_error')
    response.status_code = 501
    return response


@app.errorhandler(InputError)
def handle_input_error(error):
    response = flask_jsonify(message=str(error), type='api_error')
    response.status_code = 400
    return response


@app.route('/')
def index():
    return """
    <html><body>
       Check out the <strong><pre style="display:inline;">docs</pre></strong>
       folder for how to use this API.
    </body></html>
    """


@app.route('/login', methods=['POST'])
def login():  
    data = request.get_json(force=True)

    if data.get('email'):
        email_address = data.get('email')
        
        reauth = True if data.get('reauth') else False

        with session_scope() as db_session:
            account = db_session.query(Account).filter_by(
                email_address=email_address).first()
        
        if account is not None and reauth is False:
            return err(409, 'Account already logged in!')

        provider = provider_from_address(email_address)

        if provider == 'unknown':
            provider = 'custom'

        auth_handler = handler_from_provider(provider)

        response = auth_handler.init_auth(email_address)

        return g.encoder.jsonify({'provider': provider, 'response': response,
                                  'email': email_address})
    else:
        return err(406, 'Email address is required!')


def authorize(email_address, provider, auth_data):
    auth_info = {}
    auth_info['provider'] = provider

    with session_scope() as db_session:
        account = db_session.query(Account).filter_by(
            email_address=email_address).first()

    auth_handler = handler_from_provider(provider)
    auth_response = auth_handler.auth(auth_data)

    if auth_response is False:
        return err(403, 'Authorizatisdsdon error!')

    auth_info.update(auth_response)
    account = auth_handler.create_account(db_session, email_address, auth_info)

    try:
        if auth_handler.verify_account(account):
            db_session.add(account)
            db_session.commit()
    except NotSupportedError as e:
        return err(406, 'Provider not supported!')

    return g.encoder.jsonify({"msg": "Authorization success"})


@app.route('/gmail', methods=['POST'])
def gmail_auth():
    data = request.get_json(force=True)

    if data.get('email'):
        email_address = data.get('email')
    else:
        return err(406, 'Email address is required!')

    if data.get('code'):
        return authorize(email_address, 'gmail', data.get('code'))
    else:
        return err(406, 'Authorization code is required!')


@app.route('/outlook', methods=['POST'])
def outlook_auth():
    data = request.get_json(force=True)

    if data.get('email'):
      email_address = data.get('email')
    else:
        return err(406, 'Email address is required!')

    if data.get('code'):
        return authorize(email_address, 'outlook', data.get('code'))
    else:
        return err(406, 'Authorization code is required!')


@app.route('/custom', methods=['POST'])
def custom_auth():
    data = request.get_json(force=True)
    args = []

    if not data.get('email'):
        return err(406, 'Email address is required!')

    if not data.get('password'):
        return err(406, 'Password is required!')

    if not data.get('imap_server_host'):
        return err(406, 'Imap server host is required!')

    if not data.get('imap_server_port'):
        imap_server_port = 993
    else:
        imap_server_port = data.get('imap_server_port')

    if not data.get('smtp_server_host'):
        return err(406, 'Smtp server host is required!')

    if not data.get('smtp_server_port'):
        smtp_server_port = 587
    else:
        smtp_server_port = data.get('smtp_server_port')

    return authorize(data.get('email'), 'custom', {
                    "provider_type": "custom", "email_address": data.get('email'),
                    "password": data.get('password'), "imap_server_host": data.get('imap_server_host'),
                    "imap_server_port": imap_server_port, "smtp_server_host": data.get('smtp_server_host'),
                    "smtp_server_port": smtp_server_port})


@app.route('/generic', methods=['POST'])
def generic_auth():
    data = request.get_json(force=True)

    if not data.get('email'):
        return err(406, 'Email address is required!')

    if not data.get('password'):
        return err(406, 'Password is required!')

    return authorize(data.get('email'), provider_from_address(data.get('email')), {
                  "provider_type": "generic", "email_address": data.get('email'),
                  "password": data.get('password')})
