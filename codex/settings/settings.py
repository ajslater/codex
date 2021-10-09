"""
Django settings for codex project.

Generated by 'django-admin startproject' using Django 3.0.3.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.0/ref/settings/
"""


import logging
import os

from pathlib import Path

from codex.settings.hypercorn import load_hypercorn_config
from codex.settings.logging import init_logging
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

#
# Logging
#
LOG_DIR = CONFIG_PATH / "logs"
init_logging(LOG_DIR, DEBUG)

LOG = logging.getLogger(__name__)

ALLOWED_HOSTS = ["*"]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
]

if DEBUG:
    # comes before static apps
    INSTALLED_APPS += ["livereload", "debug_toolbar"]

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
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    ]


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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DB_PATH,
        "CONN_MAX_AGE": 600,
        "OPTIONS": {"timeout": 120},
    },
}
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"


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
# https://docs.djangoproject.com/en/3.0/topics/i18n/
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Hypercorn
HYPERCORN_CONFIG_TOML = CONFIG_PATH / "hypercorn.toml"
HYPERCORN_CONFIG_TOML_DEFAULT = CODEX_PATH / "settings/hypercorn.toml.default"
HYPERCORN_CONFIG = load_hypercorn_config(
    HYPERCORN_CONFIG_TOML, HYPERCORN_CONFIG_TOML_DEFAULT, DEBUG
)
ROOT_PATH = ""
PORT = int(HYPERCORN_CONFIG.bind[0].split(":")[1])

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/
CONFIG_STATIC = CONFIG_PATH / "static"
CONFIG_STATIC.mkdir(exist_ok=True, parents=True)
# XXX Abuse the Whitenoise ROOT feature to serve covers
# A little dangerous because whitenoise will serve anything from that
# static directory. But it sure is fast.
WHITENOISE_ROOT = CONFIG_STATIC
WHITENOISE_KEEP_ONLY_HASHED_FILES = True
WHITENOISE_STATIC_PREFIX = "static/"
# XXX Attempt to fix new covers not displaying bug
#     Bad for performance and security
# http://whitenoise.evans.io/en/stable/django.html#WHITENOISE_AUTOREFRESH
WHITENOISE_AUTOREFRESH = True
STATIC_ROOT = CODEX_PATH / "static_root"
STATIC_URL = ROOT_PATH + WHITENOISE_STATIC_PREFIX
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
if DEBUG:
    STATIC_SRC = CODEX_PATH / "static_src"
    STATIC_SRC.mkdir(exist_ok=True, parents=True)
    STATIC_BUILD = CODEX_PATH / "static_build"
    STATIC_BUILD.mkdir(exist_ok=True, parents=True)
    STATICFILES_DIRS = (
        STATIC_SRC,
        STATIC_BUILD,
    )

SESSION_COOKIE_AGE = 60 * 60 * 24 * 60  # 60 days

# Setup support for proxy headers
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
    ),
}

CORS_ALLOW_CREDENTIALS = True

CACHE_PATH = CONFIG_PATH / "cache"
CACHE_PATH.mkdir(exist_ok=True, parents=True)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": str(CACHE_PATH),
    }
}

INTERNAL_IPS = [
    "127.0.0.1",
]
