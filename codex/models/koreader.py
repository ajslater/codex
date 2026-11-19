"""KOReader sync document hashes, kept beside Comic rather than on it."""

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Final, override

from django.db.models import CASCADE, CharField, Model, OneToOneField

from codex.librarian.scribe.koreader_hash import (
    koreader_name_md5,
    koreader_partial_md5,
)
from codex.models.comic import Comic

__all__ = ("ComicKoreaderHash",)

HASH_FIELDS: Final = ("binary_hash", "name_hash")


class ComicKoreaderHash(Model):
    """
    A comic's KOReader kosync document ids.

    ``binary_hash`` is KOReader's ``util.partialMD5`` of the file and
    ``name_hash`` the MD5 of its base name (see
    :mod:`codex.librarian.scribe.koreader_hash`). The binary hash reads the
    file, so imports take it only while KOReader Sync is on; it is null until
    the backfill job fills it. A comic with no row has neither.

    One row per comic, keyed by it and deleted with it. The reverse relation
    is hidden, so the hashes never join the "every Comic field" registries:
    serializers, metadata, search and the importer's field lists.
    """

    comic = OneToOneField(Comic, on_delete=CASCADE, primary_key=True, related_name="+")
    binary_hash = CharField(db_index=True, max_length=32, null=True)  # noqa: DJ001
    name_hash = CharField(db_index=True, max_length=32, null=True)  # noqa: DJ001

    class Meta:
        """Admin name."""

        verbose_name = "comic KOReader hash"

    @override
    def __str__(self) -> str:
        """Name the row by its comic, never by its hashes."""
        return f"KOReader hashes of comic {self.pk}"

    @staticmethod
    def compute(
        comic_id: int, path: str | Path, *, binary: bool
    ) -> "ComicKoreaderHash":
        """
        Return an unsaved row of the hashes of the file at ``path``.

        The name hash needs no disk access and is always set. Without
        ``binary``, or for a file that can't be read, the binary hash is
        null for the backfill to fill once the flag is on.
        """
        binary_hash = None
        if binary:
            try:
                binary_hash = koreader_partial_md5(path)
            except OSError:
                binary_hash = None
        return ComicKoreaderHash(
            comic_id=comic_id,
            binary_hash=binary_hash,
            name_hash=koreader_name_md5(path),
        )

    @staticmethod
    def upsert(
        rows: Iterable["ComicKoreaderHash"], fields: Sequence[str] = HASH_FIELDS
    ) -> None:
        """Insert ``rows``, or set ``fields`` where a comic already has one."""
        objs = tuple(rows)
        if not objs:
            return
        ComicKoreaderHash.objects.bulk_create(
            objs,
            update_conflicts=True,
            unique_fields=("comic",),
            update_fields=fields,
        )
