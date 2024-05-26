"""Update Groups timestamp for cover cache busting."""

from django.db.models.functions import Now
from django.db.models.query import Q

from codex.models import StoryArc


class CoversMixin:
    """Update Groups timestamp for cover cache busting."""

    def update_groups_for_covers(self, start_time, deleted_comic_groups):
        """Update timestamps for each group for cover cache busting."""
        total_count = 0
        now = Now()

        log_list = []
        for model, pks in deleted_comic_groups.items():
            rel = "story_arc_number__" if model == StoryArc else ""
            updated_at_rel = rel + "comic__updated_at__gt"
            updated_filter = {updated_at_rel: start_time}
            model_qs = (
                model.objects.filter(Q(**updated_filter) | Q(pk__in=pks))
                .distinct()
                .only("updated_at")
            )

            updated = []
            for obj in model_qs:
                obj.updated_at = now
                updated.append(obj)

            count = len(updated)
            if count:
                model.objects.bulk_update(updated, ["updated_at"])
                log_list.append(f"{count} {model.__name__}s.")
                total_count += count
        if total_count:
            groups_log = ", ".join(log_list)
            self.log.debug(  # type: ignore
                f"Updated {groups_log} timestamps for browser cache busting."
            )
            self.log.info(  # type: ignore
                f"Updated {total_count} group timestamps for browser cache busting."
            )

        return total_count
