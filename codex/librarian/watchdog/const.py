"""Watchdog consts."""

import re
from types import MappingProxyType

from comicbox.box import Comicbox
from loguru import logger
from watchdog.events import (
    EVENT_TYPE_CREATED,
    EVENT_TYPE_DELETED,
    EVENT_TYPE_MODIFIED,
    DirDeletedEvent,
    DirModifiedEvent,
    DirMovedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEvent,
)

from codex.librarian.watchdog.events import (
    CodexPollEvent,
    CoverCreatedEvent,
    CoverDeletedEvent,
    CoverModifiedEvent,
    CoverMovedEvent,
)

#############
# Observers #
#############
EVENT_FILTER: tuple[type[FileSystemEvent], ...] = (
    # FileClosed,
    # FileClosedNoWriteEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    # FileSystemMovedEvent
    # FileOpenedEvent,
    # DirCreatedEvent,
    DirDeletedEvent,
    DirMovedEvent,
    DirModifiedEvent,
)

###########
# Emitter #
###########
ATTR_EVENT_MAP = MappingProxyType(
    {
        "files_deleted": FileDeletedEvent,
        "files_modified": FileModifiedEvent,
        "files_created": FileCreatedEvent,
        "files_moved": FileMovedEvent,
        "dirs_deleted": DirDeletedEvent,
        "dirs_modified": DirModifiedEvent,
        "dirs_moved": DirMovedEvent,
    }
)
DIR_NOT_FOUND_TIMEOUT = 15 * 60
POLLING_EVENT_FILTER: tuple[type[FileSystemEvent], ...] = (
    *EVENT_FILTER,
    CodexPollEvent,
)
DOCKER_UNMOUNTED_FN = "DOCKER_UNMOUNTED_VOLUME"

############
# Handlers #
############


def _get_comic_matcher():
    comic_regex = r"\.(cb[zt7"
    unsupported = []
    if Comicbox.is_unrar_supported():
        comic_regex += r"r"
    else:
        unsupported.append("CBR")
    comic_regex += r"]"

    if Comicbox.is_pdf_supported():
        comic_regex += r"|pdf"
    else:
        unsupported.append("PDF")
    comic_regex += ")$"
    if unsupported:
        un_str = ", ".join(unsupported)
        logger.warning(f"Cannot detect or read from {un_str} archives")
    return re.compile(comic_regex, re.IGNORECASE)


COMIC_MATCHER = _get_comic_matcher()
COVERS_EVENT_TYPE_MAP = MappingProxyType(
    {
        EVENT_TYPE_MODIFIED: CoverModifiedEvent,
        EVENT_TYPE_CREATED: CoverCreatedEvent,
        EVENT_TYPE_DELETED: CoverDeletedEvent,
    }
)


####################
# Event Aggregator #
####################
EVENT_CLASS_DIFF_ATTR_MAP = MappingProxyType(
    {
        FileDeletedEvent: "files_deleted",
        FileModifiedEvent: "files_modified",
        FileCreatedEvent: "files_created",
        DirDeletedEvent: "dirs_deleted",
        DirModifiedEvent: "dirs_modified",
    }
)
EVENT_MOVED_CLASS_DIFF_ATTR_MAP = MappingProxyType(
    {FileMovedEvent: "files_moved", DirMovedEvent: "dirs_moved"}
)
EVENT_COVERS_DIFF_ATTR_MAP = MappingProxyType(
    {
        CoverCreatedEvent: "covers_created",
        CoverDeletedEvent: "covers_deleted",
        CoverModifiedEvent: "covers_modified",
    }
)
EVENT_COVERS_MOVED_CLASS_DIFF_ATTR_MAP = MappingProxyType(
    {CoverMovedEvent: "covers_moved"}
)

EVENT_CLASS_DIFF_ALL_MAP: MappingProxyType[type[FileSystemEvent], str] = (
    MappingProxyType(
        {
            **EVENT_CLASS_DIFF_ATTR_MAP,
            **EVENT_MOVED_CLASS_DIFF_ATTR_MAP,
            **EVENT_COVERS_DIFF_ATTR_MAP,
            **EVENT_COVERS_MOVED_CLASS_DIFF_ATTR_MAP,
        }
    )
)
