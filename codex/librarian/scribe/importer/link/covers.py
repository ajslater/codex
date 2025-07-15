"""Link Covers."""

from pathlib import Path

from codex.librarian.scribe.importer.const import (
    CLASS_CUSTOM_COVER_GROUP_MAP,
    LINK_COVER_PKS,
)
from codex.librarian.scribe.importer.failed.failed import FailedImportsImporter
from codex.librarian.scribe.importer.statii.link import ImporterLinkCoversStatus
from codex.models import CustomCover, Folder


class LinkCoversImporter(FailedImportsImporter):
    """Link Covers methods."""

    def _link_custom_cover_prepare(self, cover, model_map):
        """Prepare one cover in the model map for bulk update."""
        if cover.library and cover.library.covers_only:
            model = CLASS_CUSTOM_COVER_GROUP_MAP.inverse.get(cover.group)
            if not model:
                self.log.warning(f"Custom Cover model not found for {cover.path}")
                return
            group_filter = {"sort_name": cover.sort_name}
        else:
            model = Folder
            path = str(Path(cover.path).parent)
            group_filter = {"path": path}
        qs = model.objects.filter(**group_filter).exclude(custom_cover=cover)
        if not qs.exists():
            return

        if model not in model_map:
            model_map[model] = []

        for obj in qs.iterator():
            obj.custom_cover = cover
            model_map[model].append(obj)

    def _link_custom_cover_group(self, model, objs, status):
        """Bulk link a group to it's custom covers."""
        if not objs:
            return
        model.objects.bulk_update(objs, ["custom_cover"])
        status.complete += len(objs)
        self.status_controller.update(status)

    def link_custom_covers(self):
        """Link Custom Covers to Groups."""
        link_cover_pks = self.metadata.get(LINK_COVER_PKS, {})
        num_link_cover_pks = len(link_cover_pks)
        status = ImporterLinkCoversStatus(0, num_link_cover_pks)
        try:
            if not num_link_cover_pks:
                return 0
            self.status_controller.start(status)
            # Aggregate objs to update for each group model.
            model_map = {}
            covers = CustomCover.objects.filter(pk__in=link_cover_pks).only(
                "library", "path"
            )
            for cover in covers:
                self._link_custom_cover_prepare(cover, model_map)

            # Bulk update each model type
            for model, objs in model_map.items():
                self._link_custom_cover_group(model, objs, status)
        finally:
            self.status_controller.finish(status)
        return status.complete
