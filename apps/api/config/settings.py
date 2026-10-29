from pathlib import Path

import dj_database_url
from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured
from environ import Env

env = Env()

BASE_DIR = Path(__file__).resolve().parent.parent

# -----------------------------------------------------------------------------
# Django
# -----------------------------------------------------------------------------
env.read_env(
    env_file=BASE_DIR / ".env",
    overwrite=False,
)

DEBUG = env.bool(
    var="DEBUG",
    default=True,
)

SECRET_KEY = env("SECRET_KEY")

ROOT_URLCONF = "config.urls"

ASGI_APPLICATION = "config.asgi.application"

WSGI_APPLICATION = "config.wsgi.application"


# -----------------------------------------------------------------------------
# HOSTS
# -----------------------------------------------------------------------------
ALLOWED_HOSTS = env(
    var="ALLOWED_HOSTS",
    cast=list,
    default=[],
)


# -----------------------------------------------------------------------------
# CORS
# -----------------------------------------------------------------------------
FRONTEND_URL = env(
    var="FRONTEND_URL",
    default="http://localhost:5173",
)

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = [
    *default_headers,
]

CORS_ALLOWED_ORIGINS = env(
    var="CORS_ALLOWED_ORIGINS",
    cast=list,
    default=[FRONTEND_URL],
)


# -----------------------------------------------------------------------------
# CSRF
# -----------------------------------------------------------------------------
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_NAME = "csrftoken"
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=not DEBUG)

CSRF_TRUSTED_ORIGINS = env(
    var="CSRF_TRUSTED_ORIGINS",
    cast=list,
    default=[FRONTEND_URL],
)


# -----------------------------------------------------------------------------
# Session
# -----------------------------------------------------------------------------
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_NAME = "sessionid"
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=not DEBUG)

SESSION_CACHE_ALIAS = "default"

SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=not DEBUG)
SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]


# -----------------------------------------------------------------------------
# Internationalization
# -----------------------------------------------------------------------------
USE_TZ = True

TIME_ZONE = "America/Sao_Paulo"

LOCALE_PATHS = [BASE_DIR / "locale"]

LANGUAGE_CODE = "en-us"
LANGUAGES = [
    ("en", "English"),
    ("pt", "Portuguese"),
]


# -----------------------------------------------------------------------------
# Application
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.postgres",
]

THIRD_PARTY_APPS = [
    "daphne",
    "auditlog",
    # -------------------------------------------------------------------------
    # Django Tasks
    # -------------------------------------------------------------------------
    "django_rq",
    "django_tasks",
    "django_tasks_rq",
    # -------------------------------------------------------------------------
    # DRF
    # -------------------------------------------------------------------------
    "corsheaders",
    "drf_spectacular",
    "rest_framework",
    "drf_standardized_errors",
    # -------------------------------------------------------------------------
    # Guardian (object-level permissions)
    # -------------------------------------------------------------------------
    "guardian",
    # -------------------------------------------------------------------------
    # Allauth
    # -------------------------------------------------------------------------
    "allauth",
    "allauth.account",
    "allauth.headless",
    "allauth.usersessions",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    # -------------------------------------------------------------------------
    # Payments
    # -------------------------------------------------------------------------
    "payments",
]

INSTALLED_APPS = [
    *THIRD_PARTY_APPS,
    *DJANGO_APPS,
    # -------------------------------------------------------------------------
    # App Domains
    # -------------------------------------------------------------------------
    "apps.domains.client",
    "apps.domains.setup",
    "apps.domains.gallery",
    "apps.domains.commerce",
    "apps.domains.photographer",
    "apps.domains.contract",
    # -------------------------------------------------------------------------
    # App Common
    # -------------------------------------------------------------------------
    "apps.common.websocket",
    "apps.common.streaming",
]


# -----------------------------------------------------------------------------
# Middleware
# -----------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "auditlog.middleware.AuditlogMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

# -----------------------------------------------------------------------------
# Template
# -----------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
            "builtins": [
                "django.templatetags.static",
            ],
        },
    },
]

# -----------------------------------------------------------------------------
# Email
# -----------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_PORT = env("EMAIL_PORT")
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")

EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=not DEBUG)
EMAIL_USE_SSL = False

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")

# -----------------------------------------------------------------------------
# Database
# -----------------------------------------------------------------------------
DATABASE_URL = env("DATABASE_URL")

DATABASES = {
    "default": dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=600,
    )
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -----------------------------------------------------------------------------
# Authentication
# -----------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -----------------------------------------------------------------------------
# Redis
# -----------------------------------------------------------------------------
REDIS_URL = env("REDIS_URL")

