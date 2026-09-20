"""
Production settings — extends base.py.
"""

from .base import *  # noqa: F401, F403

DEBUG = False

# Render injects RENDER_EXTERNAL_HOSTNAME — auto-allow it so a missing
# DJANGO_ALLOWED_HOSTS env var does not 400 every request / health check.
_render_host = env("RENDER_EXTERNAL_HOSTNAME", default="")  # noqa: F405
if _render_host and _render_host not in ALLOWED_HOSTS:  # noqa: F405
    ALLOWED_HOSTS = list(ALLOWED_HOSTS) + [_render_host, ".onrender.com"]  # noqa: F405

# Allow the production Vercel app + preview deployments even if the Render
# env var lags behind a renamed project URL.
_CORS_DEFAULTS = [
    "https://personal-caui.vercel.app",
    "https://finsight.vercel.app",
]
CORS_ALLOWED_ORIGINS = list(  # noqa: F405
    dict.fromkeys([*CORS_ALLOWED_ORIGINS, *_CORS_DEFAULTS])  # noqa: F405
)
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://[\w-]+\.vercel\.app$",
    r"^https://[\w-]+-[\w-]+-[\w]+\.vercel\.app$",  # team preview URLs
]
CSRF_TRUSTED_ORIGINS = list(  # noqa: F405
    dict.fromkeys([*CSRF_TRUSTED_ORIGINS, *CORS_ALLOWED_ORIGINS])  # noqa: F405
)

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
