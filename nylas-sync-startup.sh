#!/bin/sh
export REPLACE_VARS='$MYSQL_ENV_MYSQL_USERNAME:$MYSQL_ENV_MYSQL_PASSWORD:$MYSQL_PORT_3306_TCP_PORT'
envsubst "$REPLACE_VARS" < /etc/inboxapp/config-env.json > /etc/inboxapp/config.json
envsubst "$REPLACE_VARS" < /etc/inboxapp/secrets-env.yml > /etc/inboxapp/secrets.yml

