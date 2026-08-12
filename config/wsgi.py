"""
WSGI config for FinSight project.
"""

import os

from django.core.wsgi import get_wsgi_application

# Default to prod so PaaS hosts (Render, etc.) are safe if the env var is
# forgotten. Local `runserver` / manage.py still set/override to dev.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
application = get_wsgi_application()
