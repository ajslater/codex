"""A filter for group ACLS."""
from django.db.models import Q


class GroupACLMixin:
    """Filter group ACLS for views."""

    ROOT_GROUP = "r"
    FOLDER_GROUP = "f"
    COMIC_GROUP = "c"
    GROUP_RELATION = {
        "p": "publisher",
        "i": "imprint",
        "s": "series",
        "v": "volume",
        COMIC_GROUP: "pk",
        FOLDER_GROUP: "parent_folder",
    }

    def get_group_acl_filter(self, is_comic_model):
        """Generate the group acl filter for comics."""
        # The rel prefix
        if is_comic_model:
            prefix = ""
        else:
            prefix = "comic__"
        groups_rel = f"{prefix}library__groups"

        # Libraries with no groups are always visible
        query = Q(**{groups_rel: None})

        # If the user is logged in, they can see grouped libraries
        # for the groups they're in.
        user = self.request.user  # type: ignore
        if user:
            query |= Q(**{f"{groups_rel}__in": user.groups.all()})

        return query
