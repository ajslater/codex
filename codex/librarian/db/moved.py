"""Bulk import and move comics and folders."""
from pathlib import Path

from django.db.models.functions import Now

from codex.librarian.db.create_comics import bulk_recreate_m2m_field
from codex.librarian.db.create_fks import bulk_folders_create
from codex.librarian.db.query_fks import query_missing_folder_paths
from codex.librarian.queue_mp import LIBRARIAN_QUEUE, BulkComicCoverCreateTask
from codex.models import Comic, Folder
from codex.settings.logging import get_logger


LOG = get_logger(__name__)
MOVED_BULK_COMIC_UPDATE_FIELDS = ("path", "parent_folder")
MOVED_BULK_FOLDER_UPDATE_FIELDS = ("path", "parent_folder", "name")


def bulk_comics_moved(library, moved_paths):
    """Abbreviated bulk_import_comics to just change path related fields."""
    # Prepare FKs
    create_folder_paths = query_missing_folder_paths(library.path, moved_paths.values())
    bulk_folders_create(library, create_folder_paths)

    # Update Comics
    comics = Comic.objects.filter(library=library, path__in=moved_paths.keys()).only(
        "pk", "path", "parent_folder", "folders"
    )

    folder_m2m_links = {}
    now = Now()
    comic_pks = []
    for comic in comics:
        try:
            comic.path = moved_paths[comic.path]
            new_path = Path(comic.path)
            if new_path.parent == Path(library.path):
                comic.parent_folder = None
            else:
                comic.parent_folder = Folder.objects.get(  # type: ignore
                    path=new_path.parent
                )
            comic.updated_at = now
            comic.set_stat()
            folder_m2m_links[comic.pk] = Folder.objects.filter(
                path__in=new_path.parents
            ).values_list("pk", flat=True)
            comic_pks.append(comic.pk)
        except Exception as exc:
            LOG.error(f"moving {comic.path}: {exc}")

    count = Comic.objects.bulk_update(comics, MOVED_BULK_COMIC_UPDATE_FIELDS)

    # Update m2m field
    if folder_m2m_links:
        bulk_recreate_m2m_field("folders", folder_m2m_links)
    log = f"Moved {count} comics."
    task = BulkComicCoverCreateTask(True, tuple(comic_pks))
    LIBRARIAN_QUEUE.put(task)
    if count:
        LOG.info(log)
    else:
        LOG.verbose(log)  # type: ignore

    return bool(count)


def _get_parent_folders(library, folders_moved):
    """Get destination parent folders."""
    library_path = Path(library.path)
    dest_folder_paths = frozenset(folders_moved.values())
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
    src_folder_paths = frozenset(folders_moved.keys())
    folders = Folder.objects.filter(library=library, path__in=src_folder_paths)

    update_folders = []
    now = Now()
    for folder in folders:
        new_path = folders_moved[folder.path]
        folder.name = Path(new_path).name
        folder.path = new_path
        parent_path = str(Path(new_path).parent)
        if parent_path == library.path:
            folder.parent_folder = None
        else:
            folder.parent_folder = dest_parent_folders.get(parent_path)
        folder.set_stat()
        folder.updated_at = now  # type: ignore
        update_folders.append(folder)

    update_folders = sorted(update_folders, key=lambda x: len(Path(x.path).parts))

    count = Folder.objects.bulk_update(update_folders, MOVED_BULK_FOLDER_UPDATE_FIELDS)
    log = f"Moved {count} folders."
    if count:
        LOG.info(log)
    else:
        LOG.verbose(log)  # type: ignore
    return bool(count)


def bulk_folders_moved(library, folders_moved):
    """Move folders in the database instead of recreating them."""
    dest_parent_folders = _get_parent_folders(library, folders_moved)
    return _update_moved_folders(library, folders_moved, dest_parent_folders)
