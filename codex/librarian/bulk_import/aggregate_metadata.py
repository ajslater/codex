"""
Aggregate metadata from comics to prepare for importing.
"""

import logging

from pathlib import Path

from comicbox.comic_archive import ComicArchive

from codex.librarian.bulk_import import BROWSER_GROUPS
from codex.librarian.cover import get_cover_path
from codex.librarian.queue_mp import QUEUE, ComicCoverCreateTask
from codex.models import Comic, FailedImport


LOG = logging.getLogger(__name__)
BROWSER_GROUP_TREE_COUNT_FIELDS = set(["volume_count", "issue_count"])
COMIC_M2M_FIELDS = set()
for field in Comic._meta.get_fields():
    if field.many_to_many and field.name != "folder":
        COMIC_M2M_FIELDS.add(field.name)
MD_UNUSED_KEYS = ("remainder", "ext", "pages", "cover_image")


def _clean_md(md):
    # Maybe this should use a whitelist instead
    for key in MD_UNUSED_KEYS:
        if key in md:
            del md[key]


def _get_path_metadata(library_pk, path):
    md = {}
    m2m_md = {}
    group_tree_md = {}
    failed_import = {}

    try:
        md = ComicArchive(path).get_metadata()
        md["path"] = str(path)
        md["size"] = Path(path).stat().st_size
        cover_path = get_cover_path(path)
        md["cover_path"] = cover_path
        QUEUE.put(ComicCoverCreateTask(library_pk, path, cover_path, True))
        _clean_md(md)
        group_tree = []
        for group_cls in BROWSER_GROUPS:
            group_field = group_cls.__name__.lower()
            # some volumes are read by ComicArchive as ints, cast
            group_name = str(md.get(group_field, ""))
            # This fixes no imprint or whatever being in md
            md[group_field] = group_name
            group_tree.append(group_name)

        groups_md = {}
        md_group_count_fields = BROWSER_GROUP_TREE_COUNT_FIELDS & md.keys()
        for key in md_group_count_fields:
            groups_md[key] = md.pop(key)

        group_tree_md[tuple(group_tree)] = groups_md

        # many_to_many fields get moved into a seperate dict
        md_m2m_fields = COMIC_M2M_FIELDS & md.keys()
        for field in md_m2m_fields:
            m2m_md[field] = md.pop(field)
    except Exception as exc:
        LOG.exception(exc)
        failed_import = {path: exc}
    return md, m2m_md, group_tree_md, failed_import


def _aggregate_metadata(
    all_mds,
    all_m2m_mds,
    all_fks,
    all_failed_imports,
    md,
    m2m_md,
    group_tree_md,
    failed_import,
):
    path = md["path"]
    if md:
        all_mds[path] = md

    if m2m_md:
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
                        # These fields are ambigous because they're fks to Credit
                        #   but aren't ever in Comic so query_fks.py can
                        #   disambiguate with special code
                        if field not in all_fks:
                            all_fks[field] = set()
                        all_fks[field].add(name)
                    credit_tuple = tuple(sorted(credit_dict.items()))
                    all_fks["credits"].add(credit_tuple)
            else:
                if field not in all_fks:
                    all_fks[field] = set()
                all_fks[field] |= set(names)

    # group hierarchy
    if group_tree_md:
        if "group_trees" not in all_fks:
            all_fks["group_trees"] = {}
        all_fks["group_trees"].update(group_tree_md)

    all_failed_imports.update(failed_import)


def _bulk_update_failed_imports(library_pk, failed_imports):
    existing_fi_paths = FailedImport.objects.filter(
        library=library_pk, path=failed_imports.keys()
    ).values_list("path", flat=True)
    exisiting_fi_paths = set(existing_fi_paths)
    update_failed_imports = []
    create_failed_imports = []
    for path, exc in failed_imports.items():
        reason = FailedImport.get_reason(path, exc)
        fi = FailedImport(library_id=library_pk, path=path, reason=reason)
        if path in exisiting_fi_paths:
            update_failed_imports.append(fi)
        else:
            create_failed_imports.append(fi)

    if update_failed_imports:
        FailedImport.objects.bulk_update(update_failed_imports, fields=("reason",))
    if create_failed_imports:
        FailedImport.objects.bulk_create(create_failed_imports)


def get_metadata(library_pk, all_paths):
    all_mds = {}
    all_m2m_mds = {}
    all_fks = {}
    all_failed_imports = {}

    for path in all_paths:
        md, m2m_md, group_tree_md, failed_import = _get_path_metadata(library_pk, path)
        _aggregate_metadata(
            all_mds,
            all_m2m_mds,
            all_fks,
            all_failed_imports,
            md,
            m2m_md,
            group_tree_md,
            failed_import,
        )

    all_fks["comic_paths"] = set(all_mds.keys())

    _bulk_update_failed_imports(library_pk, all_failed_imports)

    return all_mds, all_m2m_mds, all_fks
