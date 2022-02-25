"""Aggregate metadata from comics to prepare for importing."""

import decimal
import time

from logging import getLogger
from pathlib import Path
from zipfile import BadZipFile

from comicbox.comic_archive import ComicArchive
from comicbox.exceptions import UnsupportedArchiveTypeError
from rarfile import BadRarFile

from codex.librarian.queue_mp import LIBRARIAN_QUEUE, ImageComicCoverCreateTask
from codex.models import Comic, Imprint, Publisher, Series, Volume
from codex.settings.logging import LOG_EVERY


LOG = getLogger(__name__)
BROWSER_GROUPS = (Publisher, Imprint, Series, Volume)
BROWSER_GROUP_TREE_COUNT_FIELDS = set(["volume_count", "issue_count"])
COMIC_M2M_FIELDS = set()
for field in Comic._meta.get_fields():
    if field.many_to_many and field.name != "folders":
        COMIC_M2M_FIELDS.add(field.name)
WRITE_WAIT_EXPIRY = LOG_EVERY
WRITE_WAIT_DELAY = 0.01
_MD_INVALID_KEYS = set(
    [
        "created_at",
        "id",
        "library",
        "parent_folder",
        "pk",
        "stat",
        "title",
        "updated_at",
    ]
)
_MD_VALID_KEYS = (
    set([field.name for field in Comic._meta.get_fields()]) - _MD_INVALID_KEYS
)
_MD_DECIMAL_KEYS = set(("issue", "issue_count", "community_rating", "critical_rating"))
_DECIMAL_MAX = decimal.Decimal(99.99)
_DECIMAL_MIN = decimal.Decimal(0.0)
_TWO_PLACES = decimal.Decimal("0.01")


def _clean_md(md):
    """Clean metadata before importing."""
    # remove unused keys.
    md_keys = set(md.keys())
    unused_keys = md_keys - _MD_VALID_KEYS
    for key in unused_keys:
        del md[key]
    md_keys = set(md.keys())

    # fix ranges of decimals
    decimal_keys = md_keys & _MD_DECIMAL_KEYS
    for key in decimal_keys:
        val = md[key]
        try:
            val = max(min(val, _DECIMAL_MAX), _DECIMAL_MIN)
            val = val.quantize(_TWO_PLACES)
            md[key] = val
        except Exception:
            LOG.warning(f"Failed cleaning metadata {key} = {val}")
            del md[key]


def _wait_for_copy(path):
    """
    Wait for a file to stay the same size.

    Watchdog events fire on the start of the copy. On slow or network
    filesystems, this sends an event before the file is finished
    copying.
    """
    started_waiting = time.time()
    old_size = -1
    path = Path(path)
    while old_size != path.stat().st_size:
        if time.time() - started_waiting > WRITE_WAIT_EXPIRY:
            raise ValueError("waited for copy too long")
        old_size = path.stat().st_size
        time.sleep(WRITE_WAIT_DELAY)


def _get_path_metadata(path):
    """Get the metatada from comicbox and munge it a little."""
    md = {}
    m2m_md = {}
    group_tree_md = {}
    failed_import = {}

    try:
        _wait_for_copy(path)
        car = ComicArchive(path, get_cover=True)
        md = car.get_metadata()
        md["path"] = path
        md["size"] = Path(path).stat().st_size
        title = md.get("title")
        if title:
            md["name"] = title[:31]
        if not md.get("summary") and md.get("description"):
            # CoMet to cix copy
            md["summary"] = md.pop("description")
        md["max_page"] = max(md["page_count"] - 1, 0)
        if credits := md.get("credits"):
            for credit in credits:
                if credit.get("role") == "CoverArtist":
                    credit["role"] = "Cover Artist"
        # Getting the cover data while getting the metada and handing to the
        # other thread is significantly faster than doing it later.
        # Updated the dabbase with cover_path
        if car.cover_image_data:
            task = ImageComicCoverCreateTask(True, path, car.cover_image_data)
            LIBRARIAN_QUEUE.put_nowait(task)
        _clean_md(md)
        group_tree = []
        for group_cls in BROWSER_GROUPS:
            group_field = group_cls.__name__.lower()
            # some volumes are read by ComicArchive as ints, cast
            group_name = str(md.get(group_field, Publisher.DEFAULT_NAME))
            # This fixes no imprint or whatever being in md
            md[group_field] = group_name
            group_tree.append(group_name)

        groups_md = {}
        md_group_count_fields = BROWSER_GROUP_TREE_COUNT_FIELDS & md.keys()
        for key in md_group_count_fields:
            groups_md[key] = md.pop(key)

        group_tree_md[tuple(group_tree)] = groups_md

        # many_to_many fields get moved into a separate dict
        md_m2m_fields = COMIC_M2M_FIELDS & md.keys()
        for field in md_m2m_fields:
            m2m_md[field] = md.pop(field)
        m2m_md["folders"] = Path(path).parents
    except (UnsupportedArchiveTypeError, BadRarFile, BadZipFile, OSError) as exc:
        LOG.warning(f"Failed to import {path}: {exc}")
        failed_import = {path: exc}
    except Exception as exc:
        LOG.warning(f"Failed to import: {path}")
        LOG.exception(exc)
        failed_import = {path: exc}
    return md, m2m_md, group_tree_md, failed_import


