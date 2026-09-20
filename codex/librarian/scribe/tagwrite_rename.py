"""
Predict where a tag write will leave each archive.

Renaming happens *before* the write, so the destination has to be known
in advance rather than read back off the finished file. Comicbox does the
predicting — the name it renders is exactly what ``rename_file`` would
use — but it has to be handed the same settings and pending patch the
write will apply, or the rename lands somewhere the write never agreed
to.

Whether the write also *converts* the archive is a separate question,
and the answer is the comic's stored ``file_type`` rather than its
suffix: comicbox decides from the archive's contents, so a CBZ misnamed
``.cbr`` is written in place.

The admin preflight preview derives its names through here too, so the
dialog cannot promise a name the rename won't produce.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from comicbox.box import Comicbox
from comicbox.config.settings import MergeMode

from codex.settings import COMICBOX_CONFIG

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping
    from pathlib import Path

#: Archive types comicbox repacks as a CBZ at a new path, which is what
#: makes a conversion a *move* rather than a modification. PDFs stay put
#: because codex never sets comicbox's ``convert.cbz``.
#:
#: These are ``Comic.file_type`` values, which the importer stores from
#: comicbox's own sniff of the archive's contents. Ask the row, not the
#: filename: a CBZ misnamed ``.cbr`` is written in place, and guessing
#: from the suffix mis-planned its rename.
CONVERTING_FILE_TYPES = frozenset({"CBR", "CBT", "CB7"})

#: Fallback for a row whose ``file_type`` is empty — nothing has read the
#: archive yet, so the name is the only evidence there is.
_WRITE_IN_PLACE_SUFFIXES = frozenset({".cbz", ".pdf"})

#: comicbox's conversion destination suffix.
_CBZ_SUFFIX = ".cbz"


@dataclass(frozen=True, slots=True)
class RenamePlan:
    """Where one comic's archive is headed."""

    pk: int
    old_path: Path
    #: The pre-write rename destination. Keeps the archive's current
    #: suffix: a CBR is still a CBR until the write repacks it.
    target: Path
    #: Where the file ends up once the write's conversion (if any) is
    #: done. Only differs from ``target`` for a converting archive.
    final_path: Path


def build_predict_config(delete_keys: Collection[str] | None, mode: str):
    """
    Return the config a write with these settings would parse under.

    Mirrors comicbox's own ``_build_write_settings``: the merge mode
    picks the merger that decides whether a patch value replaces or
    extends what the archive already holds, and cleared fields must
    vanish from the predicted name exactly as the write will clear them.
    """
    write = replace(COMICBOX_CONFIG.write, merge_mode=MergeMode(mode))
    keys = frozenset(
        key.removeprefix("comicbox.") for key in (delete_keys or ()) if key
    )
    if not keys:
        return replace(COMICBOX_CONFIG, write=write)
    general = replace(
        COMICBOX_CONFIG.general,
        delete_keys=COMICBOX_CONFIG.general.delete_keys | keys,
    )
    return replace(COMICBOX_CONFIG, write=write, general=general)


def predict_name(path: Path, patch: Mapping | None, config) -> str:
    """
    Return the scheme name a write carrying ``patch`` would rename to.

    Empty when no usable name could be built. Opens the archive.
    """
    metadata = {"comicbox": dict(patch)} if patch else None
    with Comicbox(path, config=config, metadata=metadata) as car:
        return car.predict_filename()


def will_convert(file_type: str, path: Path) -> bool:
    """
    Whether writing this archive repacks it as a CBZ at a new path.

    ``file_type`` is comicbox's sniff, recorded at import. Only when it
    is missing does the suffix get a say.
    """
    if file_type:
        return file_type.upper() in CONVERTING_FILE_TYPES
    return path.suffix.lower() not in _WRITE_IN_PLACE_SUFFIXES


def conversion_destination(path: Path) -> Path:
    """Where a converting write leaves this archive."""
    return path.with_suffix(_CBZ_SUFFIX)


def plan_rename(
    pk: int,
    old_path: Path,
    patch: Mapping | None,
    config,
    *,
    converts: bool,
) -> RenamePlan | None:
    """
    Build one comic's rename plan, or None when there is no name.

    ``converts`` is decided by the caller from the comic's stored
    ``file_type``. It used to be re-derived here from ``target``, a path
    that does not exist yet, which is doubly wrong: nothing can sniff a
    file that has not been written, and the suffix it guessed from was
    the predicted name's, not the archive's.
    """
    name = predict_name(old_path, patch, config)
    if not name:
        return None
    target = old_path.parent / name
    final_path = conversion_destination(target) if converts else target
    return RenamePlan(pk=pk, old_path=old_path, target=target, final_path=final_path)
