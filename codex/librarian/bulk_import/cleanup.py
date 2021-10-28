import logging

from pathlib import Path

from codex.librarian.cover import purge_cover_path
from codex.models import (
    Character,
    Comic,
    Credit,
    CreditPerson,
    CreditRole,
    FailedImport,
    Folder,
    Genre,
    Imprint,
    Library,
    Location,
    Publisher,
    Series,
    SeriesGroup,
    StoryArc,
    Tag,
    Team,
    Volume,
)


DELETE_COMIC_FKS = (
    Volume,
    Series,
    Imprint,
    Publisher,
    Folder,
    Credit,
    Tag,
    Team,
    Character,
    Location,
    SeriesGroup,
    StoryArc,
    Genre,
)
DELETE_CREDIT_FKS = (CreditRole, CreditPerson)
LOG = logging.getLogger(__name__)


def _bulk_delete_comics(library, delete_comic_paths=None):
    if not delete_comic_paths:
        return
    query = Comic.objects.filter(library=library, path__in=delete_comic_paths)
    delete_cover_paths = query.values_list("cover_path", flat=True)

    for cover_path in delete_cover_paths:
        purge_cover_path(cover_path)

    query.delete()
    LOG.info(f"Deleted {len(delete_cover_paths)} comics from {library.path}")


def _bulk_cleanup_fks(classes, field_name):
    for cls in classes:
        filter_dict = {f"{field_name}__isnull": True}
        query = cls.objects.filter(**filter_dict)
        count = query.count()
        if count:
            query.delete()
            LOG.info(f"Deleted {count} orphan {cls.__name__}s")


def _bulk_cleanup_failed_imports(library):

    failed_import_paths = FailedImport.objects.filter(library=library).values_list(
        "path", flat=True
    )

    # Cleanup FailedImports that were actually successful
    succeeded_imports = Comic.objects.filter(
        library=library, path__in=failed_import_paths
    ).values_list("path", flat=True)
    delete_failed_imports = set(succeeded_imports)

    # Cleanup FailedImports that aren't on the filesystem anymore.
    for path in failed_import_paths:
        if not Path(path).exists():
            delete_failed_imports.add(path)

    if not delete_failed_imports:
        return

    FailedImport.objects.filter(
        library=library.pk, path__in=delete_failed_imports
    ).delete()
    LOG.info(
        f"Cleaned up {len(delete_failed_imports)} failed imports from {library.path}"
    )


def cleanup_database(library=None, delete_comic_paths=None, library_pk=None):
    if not library:
        library = Library.objects.get(pk=library_pk)
    _bulk_delete_comics(library, delete_comic_paths)
    _bulk_cleanup_fks(DELETE_COMIC_FKS, "comic")
    _bulk_cleanup_fks(DELETE_CREDIT_FKS, "credit")
    _bulk_cleanup_failed_imports(library)
