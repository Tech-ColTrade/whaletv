FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER=/usr/bin/chromedriver

# Chromium + driver para Selenium, y libpq para Postgres.
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        libpq5 \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Genera los estáticos (admin, etc.) servidos por WhiteNoise.
RUN python manage.py collectstatic --noinput

# Render expone el puerto en $PORT.
CMD gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --threads 4 --timeout 120
