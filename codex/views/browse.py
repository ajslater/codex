"""Views for browsing comic library."""
import logging

from bidict import bidict
from django.shortcuts import redirect
from django.urls import reverse_lazy

from codex.forms import GroupMixin
from codex.models import Comic
from codex.models import Imprint
from codex.models import Publisher
from codex.models import Series
from codex.models import Volume
from codex.views.browse_base import BrowseBaseView


LOG = logging.getLogger(__name__)


class BrowseView(BrowseBaseView):
    """Browse comics with a variety of filters and sorts."""

    success_url = reverse_lazy("browse")

    GROUP_CLASS = bidict(
        {"r": None, "p": Publisher, "i": Imprint, "s": Series, "v": Volume, "c": Comic}
    )
    GROUP_CODES = "".join(GROUP_CLASS.keys())

    def get_group(self):
        """Get the group from kwargs. Used by browse_base."""
        return self.kwargs.get("group")

    @classmethod
    def is_group_parent_of(cls, group_a, group_b):
        """Determine if a group is a parent of another."""
        return cls.GROUP_CODES.find(group_a) < cls.GROUP_CODES.find(group_b)

    def get_group_neighbor(self, group, offset):
        """
        Get a group code parent or child skipping according to settings.

        offset 1 or -1 determines parent or child.
        """
        neighbor = None
        i = self.GROUP_CODES.find(group) + offset
        if i >= 0 and i < len(self.GROUP_CODES):
            neighbor = self.GROUP_CODES[i]
        return neighbor

    def get_parent_group(self):
        """Get the parent group, skipping according to settings."""
        group = self.kwargs.get("group")
        if group == self.root_group:
            return None, False
        parent_group = self.get_group_neighbor(group, -1)
        if parent_group:
            if parent_group == "s" and not self.show_series:
                return "i", True
            if parent_group == "r" and not self.show_publishers:
                return None, True

        return parent_group, False

    def get_root_group_skip(self):
        """Get the root group, skipping according to settings."""
        if self.root_group == "r" and not self.show_publishers:
            return "p"
        if self.root_group == "s" and not self.show_series:
            return "i"
        return self.root_group

    def is_group_skipped(self, group):
        """Determine if the requested group isn't allowed."""
        if group == "r" and not self.show_publishers:
            return True
        if group == "s" and not self.show_series:
            return True

    def create_object_list(self, comics):
        """Get the objects we'll be displaying."""
        # Determine group_class and model class
        group = self.kwargs.get("group")
        self.group_class = self.GROUP_CLASS[group]

        # Get the child/model class
        if self.group_class is None:
            # We're at 'r', the root.
            self.model = Publisher
        elif self.group_class == Imprint and not self.show_series:
            # Skip Series model going down.
            self.model = Volume
        else:
            self.model = self.group_class.CHILD_CLASS

        pk = self.kwargs.get("pk")
        if pk:
            self.group_instance = self.group_class.objects.select_related().get(pk=pk)
        else:
            self.group_instance = None

        search_kwargs = {"comic__in": comics}

        # Get the instances that are children of the group_instance
        # And the filtered comics that are children of the group_instance
        if pk > 0 and group != self.root_group:
            ancestor_relation = self.model.PARENT_FIELD
            if not self.show_series and group == "i":
                grandparent_field = self.model.grandparent_field()
                ancestor_relation += f"__{grandparent_field}"
            if ancestor_relation:
                search_kwargs[ancestor_relation] = pk

            # Filter by comics that are part of this group if we're not
            # in a 0 pk level
            comic_filter = {self.group_class.__name__.lower(): pk}
            comics = comics.filter(**comic_filter)
        obj_list = self.model.objects.filter(**search_kwargs)

        return obj_list, comics

    def get_up_context(self):
        """Get the up link context."""
        # Parent Group
        # Get the parent group possibly skipping a level according to
        # settings
        parent_group, skipped = self.get_parent_group()

        # Parent ID
        # Get the parent id if we're not at the root, if we skipped a level
        # get the grandparent.
        ancestor_id = 0
        pk = self.kwargs.get("pk")
        if parent_group and parent_group != self.root_group and pk:
            ancestor = self.group_instance.parent
            if ancestor and skipped:
                # Get granparent
                ancestor = ancestor.parent
            if ancestor:
                ancestor_id = ancestor.pk

        return parent_group, ancestor_id

    def get_browse_title(self):
        """Get the proper title for this browse level."""
        show_folders = True
        pk = self.kwargs.get("pk")
        group = self.kwargs.get("group")
        if group == self.root_group or pk == 0:
            settings = self.browse_session.get("settings")
            browse_title = GroupMixin.get_group_name(group, settings, show_folders)
        else:
            browse_title = ""
            header = self.group_instance.header_name
            if header:
                browse_title += header + " "
            browse_title += self.group_instance.display_name
        return browse_title

    def get_context(self):
        """Set context."""
        parent_group, parent_id = self.get_up_context()
        child_group = self.GROUP_CLASS.inverse[self.model]
        browse_title = self.get_browse_title()

        context = self.get_context_data(
            root_group=self.root_group,
            browse_parent_group=parent_group,
            browse_parent_id=parent_id,
            browse_title=browse_title,
            child_group=child_group,
        )
        return self.get_common_context(context)

    def set_browse_options(self):
        """Set the browse options on the view to save db calls."""
        self.show_publishers = self.browse_session["settings"].get("show_publishers")
        self.show_series = self.browse_session["settings"].get("show_series")

    def redirect_to_correct_view(self):
        """Check that all the view variables are set right."""
        self.root_group = self.browse_session.get("root_group")
        if self.root_group == "f":
            LOG.debug("Redirect to folder view.")
            pk = self.kwargs.get("pk")
            return redirect("folder", pk=pk)
        self.set_browse_options()
        skip_to = self.get_root_group_skip()
        if skip_to != self.root_group:
            self.browse_session["root_group"] = self.root_group = skip_to
            self.request.session.save()
            LOG.debug(f"Reset root group to '{self.root_group}'")

        group = self.kwargs.get("group", "r")

        if self.is_group_skipped(group):
            LOG.debug(
                f"Asked for skipped group {group}."
                f" Redirecting to root group {self.root_group}"
            )
            return redirect("browse", group=self.root_group, pk=0)

        if self.is_group_parent_of(group, self.root_group):
            LOG.debug(
                f"Redirect to {self.root_group}/0 because group"
                f" '{group}' was a parent of root group '{self.root_group}'."
            )
            return redirect("browse", group=self.root_group, pk=0)

        return False

    def get_queryset(self):
        """Create and browse queryset."""
        comics = self.get_filtered_comics()
        obj_list, comics = self.create_object_list(comics)
        return self.annotate_and_sort_object_list(obj_list, comics, self.model)

    def form_valid(self, form):
        """Collect arguments from form."""
        old_root_group = self.session_get(self.BROWSE_KEY, "root_group")
        # Write the form to the session
        self.session_form_set(self.BROWSE_KEY, form)
        self.request.session.save()

        root_group = self.session_get(self.BROWSE_KEY, "root_group")
        if old_root_group != root_group:
            # If group choice changed, redirect to proper browse top
            LOG.debug(f"Root group changed from {old_root_group} to {root_group}.")
            LOG.debug(f"Redirect to new {root_group}.")
            return redirect("browse", group=root_group, pk=0)
        return self.main_view()

    def get(self, request, *args, **kwargs):
        """Check to see if we need a different view, otherwise render."""
        return self.main_view()
