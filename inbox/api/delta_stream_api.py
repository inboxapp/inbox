"""
Provides an endpoint that returns all transactions for all accounts.

Endpoint: /delta_stream/

@author: Nils Reimers <Rnils@web.de>
"""
from __future__ import print_function
import os
import sys
import json
import time
import uuid
import base64
import gevent
import itertools
from pprint import pprint

from sqlalchemy import asc, desc, bindparam
from hashlib import sha256
from datetime import datetime
from collections import namedtuple
from werkzeug.exceptions import HTTPException
from flask import (request, g, Blueprint, make_response, Response, stream_with_context)
from flask import jsonify
from flask.ext.restful import reqparse


from inbox.basicauth import NotSupportedError
from inbox.util.url import provider_from_address
from inbox.providers import providers
from inbox.models.session import session_scope
from inbox.models import Transaction, Message, Thread, Account, Namespace
from nylas.logging import get_logger


from inbox.transactions import delta_sync

app = Blueprint('delta_stream_api',__name__,url_prefix='/delta_stream')

def default_json_error(ex):
    """ Exception -> flask JSON responder """ 
    logger = get_logger()

    logger.error('Uncaught error thrown by Flask/Werkzeug', exc_info=ex)
    response = jsonify(message=str(ex), type='api_error')
    response.status_code = (ex.code
                            if isinstance(ex, HTTPException)
                            else 500)


    return response

@app.route('/')
def pull():
    pointer = int(request.values.get('pointer'))
    result_limit = int(request.values.get('limit')) if 'limit' in request.values else  100
    output = {}
    
    if result_limit < 0 or result_limit > 10000:
        return default_json_error('Invalid value for result_lmit')

    output['pointer_start'] = pointer
    with session_scope(0) as db_session:
        deltas, pointer_end = delta_sync.format_transactions_after_pointer(None, pointer, db_session, result_limit, filter_for_namespace=False)

        output['deltas'] = deltas
        output['pointer_end'] = pointer_end

    return jsonify(output)