# -----------------------------------------------------------------------------
# RQ
# -----------------------------------------------------------------------------
RQ_QUEUES = {
    "default": {
        "URL": REDIS_URL,
        "DEFAULT_TIMEOUT": 360,
    }
}

# -----------------------------------------------------------------------------
# Channels
# -----------------------------------------------------------------------------
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            # `channels_redis` long-polls for new messages with a 5s BZPOPMIN
            # (`RedisChannelLayer.brpop_timeout`). redis-py's own client-side
            # `socket_timeout` now defaults to 5s too (`DEFAULT_SOCKET_TIMEOUT`),
            # so the two races every cycle and the client-side timeout usually
            # wins, raising `redis.exceptions.TimeoutError` and killing every
            # WebSocket connection roughly every 5 seconds. Set a socket timeout
            # comfortably above 5s so the server's own nil reply always wins.
            "hosts": [
                {
                    "address": REDIS_URL,
                    "socket_timeout": 20,
                }
            ],
        },
    }
}

# -----------------------------------------------------------------------------
# Cache
# -----------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# -----------------------------------------------------------------------------
# Tasks
# -----------------------------------------------------------------------------
TASKS = {
    "default": {
        "BACKEND": env(
            "DJANGO_TASKS_BACKEND",
            default="django_tasks.backends.immediate.ImmediateBackend" if DEBUG else "django_tasks_rq.RQBackend",
        ),
        "QUEUES": ["default"],
    }
}

# -----------------------------------------------------------------------------
# Static
# -----------------------------------------------------------------------------
STATIC_URL = "/api/static/"
STATIC_ROOT = BASE_DIR / "static"


# -----------------------------------------------------------------------------
# MEDIA
# -----------------------------------------------------------------------------
MEDIA_URL = "/api/media/"
MEDIA_ROOT = BASE_DIR / "media"

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
}

# -----------------------------------------------------------------------------
# DRF
# -----------------------------------------------------------------------------
API_THROTTLE_ANON = env("API_THROTTLE_ANON", default="100/hour")
API_THROTTLE_USER = env("API_THROTTLE_USER", default="2000/hour")
API_THROTTLE_UNSPLASH = env("API_THROTTLE_UNSPLASH", default="300/hour")

API_VIEW_CACHE_TIMEOUT = env.int("API_VIEW_CACHE_TIMEOUT", default=60)

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly",),
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework.authentication.SessionAuthentication",),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": API_THROTTLE_ANON,
        "user": API_THROTTLE_USER,
        "unsplash": API_THROTTLE_UNSPLASH,
    },
    "DEFAULT_FILTER_BACKENDS": (
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_VERSION": "api",
    "ALLOWED_VERSIONS": ["api"],
    "EXCEPTION_HANDLER": "drf_standardized_errors.handler.exception_handler",
}

if not DEBUG:
    REST_FRAMEWORK = {
        **REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {
            "anon": "5000/hour",
            "user": "50000/hour",
        },
    }

# -----------------------------------------------------------------------------
# Spectacular
# -----------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "OPEN-PHOTOGRAPH API",
    "DESCRIPTION": "OPEN-PHOTOGRAPH API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# -----------------------------------------------------------------------------
# Allauth
# -----------------------------------------------------------------------------
SITE_ID = 1
ALLAUTH_HEADLESS_ONLY = True

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
    "guardian.backends.ObjectPermissionBackend",
]

# -----------------------------------------------------------------------------
# Guardian
# -----------------------------------------------------------------------------
# Every endpoint that checks object permissions already requires authentication
# (IsAuthenticated), so guardian's anonymous-user bookkeeping is unnecessary here.
ANONYMOUS_USER_NAME = None

HEADLESS_ONLY = True
HEADLESS_SERVE_SPECIFICATION = True

HEADLESS_FRONTEND_URLS = {
    "socialaccount_login_cancelled": "/auth/login",
    "socialaccount_login_error": "/auth/login",
    "account_confirm_email": "/auth/verify-email/{key}",
    "account_reset_password_from_key": "/auth/reset-password/{key}",
}

ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = [
    "email*",
    "password1*",
    "password2*",
]
ACCOUNT_EMAIL_VERIFICATION = "optional"
CLIENT_REQUIRE_VERIFIED_EMAIL_LINK = env.bool("CLIENT_REQUIRE_VERIFIED_EMAIL_LINK", default=True)

GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID", default="")
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET", default="")

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "AUTH_PARAMS": {
            "access_type": "offline",
            "prompt": "consent",
        },
        "SCOPE": [
            "profile",
            "email",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    },
}

SOCIALACCOUNT_EMAIL_AUTHENTICATION = True

if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    SOCIALACCOUNT_PROVIDERS["google"]["APP"] = {
        "client_id": GOOGLE_CLIENT_ID,
        "secret": GOOGLE_CLIENT_SECRET,
        "key": "",
    }

SOCIALACCOUNT_STORE_TOKENS = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
LOGIN_REDIRECT_URL = f"{FRONTEND_URL}/setup/drive"

# -----------------------------------------------------------------------------
# Payment gateway configuration
# -----------------------------------------------------------------------------
# Host usado para construir URLs absolutas nos callbacks dos providers.
PAYMENT_HOST = env("PAYMENT_HOST", default="localhost:8000")
PAYMENT_USES_SSL = env.bool("PAYMENT_USES_SSL", default=not DEBUG)
PAYMENT_MODEL = "commerce.Payment"

# Native django-payments factory; secrets are configured only on the server.
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
MERCADO_PAGO_ACCESS_TOKEN = env("MERCADO_PAGO_ACCESS_TOKEN", default="")

PAYMENT_VARIANTS = {}

if STRIPE_SECRET_KEY:
    PAYMENT_VARIANTS["stripe"] = (
        "payments.stripe.StripeProviderV3",
        {
            "api_key": STRIPE_SECRET_KEY,
            "use_token": True,
            "endpoint_secret": env("STRIPE_WEBHOOK_SECRET", default=""),
        },
    )

if MERCADO_PAGO_ACCESS_TOKEN:
    PAYMENT_VARIANTS["mercado_pago"] = (
        "payments.mercadopago.MercadoPagoProvider",
        {
            "access_token": MERCADO_PAGO_ACCESS_TOKEN,
            "sandbox": env.bool("MERCADO_PAGO_SANDBOX", default=False),
        },
    )


# -----------------------------------------------------------------------------
# S3
# -----------------------------------------------------------------------------
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
AWS_ENDPOINT_URL = env("AWS_ENDPOINT_URL", default="") or None
AWS_REGION = env("AWS_REGION", default="us-east-1")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")
AWS_BUCKET = env("AWS_BUCKET", default="")
AWS_S3_ADDRESSING_STYLE = env("AWS_S3_ADDRESSING_STYLE", default="virtual")

# -----------------------------------------------------------------------------
# Storage
# -----------------------------------------------------------------------------
# Original-file providers are selected in Setup. Internal media storage is separate.
SOURCE_S3_ACCESS_KEY_ID = env("SOURCE_S3_ACCESS_KEY_ID", default="")
SOURCE_S3_SECRET_ACCESS_KEY = env("SOURCE_S3_SECRET_ACCESS_KEY", default="")
SOURCE_S3_BUCKET_NAME = env("SOURCE_S3_BUCKET_NAME", default="")
SOURCE_S3_ENDPOINT_URL = env("SOURCE_S3_ENDPOINT_URL", default="") or None
SOURCE_S3_REGION_NAME = env("SOURCE_S3_REGION_NAME", default="us-east-1")

SYSTEM_STORAGE_PROVIDER = env(
    "SYSTEM_STORAGE_PROVIDER",
    default=env(
        "STORAGE_PROVIDER",
        default="local" if DEBUG else "s3",
    ),
)

if SYSTEM_STORAGE_PROVIDER not in {"local", "s3"}:
    raise ImproperlyConfigured("SYSTEM_STORAGE_PROVIDER deve ser local ou s3.")

STORAGES = {
    "s3": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "signature_version": "s3v4",
            "addressing_style": AWS_S3_ADDRESSING_STYLE,
            "access_key": AWS_ACCESS_KEY_ID,
            "secret_key": AWS_SECRET_ACCESS_KEY,
            "endpoint_url": AWS_ENDPOINT_URL,
            "bucket_name": AWS_BUCKET,
            "region_name": AWS_REGION,
        },
    },
    "local": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

STORAGES["default"] = STORAGES[SYSTEM_STORAGE_PROVIDER].copy()

# Signature provider credentials are configured only on the server.
ZAPSIGN_API_TOKEN = env("ZAPSIGN_API_TOKEN", default="")
ZAPSIGN_SANDBOX_API_TOKEN = env("ZAPSIGN_SANDBOX_API_TOKEN", default="")
