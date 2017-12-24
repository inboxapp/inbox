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

from inbox.config import config



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

####
# Returns which provider is needed for a certain email address
####
@app.route('/provider/<email>')
def get_provider(email):
    output = {}    
    output['email'] = email
    output['provider'] = provider_from_address(email)
    if output['provider'] in providers:
        output['provider_info'] = providers[output['provider']]
    return jsonify(output)

####
# Login with Google / Gmail
####
@app.route('/gmail/login/', methods = ['GET', 'POST'])
def login_gmail_account():
    authcode = request.values.get('authcode')
    redirecturi = request.values.get('redirecturi')
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


####
# New account registration for Gmail
####
@app.route('/gmail/register', methods = ['GET', 'POST'])
def new_gmail_account():
    logger = get_logger()
  
    authcode = request.values.get('authcode')
    redirecturi = request.values.get('redirecturi')
    reauth = True
    auth_handler = GmailAuthHandler(provider_name='gmail')
    auth_handler.OAUTH_REDIRECT_URI = redirecturi

    auth_info = auth_handler._get_authenticated_user(authcode)
    auth_info['contacts'] = True
    auth_info['events'] = True
    auth_info['provider'] = 'gmail'

    email_address = auth_info['email']
    account_exsist = False

    # Check for email in allowed emails list
    allowed_emails = config.get('ALLOWED_EMAILS')
    if allowed_emails and email_address not in allowed_emails:
        return jsonify({"code": "email_not_allowed", "message": "Email not allowed", "profile": auth_info})

    with session_scope(0) as db_session:
        account = db_session.query(Account).filter_by(email_address=email_address).first()
        if account is not None and not reauth:
            api_id = account.namespace.public_id
            return jsonify({"code": "account_exist", "message": "Account already exist", "api_id": api_id})
        elif account is not None and reauth:
            account_exsist = True
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

    if account_exsist:
        return jsonify({"code": "account_updated", "message": "Account already exist and Updated", "api_id": api_id})

    return jsonify({"code": "account_created", "message": "new account created", "api_id": api_id})
