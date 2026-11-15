"""
KOReader kosync progress endpoints.

``document`` is a KOReader hash: the partial MD5 of the file or, for devices
set to Filename matching, the MD5 of its base name. Either matches.

For comics and PDFs KOReader's ``progress`` is the 1-based page number as a
string and ``percentage`` is ``page / page_count``. Codex bookmarks store a
0-based page.

A device queues any failed push that isn't a 401 and retries it for weeks,
so a push for a book that is unknown, or that the user may not see, gets the
same 200 as a stored one, and stores nothing. A pull for one answers ``{}``,
which KOReader reads as "no progress". The two cases are indistinguishable.
"""

import math
import re
import time
from collections.abc import Mapping
from http import HTTPStatus
from typing import Final

from django.db.models import Q
from rest_framework.response import Response

from codex.librarian.bookmark.update import BookmarkUpdateMixin
from codex.models import Bookmark, Comic
from codex.views.auth import GroupACLMixin
from codex.views.koreader.base import (
    ERROR_DOCUMENT_FIELD_MISSING,
    ERROR_INVALID_FIELDS,
    KOSyncAPIView,
    kosync_error,
)

# Pulls report Codex itself as the last device, under a fixed id so
# KOReader never mistakes it for one of its own.
CODEX_DEVICE: Final = "Codex"
CODEX_DEVICE_ID: Final = "00000000000000000000000000c0de00"
_HASH_RE: Final = re.compile(r"^[0-9a-f]{32}$")
_PERCENT_DIGITS: Final = 4


def normalize_document(document) -> str | None:
    """Return a lowercase hash, or None if this can't be one of ours."""
    if not isinstance(document, str):
        return None
    document = document.strip().lower()
    return document if _HASH_RE.match(document) else None


def _parse_page(progress) -> int | None:
    """Parse KOReader's 1-based page string. EPUB xpointers aren't pages."""
    if isinstance(progress, bool):
        return None
    if isinstance(progress, int):
        return progress
    if isinstance(progress, str):
        try:
            return int(progress.strip())
        except ValueError:
            return None
    return None


def _parse_percentage(percentage) -> float | None:
    """Parse a 0..1 percentage."""
    if isinstance(percentage, bool) or not isinstance(percentage, int | float | str):
        return None
    try:
        value = float(percentage)
    except ValueError:
        return None
    if math.isnan(value) or not 0 <= value <= 1:
        return None
    return value


def map_push(progress, percentage, page_count: int) -> tuple[int, bool] | None:
    """
    Map a pushed position to ``(0-based page, finished)``.

    The device's page is used when it agrees with Codex about how many pages
    the book has. If ``progress`` isn't a page number, or the page count the
    device implies (``progress / percentage``) differs from Codex's, the
    position is taken from ``percentage`` instead. Returns None when neither
    can be read.
    """
    device_page = _parse_page(progress)
    fraction = _parse_percentage(percentage)
    if page_count <= 0:
        # Codex hasn't counted the pages yet: keep the device's page as is.
        if device_page is None:
            return None
        return max(device_page - 1, 0), False
    if device_page is not None and fraction:
        implied_page_count = round(device_page / fraction)
        if implied_page_count != page_count:
            device_page = None
    if device_page is None:
        if fraction is None:
            return None
        device_page = max(round(fraction * page_count), 1)
    finished = device_page >= page_count
    page = min(max(device_page - 1, 0), page_count - 1)
    return page, finished


def pull_document(document: str, page: int, page_count: int, updated_at) -> dict:
    """Build the kosync progress document for a stored bookmark."""
    device_page = page + 1
    percentage = (
        math.floor(device_page / page_count * 10**_PERCENT_DIGITS) / 10**_PERCENT_DIGITS
        if page_count > 0
        else 0.0
    )
    return {
        "document": document,
        "percentage": min(percentage, 1.0),
        "progress": str(device_page),
        "device": CODEX_DEVICE,
        "device_id": CODEX_DEVICE_ID,
        "timestamp": int(updated_at.timestamp()),
    }


