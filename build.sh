#!/usr/bin/env bash
# Build command para el runtime NATIVO de Render (Python).
# OJO: este runtime no trae Chromium, así que la sincronización con Selenium
# NO funcionará aquí. Para que funcione, despliega con Docker (Dockerfile).
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
