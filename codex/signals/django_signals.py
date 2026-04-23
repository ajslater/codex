"""Django signal actions."""

from django.db.models.signals import post_delete, post_save


def _on_library_changed(*_args, **_kwargs) -> None:
    """Clear the libraries_exist cache on Library writes."""
    # Imported lazily so this module stays safe to import before django.setup().
    from codex.views.browser.browser import invalidate_libraries_exist_cache

    invalidate_libraries_exist_cache()


def connect_signals() -> None:
    """Connect actions to signals."""
    # Imported lazily for the same reason as above.
    from codex.models import Library

    post_save.connect(_on_library_changed, sender=Library)
    post_delete.connect(_on_library_changed, sender=Library)
