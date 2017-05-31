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

from flask import (request, g, Blueprint, make_response, Response,
                   stream_with_context)
from flask import jsonify as flask_jsonify
from flask.ext.restful import reqparse


from inbox.util.url import provider_from_address

from inbox.providers import providers

app = Blueprint('auth_api',__name__,url_prefix='/auth')


@app.route('/provider/<email>')
def get_provider(email):
    output = {}    
    output['email'] = email
    output['provider'] = provider_from_address(email)
    if output['provider'] in providers:
        output['provider_info'] = providers[output['provider']]
    return json.dumps(output)