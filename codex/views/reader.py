"""Views for reading comic books."""
import logging

from django.http import HttpResponse
from django.views.generic import DetailView
from django.views.generic import RedirectView
from django.views.generic import View
from django.views.generic.detail import SingleObjectMixin

from codex.models import Comic
from codex.views.session import SessionMixin
from comicbox.comic_archive import ComicArchive


LOG = logging.getLogger(__name__)


class ComicPageView(View, SingleObjectMixin):
    model = Comic

    def get(self, request, *args, **kwargs):
        comic = self.get_object()
        car = ComicArchive(comic.path)
        page_num = self.kwargs.get("page_num")
        page_image = car.get_page_by_index(page_num)
        return HttpResponse(page_image, content_type="image/jpeg")


class ComicReadView(RedirectView, SessionMixin):
    pattern_name = "comic_read_page"

    def get_page_num(self, pk):
        page_num = self.session_get_comic(pk).get("bookmark", 0)
        return page_num

    def get_redirect_url(self, *args, **kwargs):
        pk = self.kwargs.get("pk", 0)
        page_num = self.get_page_num(pk)
        return super().get_redirect_url(pk=pk, page_num=page_num)


class ComicReadPageView(DetailView, SessionMixin):
    model = Comic
    template_name = "codex/reader.html"

    def get_comics_in_series(self):
        comic = self.get_object()
        comics = (
            Comic.objects.all()
            .filter(
                volume__series=comic.volume.series,
                deleted_at=None,
                root_path__deleted_at=None,
            )
            .order_by("volume__name", "issue")
        )
        return comics

    def get_previous_comic_id(self):
        comics = self.get_comics_in_series()
        last_comic = None
        current_id = self.get_object().id
        for comic in comics:
            if comic.id == current_id:
                break
            last_comic = comic
        if last_comic:
            return last_comic.id
        else:
            return 0

    def get_next_comic_id(self):
        comics = self.get_comics_in_series()
        break_next = success = False
        for comic in comics:
            if break_next:
                success = True
                break
            current_comic = self.get_object()
            if comic.id == current_comic.id:
                break_next = True
        if success:
            return comic.id
        else:
            return 0

    def get_prev_page_url(self, page_num):
        if page_num - 1 > 0:
            comic = self.get_object()
            prev_comic_id = comic.id
            prev_page_num = page_num - 1
        else:
            prev_comic_id = self.get_previous_comic_id()
            if prev_comic_id == 0:
                prev_page_num = 0
            else:
                prev_page_num = Comic.objects.get(pk=prev_comic_id).page_count - 1

        return prev_comic_id, prev_page_num

    def get_next_page_url(self, page_num, uc):
        comic = self.get_object()
        page_count = comic.page_count
        if page_num + 1 < page_count:
            next_comic_id = comic.id
            next_page_num = page_num + 1
        else:
            next_comic_id = self.get_next_comic_id()
            if next_comic_id == 0:
                next_page_num = comic.volume.series.id
            else:
                next_page_num = 0
            uc["finished"] = True

        return next_comic_id, next_page_num

    def get(self, request, *args, **kwargs):
        pk = self.kwargs.get("pk")
        page_num = self.kwargs.get("page_num", 0)
        uc = self.session_get_comic(pk)
        uc["bookmark"] = page_num
        prev_comic_id, prev_page_num = self.get_prev_page_url(page_num)
        next_comic_id, next_page_num = self.get_next_page_url(page_num, uc)
        view_session = self.get_session(self.VIEW_KEY)
        root_group = self.session_get(self.BROWSE_KEY, "root_group")

        print(view_session)
        context = {
            "comic_id": pk,
            "view": view_session,
            "root_group": root_group,
            "page_num": page_num,
            "prev_comic_id": prev_comic_id,
            "prev_page_num": prev_page_num,
            "next_comic_id": next_comic_id,
            "next_page_num": next_page_num,
        }
        request.session.save()
        return self.render_to_response(context)
