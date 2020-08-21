"""Views for reading comic books."""
import logging

from dataclasses import dataclass

from django.http import Http404
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.generic import DetailView
from django.views.generic import FormView
from django.views.generic import RedirectView
from django.views.generic import View
from django.views.generic.detail import SingleObjectMixin

from codex.forms import ReaderForm
from codex.models import Comic
from codex.views.session import SessionMixin
from codex.views.session import UserBookmarkMixin
from comicbox.comic_archive import ComicArchive


LOG = logging.getLogger(__name__)


class ComicPageView(View, SingleObjectMixin):
    """Display a comic page from the archive itself."""

    model = Comic

    def get(self, request, *args, **kwargs):
        """Get the comic page from the archive."""
        comic = self.get_object()
        try:
            car = ComicArchive(comic.path)
            page_num = self.kwargs.get("page_num")
            page_image = car.get_page_by_index(page_num)
            return HttpResponse(page_image, content_type="image/jpeg")
        except Exception as exc:
            LOG.exception(exc)
            page_num = self.kwargs.get("page_num")
            raise Http404(f"{comic.header_name} page {page_num} not found.")


class ComicReadView(RedirectView, SessionMixin, UserBookmarkMixin):
    """The main comic reader view."""

    pattern_name = "comic_read_page"

    def get_redirect_url(self, *args, **kwargs):
        """Redirect to the correct bookmark."""
        pk = self.kwargs.get("pk", 0)
        ub = self.get_user_bookmark(pk)
        if ub and ub.bookmark is not None:
            page_num = ub.bookmark
        else:
            page_num = 0

        return super().get_redirect_url(pk=pk, page_num=page_num)


