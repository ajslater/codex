"""Test websockets."""
import pytest

from codex.websocket_server import send_msg


pytestmark = pytest.mark.asyncio

KEYS = set()


class Sender:
    """Dummy asycnio sender."""

    async def send(self, msg):
        """Send dummy message."""
        global KEYS
        print(msg)
        KEYS.add(str(msg))


class TestWebsockets:
    """Test websockets."""

    HELLO_MSG = "{'text': 'hello', 'type': 'websocket.send'}"
    COMPARE_KEYS = set([HELLO_MSG])

    async def test_get_send_msg(self):
        """Test the get_send_msg method."""
        global KEYS
        sender = Sender()
        conns = set([sender.send, sender.send])
        KEYS = set()
        await send_msg(conns, "hello")
        assert KEYS == self.COMPARE_KEYS
