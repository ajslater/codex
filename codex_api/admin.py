"""Django views for Codex."""
import logging

from django.contrib.admin import ModelAdmin
from django.contrib.admin import register

from codex_api.librarian.queue import QUEUE
from codex_api.librarian.queue import LibraryChangedTask
from codex_api.librarian.queue import ScanRootTask
from codex_api.librarian.queue import WatchLibraryTask
from codex_api.models import AdminFlag
from codex_api.models import Library


LOG = logging.getLogger(__name__)


@register(Library)
class AdminLibrary(ModelAdmin):
    """Admin model for Library."""

    fieldsets = (
        (None, {"fields": ("path", "enable_watch")}),
        ("Scans", {"fields": ("last_scan", "scan_in_progress")}),
        ("Scheduled Scans", {"fields": ("enable_scan_cron", "scan_frequency")}),
    )
    actions = ("scan", "force_scan")
    empty_value_display = "Never"
    list_display = (
        "path",
        "enable_watch",
        "enable_scan_cron",
        "scan_frequency",
        "last_scan",
        "scan_in_progress",
    )
    # Django admin will not display datetime fields if they're not editable
    list_editable = (
        "enable_watch",
        "enable_scan_cron",
        "scan_frequency",
        "scan_in_progress",
        # TODO can't submit anything if this doesn't have a value
        "last_scan",
    )
    readonly_fields = ("last_scan",)
    sortable_by = list_display

    def _scan(self, request, queryset, force):
        """Queue a scan task for the library."""
        pks = queryset.values_list("pk", flat=True)
        for pk in pks:
            task = ScanRootTask(pk, force)
            QUEUE.put(task)

    def scan(self, request, queryset):
        """Scan for new comics."""
        self._scan(request, queryset, False)

    scan.short_description = "Scan for new comics since last scan"

    def force_scan(self, request, queryset):
        """Scan all comics."""
        self._scan(request, queryset, True)

    force_scan.short_description = "Rescan all comics"

    def _on_change(self, obj, created=False):
        task = WatchLibraryTask(obj.pk, obj.enable_watch)
        QUEUE.put(task)

        if created:
            task = ScanRootTask(obj.pk, False)
            QUEUE.put(task)

    def save_model(self, request, obj, form, change):
        """Trigger watching and scanning on update or creation."""
        created = obj.pk is None
        super().save_model(request, obj, form, change)
        if change or created:
            self._on_change(obj, created)

    def delete_model(self, request, obj):
        """Stop watching on delete."""
        task = WatchLibraryTask(obj.pk, False)
        QUEUE.put(task)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """Bulk delete."""
        for obj in queryset:
            task = WatchLibraryTask(obj.pk, False)
            QUEUE.put(task)
        super().delete_queryset(request, queryset)

    def save_formset(self, request, form, formset, change):
        """Bulk update."""
        super().save_formset(request, form, formset, change)
        if change:
            for form in formset:
                self._on_change(form.instance)


@register(AdminFlag)
class AdminAdminFlag(ModelAdmin):
    """Admin model for AdminFlags."""

    fields = ("name", "on")
    readonly_fields = ("name",)
    list_display = fields
    list_editable = ("on",)
    sortable_by = fields

    def has_add_permission(self, request, obj=None):
        """Can't Add these."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Can't Remove these."""
        return False

    def save_model(self, request, obj, form, change):
        """Trigger a change notification because options have changed."""
        created = obj.pk is None
        super().save_model(request, obj, form, change)
        if change or created:
            self._on_change()

    def save_formset(self, request, form, formset, change):
        """Bulk update triggers change."""
        super().save_formset(request, form, formset, change)
        if change:
            self._on_change()

    def _on_change(self):
        """Signal UI that its out of date."""
        # XXX too heavy handed.
        # Folder View could only change the group view and let the ui decide
        # Registration only needs to change the enable flag
        task = LibraryChangedTask()
        QUEUE.put(task)
