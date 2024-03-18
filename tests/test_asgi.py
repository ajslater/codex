"""Test the asgi server."""

from django.test import TestCase

from codex.asgi import application


class EnvironTestCase(TestCase):
    """Test environment variables."""

    def receive(self):
        """Do nothing."""

    def send(self):
        """Do nothing."""

    async def test_application(self):
        """Don't even test application, yet."""
        assert application
