"""Bulk import and move comics and folders."""
from logging import getLogger
from pathlib import Path

from django.db.models.functions import Now

from codex.librarian.bulk_import.create_comics import bulk_recreate_m2m_field
from codex.librarian.bulk_import.create_fks import bulk_create_folders
from codex.librarian.bulk_import.query_fks import query_missing_folder_paths
from codex.models import Comic, Folder


LOG = getLogger(__name__)
MOVED_BULK_COMIC_UPDATE_FIELDS = ("path", "parent_folder")
MOVED_BULK_FOLDER_UPDATE_FIELDS = ("path", "parent_folder", "name", "sort_name")


# TODO optimize just name changes


def bulk_comics_moved(library, moved_paths):
    """Abbreviated bulk_import_comics to just change path related fields."""
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
        comic.set_stat()
        folder_m2m_links[comic.pk] = Folder.objects.filter(
            path__in=new_path.parents
        ).values_list("pk", flat=True)

    Comic.objects.bulk_update(comics, MOVED_BULK_COMIC_UPDATE_FIELDS)

    # Update m2m field
    bulk_recreate_m2m_field("folders", folder_m2m_links)
    LOG.info(f"Moved {len(moved_paths)} comics.")
    return len(comics) > 0


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
        folder.set_stat()
        folder.updated_at = Now()  # type: ignore
        update_folders.append(folder)

    update_folders = sorted(update_folders, key=lambda x: len(Path(x.path).parts))

    Folder.objects.bulk_update(update_folders, MOVED_BULK_FOLDER_UPDATE_FIELDS)
    LOG.info(f"Moved {len(update_folders)} folders.")
    return len(update_folders) > 0


def bulk_folders_moved(library, folders_moved):
    """Move folders in the database instead of recreating them."""
    dest_parent_folders = _get_parent_folders(library, folders_moved)
    return _update_moved_folders(library, folders_moved, dest_parent_folders)
