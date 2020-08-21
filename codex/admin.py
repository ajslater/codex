"""Django views for Codex."""
import logging

from django.contrib.admin import ModelAdmin
from django.contrib.admin import register

from codex.library.queue import QUEUE
from codex.library.queue import ScanRootTask
from codex.library.watcherd import RootPathWatcher
from codex.models import AdminFlag
from codex.models import RootPath


LOG = logging.getLogger(__name__)


def flatten(lst):
    """Flatten a nested tuple, set, or list."""
    out = []
    for i in lst:
        if type(i) in (tuple, list, set):
            out += flatten(i)
        else:
            out.append(i)
    return out


@register(RootPath)
class AdminRootPath(ModelAdmin):
    """Admin model for RootPath."""

    fields = (
        "path",
        "enable_watch",
        ("enable_scan_cron", "scan_frequency", "last_scan", "scan_in_progress"),
    )
    readonly_fields = ("last_scan",)
    actions = ("scan", "force_scan")
    empty_value_display = "Never"
    list_display = flatten(fields)
    list_editable = (
        "enable_watch",
        "enable_scan_cron",
        "scan_frequency",
        "scan_in_progress",
    )
    sortable_by = list_display

    def _scan(self, request, queryset, force):
        """Queue a scan task for the root path."""
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
        if obj.enable_watch:
            RootPathWatcher.start_watch(obj.pk)
        else:
            RootPathWatcher.stop_watch(obj.pk)

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
        RootPathWatcher.stop_watch(obj.pk)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """Bulk delete."""
        for obj in queryset:
            RootPathWatcher.stop_watch(obj.pk)
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
