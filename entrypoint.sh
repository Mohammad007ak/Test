#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py setup_roles

exec "$@"
