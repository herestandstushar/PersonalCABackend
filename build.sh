#!/usr/bin/env bash
# Build step for Render (and similar hosts).
set -o errexit

pip install --upgrade pip
pip install -r requirements/prod.txt

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.prod}"

# collectstatic must not require a live database.
python manage.py collectstatic --no-input
