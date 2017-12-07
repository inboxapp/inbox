import base64
import os
import time

import hvac

from inbox.config import config

vault_config = config.get('VAULT')


client = hvac.Client(url=vault_config['URL'])

client.auth_approle(vault_config['APP_ROLE_ID'], vault_config['APP_ROLE_SECRET_ID'])


def encrypt(plaintext, named_key):
    if not plaintext:
        return ''

    if not named_key:
        return ''

    try:
        result = client.write(
            'transit/encrypt/' + named_key,
            plaintext=base64.b64encode(plaintext)
        )

        return result['data']['ciphertext'].encode('utf-8')
    except Exception as e:
        print e
        return ''


def decrypt(ciphertext, named_key):
    if not ciphertext:
        return ''

    if not named_key:
        return ''

    try:
        result = client.write(
            'transit/decrypt/' + named_key,
            ciphertext=ciphertext
        )

        return base64.b64decode(result['data']['plaintext']).encode('utf-8')
    except Exception as e:
        print e
        return ''


def encrypt_batch(batch_input, named_key):
    if not isinstance(batch_input, list):
        return []

    if len(batch_input) == 0:
        return []

    # start = time.time()

    batch_input = [
        {'plaintext': base64.b64encode(element.encode('utf-8'))}
        for element
        in batch_input
    ]

    try:
        result = client.write(
            'transit/encrypt/' + named_key,
            batch_input=batch_input
        )

        # end = time.time()
        # latency_millis = (end - start) * 1000
        # print ''.join(['[vault] encryption latency is: ', str(latency_millis), 'ms'])

        return [
            element['ciphertext'].encode('utf-8')
            for element
            in result['data']['batch_results']
        ]
    except Exception as e:
        print e
        return [ '' for _ in batch_input ]


def decrypt_batch(batch_input, namespace_public_id):
    pass
