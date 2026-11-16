#!/bin/sh
set -e
python manage.py migrate --noinput
if [ "${DONNEES_EXEMPLE:-0}" = "1" ]; then
  python manage.py initialiser --exemples
else
  python manage.py initialiser
fi
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout 60 \
  --access-logfile - \
  --access-logformat '%({x-forwarded-for}i)s %(m)s %(U)s %(s)s %(b)s %(L)ss'
