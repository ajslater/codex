"""Poller handlers (snapshot diff: has moved events, dirs, full classification)."""

from dataclasses import dataclass
from enum import IntEnum


class PollEventType(IntEnum):
    """Poll evenv type."""

    start = 1
    finish = 2


@dataclass(frozen=True, slots=True)
class PollEvent:
    """Signal the event batcher about poll boundaries."""

    poll_type: PollEventType
    force: bool = False
