"""Test the asgi server."""
import os

from django.test import TestCase

import codex.asgi  # noqa F401


class EnvironTestCase(TestCase):
    """Test environment variables."""

    def test_env(self):
        """Test env vars."""
        assert os.environ.get("DJANGO_SETTINGS_MODULE") == "codex.settings"


# django-async-test could properly test application() but too much work
