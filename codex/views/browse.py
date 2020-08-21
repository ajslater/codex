"""Views for browsing comic library."""
import logging

from pathlib import Path

from django.db.models import OuterRef
from django.db.models import Subquery
from django.shortcuts import redirect
from django.urls import reverse_lazy

from codex.forms import SortChoice
from codex.models import Comic
from codex.models import Imprint
from codex.models import Publisher
from codex.models import Series
from codex.models import Volume
from codex.settings import STATIC_ROOT
from codex.views.browse_base import BrowseBaseView


LOG = logging.getLogger(__name__)


class BrowseView(BrowseBaseView):
    """Browse comics with a variety of filters and sorts."""

    success_url = reverse_lazy("browse")

    GROUP_CODES = "rpisvc"
    GROUP_CHILD_CLASS = {
        "r": Publisher,
        "p": Imprint,
        "i": Series,
        "s": Volume,
        "v": Comic,
    }

    @classmethod
    def is_group_parent_of(cls, group_a, group_b):
        return cls.GROUP_CODES.find(group_a) < cls.GROUP_CODES.find(group_b)

    def create_object_list(self, comics):
        # Get the objects we'll be displaying
        root_group = self.session_get(self.BROWSE_KEY, "root_group")
        group = self.kwargs.get("group")
        pk = self.kwargs.get("pk", 0)

        self.model = self.GROUP_CHILD_CLASS.get(group, Publisher)

        relation = self.model.COMIC_RELATION
        if self.model == Comic:
            relation += "pk__in"
        else:
            relation += "in"
        search_kwargs = {relation: comics}
        if pk > 0 and group != root_group:
            parent_relation = self.model.PARENT_FIELD
            if parent_relation:
                search_kwargs[parent_relation] = pk
        obj_list = self.model.objects.all().filter(**search_kwargs).distinct()
        return obj_list

    def sort_object_list(self, obj_list, comics):
        """Sort the final object list."""
        sort_by = self.session_get(self.BROWSE_KEY, "sort_by")

        if self.model == Comic:
            relation_path = "pk"
        else:
            relation_path = Comic.RELATIONS[self.model]
        search_kwargs = {relation_path: OuterRef("pk")}

        _, order_by = self.create_order_by()
        comics = comics.filter(**search_kwargs).order_by(*order_by)

        if sort_by == SortChoice.DATE.name and self.model != Comic:
            date_subquery = Subquery(comics.values("date")[:1])
            obj_list = obj_list.annotate(date=date_subquery)

        cover_id_subquery = Subquery(comics.values("pk")[:1])
        obj_list = obj_list.annotate(cover_id=cover_id_subquery).order_by(*order_by)

        return obj_list

    def get_related_group(self, group, parent=True):
        i = self.GROUP_CODES.find(group)
        if i < 0:
            return "r"
        j = i + -1 if parent else i + 1
        code = self.GROUP_CODES[j]
        return code

    def get_up_context(self):
        """Get the up link context."""
        group = self.kwargs.get("group")
        pk = self.kwargs.get("pk")
        root_group = self.session_get(self.BROWSE_KEY, "root_group")

        parent_group = self.get_related_group(group, parent=True)

        parent_id = -1
        if group != root_group and pk > 0 and self.model.PARENT_CLS:
            obj = self.model.PARENT_CLS.objects.get(pk=pk)
            parent_id = obj.parent.pk

        group_title = self.model.PLURAL
        return parent_group, parent_id, group_title

    def save_session(self):
        # Save session
        group = self.kwargs.get("group")
        self.session_set(self.VIEW_KEY, "group", group)
        pk = self.kwargs.get("pk")
        self.session_set(self.VIEW_KEY, "group_id", pk)
        self.request.session.save()

    def get_context(self):
        # Set context
        (parent_group, parent_id, group_title,) = self.get_up_context()
        group = self.kwargs.get("group")
        child_group = self.get_related_group(group, parent=False)
        initial = self.get_session(self.BROWSE_KEY)
        form = self.form_class(initial=initial)
        return self.get_context_data(
            form=form,
            child_group=child_group,
            browse_parent_group=parent_group,
            browse_parent_id=parent_id,
            browse_title=group_title,
        )

    def finish_and_render(self):
        comics = self.get_filtered_comics()
        obj_list = self.create_object_list(comics)
        self.object_list = self.sort_object_list(obj_list, comics)
        self.save_session()
        context = self.get_context()
        return self.render_to_response(context)

    def form_valid(self, form):
        """Collect arguments from form."""
        old_root_group = self.session_get(self.BROWSE_KEY, "root_group")
        # Write the form to the session
        self.session_form_set(self.BROWSE_KEY, form)
        root_group = self.session_get(self.BROWSE_KEY, "root_group")

        if root_group == "f":
            # if folder_view was chosen, redirect
            self.request.session.save()
            return redirect("folder_top", pk=0)

        group = self.kwargs.get("group")
        if self.is_group_parent_of(group, root_group):
            self.request.session.save()
            return redirect("browse", group=root_group, pk=0)
        elif old_root_group != root_group:
            # If group choice changed, redirect to proper browse top
            self.request.session.save()
            return redirect("browse", group=root_group, pk=0)

        return self.finish_and_render()

    def get(self, request, *args, **kwargs):
        """Check to see if we need a different view, otherwise render."""
        root_group = self.session_get(self.BROWSE_KEY, "root_group")
        if root_group == "f":
            return redirect("folder_top", pk=0)

        group = self.kwargs.get("group")
        if self.is_group_parent_of(group, root_group):
            return redirect("browse", group=root_group, pk=0)

        return self.finish_and_render()
