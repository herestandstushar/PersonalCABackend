#!/usr/bin/env bash
# Build step for Render (and similar hosts).
set -o errexit

pip install --upgrade pip
pip install -r requirements/prod.txt

# Collect static assets for WhiteNoise. Migrations run in the release / start
# command so a failed migrate cannot leave a half-built slug.
python manage.py collectstatic --no-input
