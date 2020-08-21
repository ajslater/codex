"""View for marking comics read and unread."""
from django.shortcuts import redirect
from django.views.generic import FormView

from codex.forms import MarkReadForm
from codex.models import Comic
from codex.views.browse import BrowseView
from codex.views.session import SessionMixin
from codex.views.session import UserBookmarkMixin


class MarkRead(FormView, SessionMixin, UserBookmarkMixin):
    """Mark read or unread recursively."""

    form_class = MarkReadForm

    def form_valid(self, form):
        """Mark read or unread recursively."""
        browse_type = self.kwargs.get("browse_type")
        pk = self.kwargs.get("pk")
        finished = form.cleaned_data.get("read")
        next_url = form.cleaned_data.get("next_url")

        cls = BrowseView.GROUP_CLASS.get(browse_type)
        field = cls.__name__.lower()
        search_kwargs = {field: pk}
        comics = Comic.objects.filter(**search_kwargs)

        for comic in comics:
            # can't do this in bulk if using update_or_create
            self.update_user_bookmark({"finished": finished}, pk=comic.pk)

        return redirect(next_url)
