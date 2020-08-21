"""Folder based view."""
import logging

from django.shortcuts import redirect
from django.urls import reverse_lazy

from codex.models import AdminFlag
from codex.models import Comic
from codex.models import Folder
from codex.views.browse_base import BrowseBaseView


LOG = logging.getLogger(__name__)


class FolderView(BrowseBaseView):
    """Browse filesystem folders, but only database comics."""

    success_url = reverse_lazy("folder")

    @staticmethod
    def get_group():
        """Return f as that's always the folder group."""
        return "f"

    def create_object_list(self, comics):
        """Create the folder and comic object lists."""
        self.model = Folder
        pk = self.kwargs.get("pk")
        if pk:
            self.host_folder = Folder.objects.get(pk=pk)
            comics_host = comics.filter(folder=pk)
        else:
            self.host_folder = None
            comics_host = comics

        folders = Folder.objects.filter(
            parent_folder=self.host_folder, comic__pk__in=comics
        )
        level_comics = comics.filter(parent_folder=self.host_folder).select_related()

        return folders, level_comics, comics_host

    def get_up_context(self):
        """Get out parent's pk."""
        up_pk = None

        # Recall root id & relative path from way back in
        # object creation
        if self.host_folder:
            if self.host_folder.parent_folder:
                up_pk = self.host_folder.parent_folder.pk
            else:
                up_pk = 0

        return up_pk

    def get_context(self):
        """Get folder view context."""
        up_pk = self.get_up_context()

        if self.host_folder:
            browse_title = self.host_folder.name
        else:
            browse_title = "Root"

        context = self.get_context_data(folder_up_pk=up_pk, browse_title=browse_title)
        return self.get_common_context(context)

    def redirect_to_correct_view(self):
        """Check that all the view variables are set right."""
        root_group = self.browse_session.get("root_group")
        enable_fv, _ = AdminFlag.objects.get_or_create(
            name=AdminFlag.ENABLE_FOLDER_VIEW
        )
        if not enable_fv.on or root_group != "f":
            # If we're supposed to be in browse view, go there.
            LOG.debug("Redirect to browse view.")
            return redirect("browse_root")

    def get_queryset(self):
        """
        Create folder queryset.

        Actually mixed types in folder view means we explode it early
        into a list.
        """
        comics = self.get_filtered_comics()
        folders, level_comics, comics = self.create_object_list(comics)
        folders = self.annotate_and_sort_object_list(folders, comics, Folder)
        level_comics = self.annotate_and_sort_object_list(level_comics, comics, Comic)
        return list(folders) + list(level_comics)

    def form_valid(self, form):
        """Process the form post."""
        # Save the form to the session.
        self.session_form_set(self.BROWSE_KEY, form)
        self.request.session.save()
        return self.main_view()

    def get(self, request, *args, **kwargs):
        """Get the form view."""
        return self.main_view()