class ComicReadPageView(DetailView, FormView, SessionMixin, UserBookmarkMixin):
    """The main reader page."""

    model = Comic
    template_name = "codex/reader.html"
    form_class = ReaderForm

    @dataclass
    class ComicArgs:
        """Arguments for building template urls."""

        pk: int
        page: int

    def get_comics_in_series(self):
        """Get all the comics in a series."""
        comic = self.object
        comics = (
            Comic.objects.all()
            .filter(volume__series=comic.volume.series)
            .order_by("volume__name", "issue")
        )
        return comics

    def get_prev_next_comics(
        self, prev_comic_id, prev_page_num, next_comic_id, next2_comic_id
    ):
        """Get the previous and next comics in a series."""
        comics = self.get_comics_in_series()
        current_id = self.object.id
        matched_current = False
        matched_next = False
        for comic in comics:
            if matched_next:
                next2_comic_id = comic.id
                break
            if matched_current:
                next_comic_id = comic.id
                matched_next = True
                if not self.two_pages or next2_comic_id:
                    # We don't need next2_comic, finish.
                    break
            if comic.id == current_id:
                matched_current = True
                if next_comic_id and (not self.two_pages or next2_comic_id):
                    # We just needed prev comic, finish
                    break
            elif not matched_current and not prev_comic_id:
                # Haven't matched yet, so set the previous comic
                prev_comic_id = comic.id
                prev_page_num = max(comic.page_count - 1, 0)
        return (prev_comic_id, prev_page_num, next_comic_id, next2_comic_id)

    def get_prev_page_num(self):
        """Get the previous page number."""
        page_num = self.kwargs.get("page_num", 0)
        prev_page_num = page_num - 1
        if prev_page_num >= 0:
            # Same comic.
            prev_comic_id = self.object.id
        else:
            prev_comic_id = 0
        return prev_comic_id, prev_page_num

    def get_next_page_num(self, page_num=None):
        """Get the next page number or the next following the argument."""
        if page_num is None:
            page_num = self.kwargs.get("page_num", 0)
        next_page_num = page_num + 1
        if next_page_num <= self.max_page:
            # Same comic.
            next_comic_id = self.object.id
        else:
            # Last page. Get next comic.
            next_comic_id = next_page_num = 0
            # Mark the comic finished if we're on the last page
            pk = self.kwargs.get("pk")
            self.update_user_bookmark({"finished": True}, pk)
        return next_comic_id, next_page_num

    def get_next2_page_num(self, next_comic_id, next_page_num):
        """Get the next2 page number."""
        if self.two_pages and next_comic_id == self.object.id:
            next2_comic_id, next2_page_num = self.get_next_page_num(next_page_num)
        else:
            next2_comic_id = next2_page_num = 0
        return next2_comic_id, next2_page_num

    def get_prev_next_pages(self):
        """Get the args the template uses to construct the prev url."""
        # Most of the time the page numbers will tell us that the
        # prev & next comic ids are in our current comic
        prev_comic_id, prev_page_num = self.get_prev_page_num()
        next_comic_id, next_page_num = self.get_next_page_num()
        next2_comic_id, next2_page_num = self.get_next2_page_num(
            next_comic_id, next_page_num
        )

        # If they're not in the same comic, get the comic ids
        (
            prev_comic_id,
            prev_page_num,
            next_comic_id,
            next2_comic_id,
        ) = self.get_prev_next_comics(
            prev_comic_id, prev_page_num, next_comic_id, next2_comic_id
        )

        return {
            "prev": self.ComicArgs(prev_comic_id, prev_page_num),
            "next": self.ComicArgs(next_comic_id, next_page_num),
            "next2": self.ComicArgs(next2_comic_id, next2_page_num),
        }

    def redirect_to_correct_view(self):
        """Redirect to a valid page number."""
        page_num = self.kwargs.get("page_num", 0)
        self.max_page = max(self.object.page_count - 1, 0)
        if page_num > self.max_page:
            LOG.warning(
                f"Page num {page_num} > max page {self.max_page}."
                "Redirecting to the end of the book."
            )
            pk = self.kwargs.get("pk")
            return redirect("comic_read_page", pk, self.max_page)

    def get_reader_setting(self, key, ub=None):
        """Get the user bookmark setting or fall back to the reader session."""
        if ub is None:
            pk = self.kwargs.get("pk")
            ub = self.get_user_bookmark(pk)
        val = None
        if ub:
            val = getattr(ub, key)
        if val is None:
            val = self.reader_session.get(key)

        return val

    def set_reader_settings(self):
        """Set the reader settings on this request."""
        pk = self.kwargs.get("pk")
        ub = self.get_user_bookmark(pk)
        self.fit_to = self.get_reader_setting("fit_to", ub)
        self.two_pages = self.get_reader_setting("two_pages", ub)

    def get_context(self):
        """Create the context."""
        self.reader_session = self.get_session(self.READER_KEY)
        self.set_reader_settings()
        pages = self.get_prev_next_pages()

        page_count = self.object.page_count
        page_num = self.kwargs.get("page_num", 0)
        progress = float(page_num / page_count) * 100

        initial = {
            "fit_to": self.fit_to,
            "two_pages": self.two_pages,
            "goto": self.kwargs.get("page_num"),
        }
        form = ReaderForm(page_count, initial=initial)

        return self.get_context_data(
            pages=pages,
            form=form,
            reader_session=self.reader_session,
            progress=progress,
            fit_to=self.fit_to,
            two_pages=self.two_pages,
        )

    def main_view(self):
        """Construct the main comic reader view."""
        self.object = self.get_object()

        response = self.redirect_to_correct_view()
        if response:
            return response

        # Set the bookmark
        page_num = self.kwargs.get("page_num", 0)
        pk = self.kwargs.get("pk")
        self.update_user_bookmark({"bookmark": page_num}, pk)

        self.request.session.save()
        context = self.get_context()
        return self.render_to_response(context)

    def form_update_bookmark(self, form):
        """Update bookmark db from form."""

    def form_valid(self, form):
        """Process form post."""
        goto = form.cleaned_data.get("goto")
        page_num = self.kwargs.get("page_num")
        pk = self.kwargs.get("pk")
        if goto is not None and goto != page_num:
            LOG.debug(f"Goto to comic {pk} page {goto}")
            return redirect("comic_read_page", pk, goto)

        self.update_user_bookmark(form.cleaned_data, pk)
        self.session_form_set(self.READER_KEY, form)
        self.request.session.save()

        return self.main_view()

    def get(self, request, *args, **kwargs):
        """Display the main view."""
        return self.main_view()
