"""
Production settings — extends base.py.
"""

from .base import *  # noqa: F401, F403

DEBUG = False

# Render (and most PaaS) terminate TLS at the proxy and forward HTTP internally.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Security
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)  # noqa: F405
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Neon / managed Postgres: avoid holding idle connections through the pooler.
DATABASES["default"]["CONN_MAX_AGE"] = env.int(  # noqa: F405
    "DB_CONN_MAX_AGE", default=0
)

# Static files
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405

# Sentry (optional — installed via requirements/prod.txt)
SENTRY_DSN = env("SENTRY_DSN", default="")  # noqa: F405
if SENTRY_DSN:
    try:
        import sentry_sdk  # noqa: E402

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
        )
    except ImportError:
        pass
