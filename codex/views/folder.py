"""Folder based view."""
import logging

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import unquote

from django.http import Http404
from django.shortcuts import redirect

# from codex.forms import BrowseForm
from django.urls import reverse_lazy

from codex.library.importer import COMIC_MATCHER
from codex.models import Comic
from codex.models import RootPath
from codex.views.browse_base import BrowseBaseView


LOG = logging.getLogger(__name__)


class FolderView(BrowseBaseView):
    """Browse filesystem folders, but only database comics."""

    # template_name = "codex/browse.html"
    # form_class = BrowseForm
    success_url = reverse_lazy("folder")

    @dataclass
    class Folder:
        """Mock a Model just for display."""

        BROWSE_TYPE = "Folder"
        root_path_id: int
        path: Path
        cover_id: int
        name: str
        date: date

        @property
        def display_name(self):
            return self.name

    def path_secure(self, path, root_path=None, root_path_id=None):
        if root_path_id == 0:
            return "", ""
        if root_path is None:
            root_path = RootPath.objects.get(pk=root_path_id)
        top_path = Path(root_path.path)
        proposed_path = top_path / path
        resolved_path = proposed_path.resolve()
        if not resolved_path.is_dir():
            raise Http404(f"{resolved_path} is not a folder.")
        # This should throw a ValueError if its not a child of
        # the root path
        relative_path = resolved_path.relative_to(top_path)
        return resolved_path, relative_path

    def create_object_list(self, comics):
        comic_dict = {}
        folder_dict = {}
        root_paths = RootPath.objects.all()
        pk = self.kwargs.get("pk")
        if pk != 0:
            root_paths = root_paths.filter(pk=pk)

        quoted_path = self.kwargs.get("path", "")
        req_path = Path(unquote(quoted_path))
        for root_path in root_paths:
            resolved_path, relative_path = self.path_secure(req_path, root_path)
            self.root_path = root_path
            self.relative_path = relative_path

            for child_path in sorted(resolved_path.iterdir()):
                if not comics.filter(path__startswith=child_path).exists():
                    continue
                if child_path.is_dir():
                    if root_path not in folder_dict:
                        folder_dict[root_path] = []
                    folder_dict[root_path].append(child_path)
                else:
                    if not COMIC_MATCHER.search(child_path.suffix):
                        continue
                    try:
                        comic = Comic.objects.get(path=child_path)
                        if root_path not in comic_dict:
                            comic_dict[root_path] = []
                        comic_dict[root_path].append(comic)
                    except Comic.DoesNotExist:
                        pass
        return folder_dict, comic_dict

    def get_unique_name(self, root_path_id, name):
        """
        If an object has a name collision, number it.

        Folder view has a mashed up root folder of many root_paths
        to protect the anonymity of the actual filesystem.
        """
        if self.kwargs.get("pk") == 0 and name in self.root_view_names:
            name += f" ({root_path_id})"
        self.root_view_names.add(name)
        return name

    def sort_folders_inner(self, root_path, folders, folder_list, order_by):
        for folder in folders:
            relative_path = folder.relative_to(root_path.path)
            comic = (
                Comic.objects.filter(path__startswith=str(folder))
                .order_by(*order_by)
                .first()
            )
            name = self.get_unique_name(root_path.id, relative_path.name)
            folder_view = self.Folder(
                root_path_id=root_path.id,
                path=self.quote(relative_path),
                cover_id=comic.id,
                name=name,
                date=comic.date,
            )

            folder_list.append(folder_view)

    def sort_comics_inner(self, root_path, comics, comic_list, order_by):
        for comic in comics:
            # Don't save this display name overwrite!
            comic.display_name = self.get_unique_name(root_path.id, comic.display_name)
            comic.cover_id = comic.id
            comic_list.append(comic)

    def sorter(self, obj_dict, sort_func, order_key, order_by):
        """Passing functions, oh my."""
        obj_list = []
        for root_path, objs in obj_dict.items():
            sort_func(root_path, objs, obj_list, order_by)
        sort_reverse = self.session_get(self.BROWSE_KEY, "sort_reverse")
        obj_list.sort(key=lambda x: getattr(x, order_key), reverse=sort_reverse)
        return obj_list

    def sort_object_list(self, folder_dict, comic_dict):
        self.root_view_names = set()
        order_key, order_by = self.create_order_by()
        folder_list = self.sorter(
            folder_dict, self.sort_folders_inner, order_key, order_by
        )
        comic_list = self.sorter(
            comic_dict, self.sort_comics_inner, order_key, order_by
        )
        return folder_list + comic_list

    def save_session(self):
        pk = self.kwargs.get("pk")
        quoted_path = self.kwargs.get("path", "")
        _, relative_path = self.path_secure(unquote(quoted_path), root_path_id=pk)
        self.session_set(self.VIEW_KEY, "folder", self.quote(relative_path))
        self.session_set(self.VIEW_KEY, "root_path_id", pk)
        self.request.session.save()

    def get_up_context(self):
        browse_title = ""
        up_pk = -1
        up_path = ""

        pk = self.kwargs.get("pk")
        # Recall root id & relative path from way back in
        # object creation
        path_str = str(self.relative_path)
        if pk > 0 and path_str != ".":
            up_pk = self.root_path.id
            up_path = self.quote(str(self.relative_path.parent))
            browse_title = path_str

        return up_pk, up_path, browse_title

    def get_context(self):
        initial = self.get_session(self.BROWSE_KEY)
        form = self.form_class(initial=initial)
        up_pk, up_path, browse_title = self.get_up_context()
        return self.get_context_data(
            form=form,
            browse_title=browse_title,
            folder_up_pk=up_pk,
            folder_up_path=up_path,
        )

    def finish_view(self):
        """Create the folder view."""
        # Filter & Create
        comics = self.get_filtered_comics()
        folder_dict, comic_dict = self.create_object_list(comics)
        self.object_list = self.sort_object_list(folder_dict, comic_dict)

        self.save_session()
        context = self.get_context()
        return self.render_to_response(context)

    def form_valid(self, form):
        """Process the form post."""
        # Save the form to the session.
        self.session_form_set(self.BROWSE_KEY, form)
        root_group = self.session_get(self.BROWSE_KEY, "root_group")

        if root_group != "f":
            # If the browse view is selected, go there.
            self.request.session.save()
            return redirect("browse_root")

        return self.finish_view()

    def get(self, request, *args, **kwargs):
        """Get the form view."""
        root_group = self.session_get(self.BROWSE_KEY, "root_group")
        if root_group != "f":
            """If we're supposed to be in browse view, go there."""
            return redirect("browse_root")

        return self.finish_view()
