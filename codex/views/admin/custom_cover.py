"""Custom cover upload / list / remove / delete endpoints."""

from __future__ import annotations

import os
import re
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from django.db import transaction
from loguru import logger
from PIL import Image, UnidentifiedImageError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from codex.librarian.covers.tasks import CoverCreateTask, CoverRemoveTask
from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.notifier.tasks import COVERS_CHANGED_TASK
from codex.librarian.scribe.importer.const import CLASS_CUSTOM_COVER_GROUP_MAP
from codex.models import CustomCover
from codex.serializers.admin.custom_cover import CustomCoverSerializer
from codex.settings import CUSTOM_COVERS_UPLOADS_DIR
from codex.settings.db import (
    get_custom_cover_max_upload_bytes,
    get_custom_cover_max_upload_mb,
)
from codex.views.admin.auth import AdminAPIView

if TYPE_CHECKING:
    from django.db.models import Model

_ALLOWED_EXTS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"})
_GROUP_CHAR_CHOICES = frozenset(c.value for c in CustomCover.GroupChoices)
_MODEL_BY_GROUP_CHAR: dict[str, type[Model]] = {
    char: model for model, char in CLASS_CUSTOM_COVER_GROUP_MAP.items()
}
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_MAX_SLUG_LEN = 60


def _slugify(name: str) -> str:
    """Filesystem-safe slug — lowercase ascii, hyphenated, truncated."""
    if not name:
        return ""
    return _SLUG_RE.sub("-", name.lower()).strip("-")[:_MAX_SLUG_LEN]


def _parse_pks(raw: str) -> tuple[int, ...]:
    if not raw:
        msg = "pks is required"
        raise ValidationError(msg)
    try:
        pks = tuple(int(p) for p in raw.split(",") if p.strip())
    except ValueError as exc:
        msg = f"invalid pks: {raw!r}"
        raise ValidationError(msg) from exc
    if not pks:
        msg = "pks is required"
        raise ValidationError(msg)
    return pks


def _validate_image(upload, ext: str) -> None:
    """Confirm the upload is a real image of an allowed type."""
    if ext not in _ALLOWED_EXTS:
        msg = f"Unsupported image type: {ext!r}"
        raise ValidationError(msg)
    if upload.size is None:
        msg = "Upload size unknown"
        raise ValidationError(msg)
    max_bytes = get_custom_cover_max_upload_bytes()
    if upload.size > max_bytes:
        msg = f"Upload exceeds {get_custom_cover_max_upload_mb()} MB limit"
        raise ValidationError(msg)
    head = upload.read()
    upload.seek(0)
    try:
        with Image.open(BytesIO(head)) as img:
            img.verify()
    except (OSError, UnidentifiedImageError) as exc:
        msg = "File is not a valid image"
        raise ValidationError(msg) from exc


def _resolve_targets(group_char: str, pks: tuple[int, ...]):
    model = _MODEL_BY_GROUP_CHAR.get(group_char)
    if model is None:
        msg = f"Unknown group {group_char!r}"
        raise ValidationError(msg)
    targets = list(model.objects.filter(pk__in=pks))
    if len(targets) != len(set(pks)):
        msg = f"Some {model.__name__} rows not found for pks={pks}"
        raise ValidationError(msg)
    return model, targets


def _sort_name_for(target) -> str:
    """Best-effort label for the new cover's sort_name field."""
    raw = getattr(target, "sort_name", None) or getattr(target, "name", None) or ""
    return str(raw)


def _delete_cover_files(cover: CustomCover) -> None:
    """Remove the source file from disk; thumb is purged by CoverRemoveTask."""
    if not cover.path:
        return
    path = Path(cover.path)
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning(f"Failed to unlink custom cover {path}: {exc}")


def _enqueue_thumb_purge(pks) -> None:
    pk_set = frozenset(pks)
    if not pk_set:
        return
    LIBRARIAN_QUEUE.put(CoverRemoveTask(pk_set, custom=True))


def _enqueue_thumb_create(pk: int) -> None:
    LIBRARIAN_QUEUE.put(CoverCreateTask((pk,), custom=True))


def _notify_covers_changed() -> None:
    """Broadcast a ``COVERS`` event so connected browsers refresh."""
    LIBRARIAN_QUEUE.put(COVERS_CHANGED_TASK)


def _swap_links(model, pks: tuple[int, ...], cover: CustomCover) -> tuple[int, ...]:
    """Point each target's ``custom_cover`` at ``cover``; return displaced cover pks."""
    displaced = tuple(
        model.objects.filter(pk__in=pks, custom_cover__isnull=False)
        .exclude(custom_cover_id=cover.pk)
        .values_list("custom_cover_id", flat=True)
        .distinct()
    )
    model.objects.filter(pk__in=pks).update(custom_cover=cover)
    return displaced


