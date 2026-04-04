"""Database cover integrity checks and remedies."""

from django.apps import apps

from codex.settings import (
    CUSTOM_COVERS_DIR,
)


def _repair_extra_custom_cover_libraries(library_model, log) -> None:
    """Attempt to remove the bad ones, probably futile."""
    delete_libs = library_model.objects.filter(covers_only=True).exclude(
        path=CUSTOM_COVERS_DIR
    )
    count, _ = delete_libs.delete()
    if count:
        log.warning(
            f"Removed {count} duplicate custom cover libraries pointing to unused custom cover dirs."
        )


def cleanup_custom_cover_libraries(log) -> None:
    """Cleanup extra custom cover libraries."""
    try:
        try:
            library_model = apps.get_model("codex", "library")
        except LookupError:
            log.debug("Library model doesn't exist yet.")
            return
        if not library_model or not hasattr(library_model, "covers_only"):
            log.debug("Library model doesn't support custom cover library yet.")
            return
        _repair_extra_custom_cover_libraries(library_model, log)

        custom_cover_libraries = library_model.objects.filter(covers_only=True)
        count = custom_cover_libraries.count()
        if count > 1:
            count, _ = custom_cover_libraries.delete()
            if count:
                log.warning(
                    f"Removed all ({count}) custom cover libraries, Unable to determine valid one. Will recreate upon startup."
                )
    except Exception as exc:
        log.warning(f"Failed to check custom cover library for integrity - {exc}")