def _none_max(a, b):
    """math.max but None aware."""
    # For determining groups counts.
    # might be better to do most-common number, not max
    # but would need access to all counts every import but
    # I don't store them in the comic table
    if a is not None and b is not None:
        return max(a, b)
    if a is None:
        return b
    if b is None:
        return a


def _aggregate_m2m_metadata(all_m2m_mds, m2m_md, all_fks, path):
    """Aggregate many to many metadata by ."""
    # m2m fields and fks
    all_m2m_mds[path] = m2m_md
    # aggregate fks
    for field, names in m2m_md.items():
        if field == "credits":
            if names and "credits" not in all_fks:
                all_fks["credits"] = set()

            # for credits add the credit fks to fks
            for credit_dict in names:
                for field, name in credit_dict.items():
                    # These fields are ambiguous because they're fks to Credit
                    #   but aren't ever in Comic so query_fks.py can
                    #   disambiguate with special code
                    if field not in all_fks:
                        all_fks[field] = set()
                    all_fks[field].add(name)
                credit_tuple = tuple(sorted(credit_dict.items()))
                all_fks["credits"].add(credit_tuple)
        elif field != "folders":
            if field not in all_fks:
                all_fks[field] = set()
            all_fks[field] |= set(names)


def _aggregate_group_tree_metadata(all_fks, group_tree_md):
    """Aggregate group tree data by class."""
    for group_tree, group_md in group_tree_md.items():
        all_fks["group_trees"][Publisher][group_tree[0:1]] = None
        all_fks["group_trees"][Imprint][group_tree[0:2]] = None

        series_group_tree = group_tree[0:3]
        volume_count = _none_max(
            all_fks["group_trees"][Series].get(series_group_tree),
            group_md.get("volume_count"),
        )
        all_fks["group_trees"][Series][series_group_tree] = volume_count
        volume_group_tree = group_tree[0:4]
        issue_count = _none_max(
            all_fks["group_trees"][Volume].get(volume_group_tree),
            group_md.get("issue_count"),
        )
        all_fks["group_trees"][Volume][volume_group_tree] = issue_count


def get_aggregate_metadata(library, all_paths):
    """Get aggregated metatada for the paths given."""
    all_mds = {}
    all_m2m_mds = {}
    all_fks = {
        "group_trees": {Publisher: {}, Imprint: {}, Series: {}, Volume: {}},
        "comic_paths": set(),
    }
    all_failed_imports = {}
    total_paths = len(all_paths)

    LOG.info(f"Reading tags from {total_paths} comics in {library.path}...")
    last_log_time = time.time()
    for num, path in enumerate(all_paths):
        path = str(path)
        md, m2m_md, group_tree_md, failed_import = _get_path_metadata(path)

        if failed_import:
            all_failed_imports.update(failed_import)
        else:
            if md:
                all_mds[path] = md

            if m2m_md:
                _aggregate_m2m_metadata(all_m2m_mds, m2m_md, all_fks, path)

            if group_tree_md:
                _aggregate_group_tree_metadata(all_fks, group_tree_md)

        now = time.time()
        if now - last_log_time > LOG_EVERY:
            LOG.info(f"Read tags from {num}/{total_paths} comics")
            last_log_time = now

    all_fks["comic_paths"] = set(all_mds.keys())

    LOG.verbose(f"Aggregated tags from {len(all_mds)} comics.")  # type: ignore
    return all_mds, all_m2m_mds, all_fks, all_failed_imports
