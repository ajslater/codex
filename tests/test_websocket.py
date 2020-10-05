"""Test websockets."""
from codex.websocket_server import get_send_msg


def test_get_send_msg():
    """Test the get_send_msg method."""
    msg = get_send_msg("hello")
    assert msg == {"type": "websocket.send", "text": "hello"}
