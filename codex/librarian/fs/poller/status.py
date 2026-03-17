"""Watcher Statii."""

from codex.librarian.fs.status import FSStatus


class FSPollStatus(FSStatus):
    """FS Poll Status."""

    CODE = "WPO"
    VERB = "Poll"
    _verbed = "Polled"
    ITEM_NAME = "library"
    SINGLE = True


FS_STATII = (FSPollStatus,)
