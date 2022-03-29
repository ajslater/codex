"""Clean up the database after moves or imports."""
from logging import getLogger
from pathlib import Path

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
LOG = getLogger(__name__)


def _bulk_cleanup_fks(classes, field_name):
    """Remove foreign keys that aren't used anymore."""
    changed = False
    for cls in classes:
        filter_dict = {f"{field_name}__isnull": True}
        query = cls.objects.filter(**filter_dict)
        count = query.count()
        query.delete()
        if count:
            LOG.info(f"Deleted {count} orphan {cls.__name__}s")
            changed = True
    return changed


def bulk_cleanup_failed_imports(library):
    """Remove FailedImport objects that have since succeeded."""
    LOG.verbose("Cleaning up failed imports...")  # type: ignore
    failed_import_paths = set(
        FailedImport.objects.filter(library=library).values_list("path", flat=True)
    )

    # Cleanup FailedImports that were actually successful
    succeeded_imports = set(
        Comic.objects.filter(library=library, path__in=failed_import_paths).values_list(
            "path", flat=True
        )
    )
    delete_failed_imports = succeeded_imports

    # Cleanup FailedImports that aren't on the filesystem anymore.
    didnt_succeed_paths = failed_import_paths - succeeded_imports
    for path in didnt_succeed_paths:
        if not Path(path).exists():
            delete_failed_imports.add(path)

    if not delete_failed_imports:
        return

    count, _ = FailedImport.objects.filter(
        library=library.pk, path__in=delete_failed_imports
    ).delete()
    if count:
        LOG.info(f"Cleaned up {count} failed imports from {library.path}")
    else:
        LOG.info("No failed imports to clean up.")


def cleanup_fks():
    """Clean up unused foreign keys."""
    # TODO move all this to janitor?
    LOG.verbose("Cleaning up unused foreign keys...")  # type: ignore
    _bulk_cleanup_fks(DELETE_COMIC_FKS, "comic")
    _bulk_cleanup_fks(DELETE_CREDIT_FKS, "credit")
    LOG.verbose("Done cleaning up unused foreign keys.")  # type: ignore
