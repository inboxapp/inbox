import base64
import os
import time

import hvac

from inbox.config import config

vault_config = config.get('VAULT')


client = hvac.Client(url=vault_config['URL'])

client.auth_approle(vault_config['APP_ROLE_ID'], vault_config['APP_ROLE_SECRET_ID'])


def encrypt(plaintext, namespace_public_id):
    start = time.time()

    if not plaintext:
        return ''

    if not namespace_public_id:
        return ''

    named_key = 'account-' + namespace_public_id

    # TODO: add proper handling of exception
    try:
        result = client.write(
            'transit/encrypt/' + named_key,
            plaintext=base64.b64encode(plaintext)
        )

        end = time.time()
        latency_millis = (end - start) * 1000
        print ''.join(['[vault] encryption latency is: ', str(latency_millis), 'ms'])

        return result['data']['ciphertext'].encode('utf-8')
    except Exception as e:
        print e
        return ''


def decrypt(ciphertext, namespace_public_id):
    start = time.time()

    if not ciphertext:
        return ''

    if not namespace_public_id:
        return ''

    named_key = 'account-' + namespace_public_id

    # TODO: add proper handling of exception
    try:
        result = client.write(
            'transit/decrypt/' + named_key,
            ciphertext=ciphertext
        )

        end = time.time()
        latency_millis = (end - start) * 1000
        print ''.join(['[vault] decryption latency is: ', str(latency_millis), 'ms'])

        return base64.b64decode(result['data']['plaintext']).encode('utf-8')
    except Exception as e:
        print e
        return ''


def encrypt_batch(batch_input, namespace_public_id):
    if not isinstance(batch_input, list):
        return []

    if len(batch_input) == 0:
        return []

    start = time.time()

    batch_input = [
        {"plaintext": base64.b64encode(element["plaintext"])}
        for element
        in batch_input
    ]

    named_key = 'account-' + namespace_public_id

    try:
        result = client.write(
            'transit/encrypt/' + named_key,
            batch_input=batch_input
        )

        end = time.time()
        latency_millis = (end - start) * 1000
        print ''.join(['[vault] encryption latency is: ', str(latency_millis), 'ms'])

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
