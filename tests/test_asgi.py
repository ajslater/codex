import os

from django.test import TestCase

import codex.asgi  # noqa F401


class EnvironTestCase(TestCase):
    def test_env(self):
        assert os.environ.get("DJANGO_SETTINGS_MODULE") == "codex.settings"


# django-async-test could properly test application() but too much work
