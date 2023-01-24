"""Initialize Django."""
from os import environ

from django import setup

from codex.signals import connect_signals


# This all happens before anything else to make django safe to use.
environ.setdefault("DJANGO_SETTINGS_MODULE", "codex.settings.settings")
connect_signals()
setup()
