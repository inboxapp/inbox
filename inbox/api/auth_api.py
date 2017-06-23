"""
Provides authentication abilities via the API endpoint /auth/...

@author: Nils Reimers <Rnils@web.de>
"""

import os
import sys
import json
import time
import uuid
import base64
import gevent
import itertools


from hashlib import sha256
from datetime import datetime
from collections import namedtuple
from werkzeug.exceptions import HTTPException
from flask import (request, g, Blueprint, make_response, Response,
                   stream_with_context)
from flask import jsonify
from flask.ext.restful import reqparse


from inbox.basicauth import NotSupportedError
from inbox.util.url import provider_from_address
from inbox.providers import providers
from inbox.auth.gmail import GmailAuthHandler
from inbox.models.session import session_scope
from inbox.models import Account
from nylas.logging import get_logger




app = Blueprint('auth_api',__name__,url_prefix='/auth')

def default_json_error(ex):
    """ Exception -> flask JSON responder """ 
    logger = get_logger()

    logger.error('Uncaught error thrown by Flask/Werkzeug', exc_info=ex)
    response = jsonify(message=str(ex), type='api_error')
    response.status_code = (ex.code
                            if isinstance(ex, HTTPException)
                            else 500)


    return response

@app.route('/provider/<email>')
def get_provider(email):
    output = {}    
    output['email'] = email
    output['provider'] = provider_from_address(email)
    if output['provider'] in providers:
        output['provider_info'] = providers[output['provider']]
    return jsonify(output)

@app.route('/gmail/login/')
def login_gmail_account():
    authcode = request.args.get('authcode')
    redirecturi = request.args.get('redirecturi')
    auth_handler = GmailAuthHandler(provider_name='gmail')
    auth_handler.OAUTH_REDIRECT_URI = redirecturi

    auth_info = auth_handler._get_authenticated_user(authcode)

    email_address = auth_info['email']

    with session_scope(0) as db_session:
        account = db_session.query(Account).filter_by(email_address=email_address).first()
        if account is None:
            return default_json_error('The account does not exist!')

        api_id = account.namespace.public_id
        return jsonify({"message": "Login successful", "api_id": api_id})

@app.route('/gmail/register')
def new_gmail_account():
    logger = get_logger()
    #email_address = request.args.get('email')
    authcode = request.args.get('authcode')
    redirecturi = request.args.get('redirecturi')
    reauth = True
    auth_handler = GmailAuthHandler(provider_name='gmail')
    auth_handler.OAUTH_REDIRECT_URI = redirecturi

    auth_info = auth_handler._get_authenticated_user(authcode)
    auth_info['contacts'] = True
    auth_info['events'] = True
    auth_info['provider'] = 'gmail'

    email_address = auth_info['email']

    with session_scope(0) as db_session:
        account = db_session.query(Account).filter_by(email_address=email_address).first()
        if account is not None and not reauth:
            api_id = account.namespace.public_id
            return jsonify({"message": "Account already existent", "api_id": api_id})
        elif account is not None and reauth:
            account = auth_handler.update_account(account, auth_info)
        else:
            account = auth_handler.create_account(email_address, auth_info)
    
        try:
            if auth_handler.verify_account(account):
                db_session.add(account)
                db_session.commit()
        except NotSupportedError as e:
            return default_json_error(e)

        api_id = account.namespace.public_id
    return jsonify({"message": "new account created", "api_id": api_id})
