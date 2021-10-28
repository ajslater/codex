"""Bulk import and move comics and folders."""
import logging

from pathlib import Path

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
from codex.librarian.queue_mp import QUEUE, LibraryChangedTask
from codex.models import Comic, Folder, Library


LOG = logging.getLogger(__name__)
MOVED_BULK_COMIC_UPDATE_FIELDS = ("path", "parent_folder")
MOVED_BULK_FOLDER_UPDATE_FIELDS = ("path", "parent_folder", "name", "sort_name")


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

        mds, m2m_mds, fks = get_aggregate_metadata(
            library.pk, update_paths | create_paths
        )

        _bulk_create_comic_relations(library, fks)

        bulk_import_comics(library, create_paths, update_paths, mds, m2m_mds)

    cleanup_database(library, delete_paths)
    total_imported = len(update_paths) + len(create_paths)
    if total_imported or delete_paths:
        QUEUE.put(LibraryChangedTask())


def bulk_comics_moved(library_pk, moved_paths):
    """Abbreviated bulk_import_comics to just change path related fields."""
    LOG.debug(f"{moved_paths=}")
    library = Library.objects.get(pk=library_pk)

    # Prepare FKs
    create_folder_paths = query_missing_folder_paths(library.path, moved_paths.values())
    bulk_create_folders(library, create_folder_paths)

    # Update Comics
    comics = Comic.objects.filter(library=library, path__in=moved_paths.keys()).only(
        "pk", "path", "parent_folder", "folder"
    )
    LOG.debug(f"{comics=}")

    folder_m2m_links = {}
    for comic in comics:
        comic.path = moved_paths[comic.path]
        new_path = Path(comic.path)
        comic.parent_folder = Folder.objects.get(path=new_path.parent)
        folder_m2m_links[comic.pk] = Folder.objects.filter(
            path__in=new_path.parents
        ).values_list("pk", flat=True)
        LOG.debug(f"{new_path=}")

    Comic.objects.bulk_update(comics, MOVED_BULK_COMIC_UPDATE_FIELDS)

    # Update m2m field
    bulk_recreate_m2m_field("folder", folder_m2m_links)
    LOG.info(f"Moved {len(moved_paths)} comics.")
    cleanup_database(library)
    if moved_paths:
        QUEUE.put(LibraryChangedTask())


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
    if folders_moved:
        QUEUE.put(LibraryChangedTask())
