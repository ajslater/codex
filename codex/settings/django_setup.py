"""Set up Django for independent processes."""
import os

import django

from django.apps import apps


def django_setup():
    """Set up django (if it hasn't already been done) for logging."""
    if not apps.ready:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "codex.settings.settings")
        django.setup()
