"""A filter for group ACLS."""
from django.db.models import Q

from codex.models import Comic, Folder, StoryArc


class GroupACLMixin:
    """Filter group ACLS for views."""

    ROOT_GROUP = "r"
    FOLDER_GROUP = "f"
    STORY_ARC_GROUP = "a"
    COMIC_GROUP = "c"
    GROUP_RELATION = {
        "p": "publisher",
        "i": "imprint",
        "s": "series",
        "v": "volume",
        COMIC_GROUP: "pk",
        FOLDER_GROUP: "parent_folder",
        STORY_ARC_GROUP: "story_arc_numbers__story_arc",
    }

    def get_rel_prefix(self, model):
        """Return the relation prfiex for most fields."""
        prefix = ""
        if model != Comic:
            if model == StoryArc:
                prefix += "storyarcnumber__"
            prefix += "comic__"
        return prefix

    def get_group_acl_filter(self, model):
        """Generate the group acl filter for comics."""
        # The rel prefix
        prefix = self.get_rel_prefix(model) if model != Folder else ""
        groups_rel = f"{prefix}library__groups"

        # Libraries with no groups are always visible
        query = Q(**{groups_rel: None})

        # If the user is logged in, they can see grouped libraries
        # for the groups they're in.
        user = self.request.user  # type: ignore
        if user:
            query |= Q(**{f"{groups_rel}__in": user.groups.all()})

        return query
