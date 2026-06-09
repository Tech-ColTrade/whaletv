release: python manage.py migrate --noinput
web: gunicorn core.wsgi:application --workers ${WEB_CONCURRENCY:-2} --threads 4 --timeout 120
