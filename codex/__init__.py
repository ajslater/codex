"""Initialize Django."""
import os

from codex.signals import connect_signals
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "codex.settings.settings")
connect_signals()
django.setup()
