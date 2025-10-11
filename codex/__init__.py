"""Initialize Django."""

from os import environ

from django import setup

from codex.signals.django_signals import connect_signals

if environ.get("PYTHONDEVMODE"):
    from icecream.builtins import install

    install()

# This all happens before anything else to make django safe to use.
environ.setdefault("DJANGO_SETTINGS_MODULE", "codex.settings")
setup()
connect_signals()
