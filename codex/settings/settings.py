"""Django settings for codex project.

Generated by 'django-admin startproject' using Django 3.0.3.

For more information on this file, see
https://docs.djangoproject.com/en/dev/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/dev/ref/settings/
"""
from os import environ
from pathlib import Path
from sys import maxsize

from codex.settings.hypercorn import load_hypercorn_config
from codex.settings.logging import get_loglevel
from codex.settings.secret_key import get_secret_key
from codex.settings.timezone import get_time_zone
from codex.settings.whitenoise import immutable_file_test

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CODEX_PATH = BASE_DIR / "codex"
CONFIG_PATH = Path(environ.get("CODEX_CONFIG_DIR", Path.cwd() / "config"))
CONFIG_PATH.mkdir(exist_ok=True, parents=True)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = get_secret_key(CONFIG_PATH)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = bool(environ.get("DEBUG", "").lower() not in ("0", "false", ""))

RESET_ADMIN = bool(environ.get("CODEX_RESET_ADMIN"))
SKIP_INTEGRITY_CHECK = bool(environ.get("CODEX_SKIP_INTEGRITY_CHECK"))

# Logging
LOGLEVEL = get_loglevel(DEBUG)
LOG_DIR = Path(environ.get("CODEX_LOG_DIR", CONFIG_PATH / "logs"))
LOG_TO_CONSOLE = environ.get("CODEX_LOG_TO_CONSOLE") != "0"
LOG_TO_FILE = environ.get("CODEX_LOG_TO_FILE") != "0"
if not DEBUG:
    LOGGING = {
        "version": 1,
        "loggers": {
            "asyncio": {
                "level": "INFO",
            },
            "watchdog": {
                "level": "INFO",
            },
            "PIL": {
                "level": "INFO",
            },
        },
    }

ALLOWED_HOSTS = ["*"]


# Application definition

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "haystack",
]

if DEBUG:
    # comes before static apps
    INSTALLED_APPS += ["nplusone.ext.django"]

INSTALLED_APPS += [
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_registration",
    "corsheaders",
    "django_vite",
    "codex",
    "drf_spectacular",
]

MIDDLEWARE = [
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
]
if DEBUG:
    from logging import WARN, getLogger

    MIDDLEWARE += ["nplusone.ext.django.NPlusOneMiddleware"]
    NPLUSONE_LOGGER = getLogger("nplusone")
    NPLUSONE_LOG_LEVEL = WARN


ROOT_URLCONF = "codex.urls.root"

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
BACKUP_DB_DIR = CONFIG_PATH / "backups"
BACKUP_DB_PATH = (BACKUP_DB_DIR / DB_PATH.stem).with_suffix(DB_PATH.suffix + ".bak")

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
TZ = environ.get("TIMEZONE", environ.get("TZ"))
TIME_ZONE = get_time_zone(TZ)

# Hypercorn
HYPERCORN_CONFIG_TOML = CONFIG_PATH / "hypercorn.toml"
HYPERCORN_CONFIG_TOML_DEFAULT = CODEX_PATH / "settings/hypercorn.toml.default"
HYPERCORN_CONFIG = load_hypercorn_config(
    HYPERCORN_CONFIG_TOML, HYPERCORN_CONFIG_TOML_DEFAULT, DEBUG
)
PORT = int(HYPERCORN_CONFIG.bind[0].split(":")[1])


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/dev/howto/static-files/
# WHITENOISE_KEEP_ONLY_HASHED_FILES is not usable with vite chunking
WHITENOISE_STATIC_PREFIX = "static/"
WHITENOISE_IMMUTABLE_FILE_TEST = immutable_file_test
STATIC_ROOT = CODEX_PATH / "static_root"
if HYPERCORN_CONFIG.root_path:
    STATIC_URL = HYPERCORN_CONFIG.root_path + "/" + WHITENOISE_STATIC_PREFIX
else:
    STATIC_URL = WHITENOISE_STATIC_PREFIX
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    }
}
STATICFILES_DIRS = []
BUILD = environ.get("BUILD", False)
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
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "codex.views.error.codex_exception_handler",
}

REST_REGISTRATION = {
    "REGISTER_VERIFICATION_ENABLED": False,
    "REGISTER_EMAIL_VERIFICATION_ENABLED": False,
    "RESET_PASSWORD_VERIFICATION_ENABLED": False,
    "USER_HIDDEN_FIELDS": (
        # DEFAULT
        "last_login",
        "is_active",
        "user_permissions",
        "groups",
        "date_joined",
        # SHOWN
        # "is_staff", "is_superuser",
        # HIDDEN
        "email",
        "first_name",
        "last_name",
    ),
}


SPECTACULAR_SETTINGS = {
    "TITLE": "Codex API",
    "DESCRIPTION": "Comic Library Browser and Reader",
    "VERSION": "3.0.0",
    "CONTACT": {"name": "Repository", "url": "https://github.com/ajslater/codex/"},
    "PREPROCESSING_HOOKS": ["codex.urls.spectacular.allow_list"],
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

SEARCH_INDEX_PATH = CONFIG_PATH / "whoosh_index"
SEARCH_INDEX_PATH.mkdir(exist_ok=True, parents=True)
SEARCH_INDEX_UUID_PATH = SEARCH_INDEX_PATH / "codex_db.uuid"
HAYSTACK_CONNECTIONS = {
    "default": {
        "ENGINE": "codex.search.engine.CodexSearchEngine",
        "PATH": str(SEARCH_INDEX_PATH),
        "BATCH_SIZE": maxsize,  # use whoosh multiprocessing not haystack's
    },
}
HAYSTACK_LOGGING = False
# Search indexing memory controls
MMAP_RATIO = int(environ.get("MMAP_RATIO", 320))
WRITER_MEMORY_PERCENT = float(environ.get("WRITER_MEMORY_PERCENT", 0.8))
CPU_MULTIPLIER = float(environ.get("CPU_MULTIPLIER", 1.5))
CHUNK_PER_GB = int(environ.get("CHUNK_PER_GB", 250))
MAX_CHUNK_SIZE = int(environ.get("MAX_CHUNK_SIZE", 1000))

CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
}

DJANGO_VITE_DEV_MODE = DEBUG
if DEBUG:
    import socket

    DJANGO_VITE_ASSETS_PATH = STATIC_BUILD  # type: ignore
    DJANGO_VITE_DEV_SERVER_HOST = environ.get("VITE_HOST", socket.gethostname())
    DJANGO_VITE_DEV_SERVER_PORT = 5173
else:
    DJANGO_VITE_ASSETS_PATH = STATIC_ROOT
