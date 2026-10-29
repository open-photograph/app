#!/bin/sh
set -eu

exec python manage.py rqworker default --with-scheduler "$@"
