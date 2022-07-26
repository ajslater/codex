"""
Django settings for codex project.

Generated by 'django-admin startproject' using Django 3.0.3.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.0/ref/settings/
"""


import os

from pathlib import Path

from tzlocal import get_localzone_name
from xapian import QueryParser

from codex.settings.hypercorn import load_hypercorn_config
from codex.settings.logging import get_logger, init_logging
from codex.settings.secret_key import get_secret_key


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CODEX_PATH = BASE_DIR / "codex"
CONFIG_PATH = Path(os.environ.get("CODEX_CONFIG_DIR", Path.cwd() / "config"))
CONFIG_PATH.mkdir(exist_ok=True, parents=True)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = get_secret_key(CONFIG_PATH)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = bool(os.environ.get("DEBUG", False))
DEBUG_TOOLBAR = bool(os.environ.get("DEBUG_TOOLBAR", False))

#
# Logging
#
LOG_DIR = CONFIG_PATH / "logs"
init_logging(LOG_DIR, DEBUG)

LOG = get_logger(__name__)

ALLOWED_HOSTS = ["*"]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "haystack",
]

if DEBUG:
    # comes before static apps
    INSTALLED_APPS += ["livereload"]
    INSTALLED_APPS += ["nplusone.ext.django"]
    if DEBUG_TOOLBAR:
        INSTALLED_APPS += ["debug_toolbar"]

INSTALLED_APPS += [
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "codex",
    "dark",
]

MIDDLEWARE = [
    "django.middleware.cache.UpdateCacheMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "codex.middleware.TimezoneMiddleware",
    "django.middleware.cache.FetchFromCacheMiddleware",
]
if DEBUG:
    MIDDLEWARE += [
        "livereload.middleware.LiveReloadScript",
    ]
    if DEBUG_TOOLBAR:
        MIDDLEWARE += [
            "debug_toolbar.middleware.DebugToolbarMiddleware",
        ]
    MIDDLEWARE += ["nplusone.ext.django.NPlusOneMiddleware"]
    NPLUSONE_LOGGER = get_logger("nplusone")
    from logging import WARN

    NPLUSONE_LOG_LEVEL = WARN


ROOT_URLCONF = "codex.urls"

CODEX_TEMPLATES = CODEX_PATH / "templates"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [CODEX_TEMPLATES],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "codex.wsgi.application"


# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases

DB_PATH = CONFIG_PATH / "db.sqlite3"
BACKUP_DB_PATH = DB_PATH.with_suffix(DB_PATH.suffix + ".bak")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DB_PATH,
        "CONN_MAX_AGE": 600,
        "OPTIONS": {"timeout": 120},
    },
}
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
# The new DEFAULT_AUTO_FIELD in Django 3.2 is BigAutoField (64 bit),
#   but it can't be auto migrated. Automigration has been punted to
#   Django 4.0 at the earliest:
#   https://code.djangoproject.com/ticket/32674
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"


# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth."
        "password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 4},
    },
]


# Internationalization
# https://docs.djangoproject.com/en/dev/topics/i18n/
LANGUAGE_CODE = "en-us"
USE_I18N = True
USE_TZ = True
TZ = os.environ.get("TIMEZONE", os.environ.get("TZ"))
if TZ and not TZ.startswith(":") and "etc/localtime" not in TZ and "/" in TZ:
    TIME_ZONE = TZ
elif get_localzone_name():
    TIME_ZONE = get_localzone_name()
else:
    TIME_ZONE = "Etc/UTC"

# Hypercorn
HYPERCORN_CONFIG_TOML = CONFIG_PATH / "hypercorn.toml"
HYPERCORN_CONFIG_TOML_DEFAULT = CODEX_PATH / "settings/hypercorn.toml.default"
HYPERCORN_CONFIG, MAX_DB_OPS = load_hypercorn_config(
    HYPERCORN_CONFIG_TOML, HYPERCORN_CONFIG_TOML_DEFAULT, DEBUG
)
LOG.verbose(f"root_path: {HYPERCORN_CONFIG.root_path}")
PORT = int(HYPERCORN_CONFIG.bind[0].split(":")[1])

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/
# Keep missing-cover.webp around
WHITENOISE_KEEP_ONLY_HASHED_FILES = True
WHITENOISE_STATIC_PREFIX = "static/"
STATIC_ROOT = CODEX_PATH / "static_root"
if HYPERCORN_CONFIG.root_path:
    STATIC_URL = HYPERCORN_CONFIG.root_path + "/" + WHITENOISE_STATIC_PREFIX
else:
    STATIC_URL = WHITENOISE_STATIC_PREFIX
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
STATICFILES_DIRS = []
BUILD = os.environ.get("BUILD", False)
if DEBUG or BUILD:
    STATIC_SRC = CODEX_PATH / "static_src"
    STATIC_SRC.mkdir(exist_ok=True, parents=True)
    STATIC_BUILD = CODEX_PATH / "static_build"
    STATIC_BUILD.mkdir(exist_ok=True, parents=True)
    STATICFILES_DIRS += [
        STATIC_SRC,
        STATIC_BUILD,
    ]

SESSION_COOKIE_AGE = 60 * 60 * 24 * 60  # 60 days

# Setup support for proxy headers
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_RENDERER_CLASSES": (
        "djangorestframework_camel_case.render.CamelCaseJSONRenderer",
        "djangorestframework_camel_case.render.CamelCaseBrowsableAPIRenderer",
    ),
    "DEFAULT_PARSER_CLASSES": (
        "djangorestframework_camel_case.parser.CamelCaseFormParser",
        "djangorestframework_camel_case.parser.CamelCaseMultiPartParser",
        "djangorestframework_camel_case.parser.CamelCaseJSONParser",
    ),
}

CORS_ALLOW_CREDENTIALS = True

ROOT_CACHE_PATH = CONFIG_PATH / "cache"
DEFAULT_CACHE_PATH = ROOT_CACHE_PATH / "default"
DEFAULT_CACHE_PATH.mkdir(exist_ok=True, parents=True)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": str(DEFAULT_CACHE_PATH),
    },
}

INTERNAL_IPS = [
    "127.0.0.1",
]

XAPIAN_INDEX_PATH = CONFIG_PATH / "xapian_index"
XAPIAN_INDEX_PATH.mkdir(exist_ok=True, parents=True)
XAPIAN_INDEX_UUID_PATH = XAPIAN_INDEX_PATH / "codex_db.uuid"
_XAPIAN_FLAGS = (
    QueryParser.FLAG_BOOLEAN
    | QueryParser.FLAG_BOOLEAN_ANY_CASE
    | QueryParser.FLAG_PHRASE
    | QueryParser.FLAG_LOVEHATE
    | QueryParser.FLAG_WILDCARD
    | QueryParser.FLAG_PURE_NOT
)
HAYSTACK_CONNECTIONS = {
    "default": {
        "ENGINE": "codex.search_engine.CodexXapianSearchEngine",
        "PATH": str(XAPIAN_INDEX_PATH),
        "HAYSTACK_XAPIAN_FLAGS": _XAPIAN_FLAGS,
    },
}
