"""Update and create failed imports."""
from pathlib import Path

from django.db.models import Q
from django.db.models.functions import Now

from codex.models import Comic, FailedImport
from codex.settings.logging import get_logger


BULK_UPDATE_FAILED_IMPORT_FIELDS = ("name", "stat", "updated_at")
LOG = get_logger(__name__)


def _bulk_update_failed_imports(library, failed_imports):
    """Bulk update failed imports."""
    if not failed_imports:
        return
    update_failed_imports = FailedImport.objects.filter(
        library=library, path__in=failed_imports.keys()
    )

    count = 0
    now = Now()
    for fi in update_failed_imports:
        try:
            exc = failed_imports.pop(fi.path)
            fi.set_reason(exc)
            fi.set_stat()
            fi.updated_at = now
        except Exception as exc:
            LOG.error(f"Error preparing failed import update for {fi.path}")
            LOG.exception(exc)

    if update_failed_imports:
        count = FailedImport.objects.bulk_update(
            update_failed_imports, fields=BULK_UPDATE_FAILED_IMPORT_FIELDS
        )
    if count is None:
        count = 0
    log = f"Updated {count} old comics in failed imports."
    if count:
        LOG.warning(log)
    else:
        LOG.verbose(log)


def _bulk_create_failed_imports(library, failed_imports) -> bool:
    """Bulk create failed imports."""
    if not failed_imports:
        return False
    create_failed_imports = []
    for path, exc in failed_imports.items():
        try:
            fi = FailedImport(library=library, path=path, parent_folder=None)
            fi.set_reason(exc)
            fi.set_stat()
            create_failed_imports.append(fi)
        except Exception as exc:
            LOG.error(f"Error preparing failed import create for {path}")
            LOG.exception(exc)
    if create_failed_imports:
        FailedImport.objects.bulk_create(create_failed_imports)
    count = len(create_failed_imports)
    log = f"Added {count} comics to failed imports."
    if count:
        LOG.warning(log)
    else:
        LOG.verbose(log)
    return bool(count)


def _bulk_cleanup_failed_imports(library):
    """Remove FailedImport objects that have since succeeded."""
    LOG.verbose("Cleaning up failed imports...")
    failed_import_paths = FailedImport.objects.filter(library=library).values_list(
        "path", flat=True
    )

    # Cleanup FailedImports that were actually successful
    succeeded_imports = Comic.objects.filter(
        library=library, path__in=failed_import_paths
    ).values_list("path", flat=True)

    # Cleanup FailedImports that aren't on the filesystem anymore.
    didnt_succeed_paths = (
        FailedImport.objects.filter(library=library)
        .exclude(path__in=succeeded_imports)
        .values_list("path", flat=True)
    )
    missing_failed_imports = set()
    for path in didnt_succeed_paths:
        if not Path(path).exists():
            missing_failed_imports.add(path)

    count, _ = (
        FailedImport.objects.filter(library=library.pk)
        .filter(Q(path__in=succeeded_imports) | Q(path__in=missing_failed_imports))
        .delete()
    )
    if count:
        LOG.info(f"Cleaned up {count} failed imports from {library.path}")
    else:
        LOG.verbose("No failed imports to clean up.")


def bulk_fail_imports(library, failed_imports) -> bool:
    """Handle failed imports."""
    new_failed_imports = False
    try:
        _bulk_update_failed_imports(library, failed_imports)
        new_failed_imports = _bulk_create_failed_imports(library, failed_imports)
        _bulk_cleanup_failed_imports(library)
    except Exception as exc:
        LOG.exception(exc)
    return new_failed_imports
