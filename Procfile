web: python manage.py collectstatic --noinput && gunicorn agripulse.wsgi --log-file - --timeout 120 --workers 2 --bind 0.0.0.0:$PORT