def _purge_orphaned(cover_pks: tuple[int, ...]) -> None:
    """Delete CustomCover rows + files that no group references."""
    for pk in cover_pks:
        try:
            cover = CustomCover.objects.get(pk=pk)
        except CustomCover.DoesNotExist:
            continue
        model = _MODEL_BY_GROUP_CHAR.get(cover.group)
        if model is None:
            continue
        if model.objects.filter(custom_cover_id=pk).exists():
            continue
        _delete_cover_files(cover)
        cover.delete()
        _enqueue_thumb_purge((pk,))


class AdminCustomCoverUploadView(AdminAPIView):
    """``POST`` a new custom cover for one or more groups."""

    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *_args, **_kwargs) -> Response:
        """Accept a multipart upload and link it to ``pks`` of ``group``."""
        group_char = request.data.get("group", "")
        if group_char not in _GROUP_CHAR_CHOICES:
            msg = f"Invalid group {group_char!r}"
            raise ValidationError(msg)
        pks = _parse_pks(request.data.get("pks", ""))
        upload = request.FILES.get("image")
        if upload is None:
            msg = "image file is required"
            raise ValidationError(msg)
        ext = Path(upload.name or "").suffix.lower()
        if ext == ".jpeg":
            ext = ".jpg"
        _validate_image(upload, ext)

        model, targets = _resolve_targets(group_char, pks)
        first = targets[0]
        sort_name = _sort_name_for(first)
        slug = _slugify(sort_name)

        with transaction.atomic():
            cover = CustomCover(
                library=None,
                path="",
                group=group_char,
                sort_name=sort_name,
            )
            # Save once to allocate a pk; presave wants ``path`` to stat
            # — write a placeholder file first.
            CUSTOM_COVERS_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
            placeholder = (
                CUSTOM_COVERS_UPLOADS_DIR / f"_pending-{os.getpid()}-{id(upload)}{ext}"
            )
            with placeholder.open("wb") as fh:
                for chunk in upload.chunks():
                    fh.write(chunk)
            cover.path = str(placeholder)
            cover.save()

            stem = f"{group_char}-{cover.pk}"
            if slug:
                stem = f"{stem}-{slug}"
            final_path = CUSTOM_COVERS_UPLOADS_DIR / f"{stem}{ext}"
            placeholder.replace(final_path)
            cover.path = str(final_path)
            cover.save(update_fields=["path", "stat"])

            displaced = _swap_links(model, pks, cover)

        _purge_orphaned(displaced)
        _enqueue_thumb_create(cover.pk)
        _notify_covers_changed()

        return Response(
            {"customCoverPk": cover.pk},
            status=status.HTTP_201_CREATED,
        )


class AdminCustomCoverRemoveView(AdminAPIView):
    """Unlink the custom cover from one or more groups, GC if orphaned."""

    def post(self, request, *_args, **_kwargs) -> Response:
        """Unlink the custom cover from each given group pk."""
        group_char = request.data.get("group", "")
        if group_char not in _GROUP_CHAR_CHOICES:
            msg = f"Invalid group {group_char!r}"
            raise ValidationError(msg)
        pks = _parse_pks(str(request.data.get("pks", "")))
        model, targets = _resolve_targets(group_char, pks)
        displaced = tuple(
            cover_id
            for cover_id in (getattr(t, "custom_cover_id", None) for t in targets)
            if cover_id is not None
        )
        with transaction.atomic():
            model.objects.filter(pk__in=pks).update(custom_cover=None)
        _purge_orphaned(tuple(set(displaced)))
        _notify_covers_changed()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminCustomCoverDeleteView(AdminAPIView):
    """Delete a single CustomCover row by pk, unlinking everything."""

    def delete(self, _request, pk: int, *_args, **_kwargs) -> Response:
        """Unlink, purge the cached thumb, and remove the row + source file."""
        try:
            cover = CustomCover.objects.get(pk=pk)
        except CustomCover.DoesNotExist as exc:
            msg = f"CustomCover {pk} not found"
            raise ValidationError(msg) from exc
        model = _MODEL_BY_GROUP_CHAR.get(cover.group)
        with transaction.atomic():
            if model is not None:
                model.objects.filter(custom_cover_id=pk).update(custom_cover=None)
            _delete_cover_files(cover)
            cover.delete()
        _enqueue_thumb_purge((pk,))
        _notify_covers_changed()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminCustomCoverListView(ListAPIView):
    """List every CustomCover row for the admin tab."""

    serializer_class = CustomCoverSerializer
    queryset = CustomCover.objects.all().order_by("group", "sort_name", "pk")

    permission_classes = AdminAPIView.permission_classes  # type: ignore[assignment]