class KOSyncProgressMixin(GroupACLMixin):
    """Find the comics a KOReader document hash names."""

    def get_matching_comics(self, document: str, *, include_missing: bool):
        """
        Return ``(pk, page_count)`` for every visible comic with this hash.

        Through the library-group and age-rating ACL, so a comic the user
        cannot browse never matches.
        """
        user = self.request.user
        acl_filter = self.get_acl_filter(Comic, user, include_missing=include_missing)
        hash_filter = Q(koreader_hash=document) | Q(koreader_name_hash=document)
        return tuple(
            Comic.objects.filter(acl_filter, hash_filter).values_list(
                "pk", "page_count"
            )
        )


class KOSyncProgressPutView(KOSyncProgressMixin, KOSyncAPIView):
    """``PUT syncs/progress``: store a device's position."""

    def __init__(self, *args, **kwargs) -> None:
        """Init the ACL cache."""
        super().__init__(*args, **kwargs)
        self.init_group_acl()

    def _store(self, comics, data: Mapping) -> int | None:
        """Write the position to every matching comic; return its timestamp."""
        auth_filter = {"user_id": self.request.user.pk}
        stored_pks = []
        for pk, page_count in comics:
            mapped = map_push(data.get("progress"), data.get("percentage"), page_count)
            if mapped is None:
                continue
            page, finished = mapped
            # Only ever set finished, as the web reader does: an earlier
            # page on a finished book is a re-read, not "mark unread".
            updates: dict = {"page": page}
            if finished:
                updates["finished"] = True
            BookmarkUpdateMixin.update_bookmarks(auth_filter, (pk,), updates)
            stored_pks.append(pk)
        if not stored_pks:
            return None
        updated_at = (
            Bookmark.objects.filter(**auth_filter, comic_id__in=stored_pks)
            .order_by("-updated_at")
            .values_list("updated_at", flat=True)
            .first()
        )
        return int(updated_at.timestamp()) if updated_at else None

    def put(self, *_args, **_kwargs) -> Response:
        """Store the position; unknown and forbidden books store nothing."""
        data = self.request.data
        # A JSON body can be a list or a scalar, whatever the stubs say.
        if not isinstance(data, Mapping):  # pyright: ignore[reportUnnecessaryIsInstance]
            return kosync_error(
                HTTPStatus.BAD_REQUEST, ERROR_INVALID_FIELDS, "Invalid request"
            )
        raw_document = data.get("document")
        if not raw_document or not isinstance(raw_document, str):
            return kosync_error(
                HTTPStatus.BAD_REQUEST,
                ERROR_DOCUMENT_FIELD_MISSING,
                "Field 'document' not provided.",
            )
        timestamp = None
        if document := normalize_document(raw_document):
            # Writes land on comics whose file is briefly missing, as the
            # web reader's and OPDS progression's do.
            comics = self.get_matching_comics(document, include_missing=True)
            timestamp = self._store(comics, data)
        if timestamp is None:
            timestamp = int(time.time())
        return Response({"document": raw_document, "timestamp": timestamp})


class KOSyncProgressGetView(KOSyncProgressMixin, KOSyncAPIView):
    """``GET syncs/progress/<document>``: the stored position, or ``{}``."""

    def __init__(self, *args, **kwargs) -> None:
        """Init the ACL cache."""
        super().__init__(*args, **kwargs)
        self.init_group_acl()

    def get(self, *_args, **_kwargs) -> Response:
        """Return the most recently updated matching bookmark."""
        raw_document = self.kwargs.get("document", "")
        document = normalize_document(raw_document)
        if not document:
            return Response({})
        comics = dict(self.get_matching_comics(document, include_missing=False))
        if not comics:
            return Response({})
        bookmark = (
            Bookmark.objects.filter(user_id=self.request.user.pk, comic_id__in=comics)
            .order_by("-updated_at")
            .values_list("comic_id", "page", "finished", "updated_at")
            .first()
        )
        if not bookmark:
            return Response({})
        comic_pk, page, finished, updated_at = bookmark
        page_count = comics[comic_pk] or 0
        if finished and not page:
            # Marked read without opening: report the last page.
            page = max(page_count - 1, 0)
        elif not page:
            # page 0 and unfinished reads the same as no bookmark in Codex.
            return Response({})
        return Response(pull_document(raw_document, page, page_count, updated_at))
