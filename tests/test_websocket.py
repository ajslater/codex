"""Test websockets."""
import pytest

from codex.notifier.notifierd import Notifier


pytestmark = pytest.mark.asyncio

KEYS = set()


class Sender:
    """Dummy asycnio sender."""

    async def send(self, msg):
        """Send dummy message."""
        global KEYS
        KEYS.add(str(msg))


class TestWebsockets:
    """Test websockets."""

    COMPARE_KEYS = set(["hello"])

    async def test_get_send_msg(self):
        """Test the get_send_msg method."""
        global KEYS
        sender = Sender()
        conns = set([sender.send, sender.send])
        KEYS = set()
        await Notifier._send_msg(conns, "hello")
        assert KEYS == self.COMPARE_KEYS
