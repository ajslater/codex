"""A filter for group ACLS."""
from django.db.models import Q


class GroupACLMixin:
    """Filter group ACLS for views."""

    def get_group_acl_filter(self, is_comic_model):
        """Generate the group acl filter for comics."""
        # The rel prefix
        if is_comic_model:
            prefix = ""
        else:
            prefix = "comic__"
        groups_rel = f"{prefix}library__groups"

        # Libraries with no groups are always visible
        ungrouped_query = Q(**{groups_rel: None})

        # If the user is logged in, they can see groupsed libraries
        # for the groups they're in.
        user_query = Q(
            **{f"{groups_rel}__in": self.request.user.groups.all()}  # type: ignore
        )

        return ungrouped_query | user_query
