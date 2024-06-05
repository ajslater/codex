"""Group Filters."""

from django.db.models import Q

from codex.models import Comic
from codex.views.const import FOLDER_GROUP, GROUP_MODEL_MAP, GROUP_RELATION
from codex.views.session import SessionView


class GroupFilterView(SessionView):
    """Group Filters."""

    SESSION_KEY = SessionView.BROWSER_SESSION_KEY

    def get_group_filter(self, model):
        """Get filter for the displayed group."""
        group = self.kwargs["group"]  # type: ignore
        pks = self.kwargs["pks"]  # type: ignore
        if pks:  # type: ignore
            if model == GROUP_MODEL_MAP.get(group):
                # metadata only
                rel = "pk"
            elif model == Comic and group == FOLDER_GROUP:
                # choices & covers
                rel = "folders"
            else:
                rel = GROUP_RELATION[group]

            rel += "__in"
            group_filter_dict = {rel: pks}  # type: ignore
        elif group == FOLDER_GROUP:
            group_filter_dict = {"parent_folder": None}
        else:
            group_filter_dict = {}

        return Q(**group_filter_dict)
