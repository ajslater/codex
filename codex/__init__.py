"""Initialize Django."""

from os import environ

from django import setup

from codex.cachalot_shim import install_cachalot_shim
from codex.signals.django_signals import connect_signals

if environ.get("PYTHONDEVMODE"):
    from icecream.builtins import install

    install()

# This all happens before anything else to make django safe to use.
environ.setdefault("DJANGO_SETTINGS_MODULE", "codex.settings")
setup()
install_cachalot_shim()
connect_signals()
