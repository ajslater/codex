"""Test websockets."""
from codex.websocket_server import send_msg


async def send(self, msg):
    """Send dummy message."""
    global KEYS
    print(self.key, msg)
    KEYS.add(self.key, self.msg)


KEYS = set()
COMPARE_KEYS = set(["hello"])
CONNS = set([send, send])


async def test_get_send_msg():
    """Test the get_send_msg method."""
    global CONNS, KEYS
    KEYS = set()
    await send_msg(CONNS, "hello")
    assert KEYS == COMPARE_KEYS
