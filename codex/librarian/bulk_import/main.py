"""Bulk import and move comics and folders."""
from logging import getLogger
from pathlib import Path

from django.core.cache import cache
from django.db.models.functions import Now

from codex.librarian.bulk_import.aggregate_metadata import get_aggregate_metadata
from codex.librarian.bulk_import.cleanup import cleanup_database
from codex.librarian.bulk_import.create_comics import (
    bulk_import_comics,
    bulk_recreate_m2m_field,
)
from codex.librarian.bulk_import.create_fks import (
    bulk_create_all_fks,
    bulk_create_folders,
)
from codex.librarian.bulk_import.query_fks import (
    query_all_missing_fks,
    query_missing_folder_paths,
)
from codex.models import Comic, Folder, Library


LOG = getLogger(__name__)
MOVED_BULK_COMIC_UPDATE_FIELDS = ("path", "parent_folder")
MOVED_BULK_FOLDER_UPDATE_FIELDS = ("path", "parent_folder", "name", "sort_name")
# Batching entire imports doesn't really seem neccissary. This code is left here
#   as a cautionary measure just in case.
# Move folder and move comics are not yet batched
BATCH_SIZE = 100000


def _bulk_create_comic_relations(library, fks):
    """Query all foreign keys to determine what needs creating, then create them."""
    if not fks:
        return

    create_fks, create_groups, create_paths, create_credits = query_all_missing_fks(
        library.path, fks
    )

    bulk_create_all_fks(
        library, create_fks, create_groups, create_paths, create_credits
    )


def _split_batch(paths, batch_size):
    """Split paths into a batch with variable size."""
    end = max(min(len(paths), batch_size), 0)
    head = set(paths[:batch_size])
    tail = paths[batch_size:]
    return end, head, tail


def _split_batches(update_paths, create_paths):
    """Split both path lists into batches totalling BATCH_SIZE."""
    update_end, update_head, update_tail = _split_batch(update_paths, BATCH_SIZE)

    create_batch_size = BATCH_SIZE - update_end
    _, create_head, create_tail = _split_batch(create_paths, create_batch_size)

    return update_head, update_tail, create_head, create_tail


def _batch_bulk_import(library, update_paths_tail, create_paths_tail):
    """Perform one batch of imports."""
    (
        update_paths_head,
        update_paths_tail,
        create_paths_head,
        create_paths_tail,
    ) = _split_batches(update_paths_tail, create_paths_tail)

    LOG.verbose(  # type: ignore
        f"Batch update {len(update_paths_head)} create {len(create_paths_head)}."
    )
    mds, m2m_mds, fks = get_aggregate_metadata(
        library, update_paths_head | create_paths_head
    )

    _bulk_create_comic_relations(library, fks)

    bulk_import_comics(library, create_paths_head, update_paths_head, mds, m2m_mds)
    return update_paths_tail, create_paths_tail


def bulk_import(
    library=None,
    update_paths=None,
    create_paths=None,
    delete_paths=None,
    library_pk=None,
):
    """Bulk import comics."""
    if not library:
        library = Library.objects.get(pk=library_pk)

    if update_paths or create_paths:
        if not update_paths:
            update_paths = set()
        if not create_paths:
            create_paths = set()

        LOG.verbose(  # type: ignore
            f"Importing comics: {len(create_paths)} new, {len(update_paths)} "
            f"outdated, {len(delete_paths)} deleted."
        )

        update_paths_tail = sorted([str(path) for path in update_paths])
        create_paths_tail = sorted([str(path) for path in create_paths])

        while update_paths_tail or create_paths_tail:
            update_paths_tail, create_paths_tail = _batch_bulk_import(
                library, update_paths_tail, create_paths_tail
            )
        total_imported = len(update_paths) + len(create_paths)
    else:
        total_imported = 0

    if not delete_paths:
        delete_paths = set()
    cleanup_database(library, delete_paths)
    return total_imported, len(delete_paths)


def bulk_comics_moved(library_pk, moved_paths):
    """Abbreviated bulk_import_comics to just change path related fields."""
    library = Library.objects.get(pk=library_pk)

    # Prepare FKs
    create_folder_paths = query_missing_folder_paths(library.path, moved_paths.values())
    bulk_create_folders(library, create_folder_paths)

    # Update Comics
    comics = Comic.objects.filter(library=library, path__in=moved_paths.keys()).only(
        "pk", "path", "parent_folder", "folders"
    )

    folder_m2m_links = {}
    for comic in comics:
        comic.path = moved_paths[comic.path]
        new_path = Path(comic.path)
        comic.parent_folder = Folder.objects.get(path=new_path.parent)
        comic.updated_at = Now()  # type: ignore
        folder_m2m_links[comic.pk] = Folder.objects.filter(
            path__in=new_path.parents
        ).values_list("pk", flat=True)

    Comic.objects.bulk_update(comics, MOVED_BULK_COMIC_UPDATE_FIELDS)

    # Update m2m field
    bulk_recreate_m2m_field("folders", folder_m2m_links)
    LOG.info(f"Moved {len(moved_paths)} comics.")
    cleanup_database(library)
    cache.clear()
    return bool(moved_paths)


def _get_parent_folders(library, folders_moved):
    """Get destination parent folders."""
    library_path = Path(library.path)
    dest_folder_paths = set(folders_moved.values())
    dest_parent_folder_paths = set()
    for dest_folder_path in dest_folder_paths:
        dest_parent_path = Path(dest_folder_path).parent
        if dest_parent_path == library_path:
            continue
        dest_parent_folder_paths.add(str(dest_parent_path))

    dest_parent_folders_objs = Folder.objects.filter(
        path__in=dest_parent_folder_paths
    ).only("path", "pk")
    dest_parent_folders = {}
    for folder in dest_parent_folders_objs:
        dest_parent_folders[folder.path] = folder
    return dest_parent_folders


def _update_moved_folders(library, folders_moved, dest_parent_folders):
    # Move folders
    src_folder_paths = set(folders_moved.keys())
    folders = Folder.objects.filter(library=library, path__in=src_folder_paths)

    update_folders = []
    for folder in folders:
        new_path = folders_moved[folder.path]
        folder.name = Path(new_path).name
        folder.sort_name = folder.name
        folder.path = new_path
        parent_path = str(Path(new_path).parent)
        folder.parent_folder = dest_parent_folders.get(parent_path)
        folder.updated_at = Now()  # type: ignore
        update_folders.append(folder)

    update_folders = sorted(update_folders, key=lambda x: len(Path(x.path).parts))

    Folder.objects.bulk_update(update_folders, MOVED_BULK_FOLDER_UPDATE_FIELDS)
    LOG.info(f"Moved {len(update_folders)} folders.")


def bulk_folders_moved(library_pk, folders_moved):
    """Move folders in the database instead of recreating them."""
    library = Library.objects.get(pk=library_pk)
    dest_parent_folders = _get_parent_folders(library, folders_moved)
    _update_moved_folders(library, folders_moved, dest_parent_folders)
    cleanup_database(library)
    cache.clear()
