"""Link Covers."""

from pathlib import Path

from codex.librarian.importer.const import CLASS_CUSTOM_COVER_GROUP_MAP, LINK_COVER_PKS
from codex.librarian.importer.failed_imports import FailedImportsImporter
from codex.librarian.importer.status import ImportStatusTypes
from codex.models import CustomCover, Folder
from codex.status import Status


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
        count = 0
        if not objs:
            return count
        model.objects.bulk_update(objs, ["custom_cover"])
        count += len(objs)
        self.log.info(f"Linked {count} custom covers to {model.__name__}s")
        status.complete += count
        self.status_controller.update(status, notify=False)
        return count

    def link_custom_covers(self):
        """Link Custom Covers to Groups."""
        link_cover_pks = self.metadata.get(LINK_COVER_PKS, {})
        num_link_cover_pks = len(link_cover_pks)
        if not num_link_cover_pks:
            return 0
        status = Status(ImportStatusTypes.COVERS_LINK, 0, num_link_cover_pks)
        try:
            self.status_controller.start(status)
            # Aggregate objs to update for each group model.
            model_map = {}
            covers = CustomCover.objects.filter(pk__in=link_cover_pks).only(
                "library", "path"
            )
            for cover in covers:
                self._link_custom_cover_prepare(cover, model_map)

            # Bulk update each model type
            total_count = 0
            for model, objs in model_map.items():
                total_count += self._link_custom_cover_group(model, objs, status)
        finally:
            self.status_controller.finish(status)
        return total_count
