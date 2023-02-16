"""Test websockets."""
import pytest

from codex.django_channels.consumers import ChannelGroups
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.notifierd import NotifierThread
from codex.librarian.notifier.tasks import NotifierTask
from codex.logger.mp_queue import LOG_QUEUE


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
        KEYS = set()
        notifier = NotifierThread(LOG_QUEUE, LIBRARIAN_QUEUE)
        notifier.queue.put(NotifierTask("hello", ChannelGroups.ALL))
        notifier.send_all_items()
        assert KEYS == self.COMPARE_KEYS
