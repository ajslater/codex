"""Publication Methods for OPDS v2.0 feed."""

from collections.abc import Iterable
from datetime import datetime
from math import floor
from urllib.parse import quote_plus

from caseconverter import snakecase
from typing_extensions import override

from codex.choices.admin import AdminFlagChoices
from codex.librarian.covers.create import THUMBNAIL_HEIGHT, THUMBNAIL_WIDTH
from codex.models import AdminFlag, Comic
from codex.models.groups import BrowserGroupModel, Folder
from codex.settings import MAX_OBJ_PER_PAGE
from codex.views.opds.const import MimeType, Rel
from codex.views.opds.v2.const import HrefData, Link, LinkData
from codex.views.opds.v2.feed.feed_links import OPDS2FeedLinksView

_PUBLICATION_PREVIEW_LIMIT = 5


class OPDS2PublicationBaseView(OPDS2FeedLinksView):
    """Base view for publication entries."""

    def __init__(self, *args, **kwargs):
        """Initialize vars."""
        self._auth_link = None
        super().__init__(*args, **kwargs)

    @staticmethod
    def is_allowed(link_spec: Link | BrowserGroupModel):
        """Return if the link allowed."""
        if (
            isinstance(link_spec, Link)
            and (
                link_spec.group == "f"
                or (
                    link_spec.query_params
                    and link_spec.query_params.get("topGroup") == "f"
                )
            )
        ) or isinstance(link_spec, Folder):
            # Folder perms
            efv_flag = (
                AdminFlag.objects.only("on")
                .get(key=AdminFlagChoices.FOLDER_VIEW.value)
                .on
            )
            if not efv_flag:
                return False
        return True

    def _publication_metadata(self, obj, zero_pad):
        title_filename_fallback = bool(self.admin_flags.get("folder_view"))
        if self.kwargs.get("group") == "f":
            title = Comic.get_filename(obj)
        else:
            title = Comic.get_title(
                obj,
                volume=False,
                name=False,
                filename_fallback=title_filename_fallback,
                zero_pad=zero_pad,
            )
        md = {
            "type": MimeType.BOOK,
            "modified": obj.updated_at,
            "published": obj.date,
            "title": title,
        }
        if subtitle := obj.name:
            md["subtitle"] = subtitle
        if page_count := obj.page_count:
            md["number_of_pages"] = page_count
        return md

    @property
    def auth_link(self):
        """Create a reusable authentication link dict."""
        if self._auth_link is None:
            auth_href_data = HrefData({}, url_name="opds:auth:v1")
            auth_link_data = LinkData(
                Rel.AUTHENTICATION,
                auth_href_data,
                mime_type=MimeType.AUTHENTICATION,
            )
            self._auth_link = self.link(auth_link_data)
        return self._auth_link

    def _publication_link(self, kwargs, url_name, rel, mime_type, size=None):
        href_data = HrefData(kwargs, url_name=url_name)
        link_data = LinkData(
            rel, href_data, mime_type=mime_type, authenticate=self.auth_link, size=size
        )
        return self.link(link_data)

    def _publication(self, obj, zero_pad):
        pub = {}
        if not obj:
            return pub
        pub["metadata"] = self._publication_metadata(obj, zero_pad)

        # Acquisition/Download link
        fn = quote_plus(obj.get_filename())
        acq_kwargs = {"pk": obj.pk, "filename": fn}
        download_mime_type = MimeType.FILE_TYPE_MAP.get(obj.file_type, MimeType.OCTET)
        acq_link = self._publication_link(
            acq_kwargs,
            "opds:bin:download",
            Rel.ACQUISITION,
            download_mime_type,
            size=obj.size,
        )

        # Progression Link
        prog_kwargs = {"group": "c", "pk": obj.pk}
        prog_link = self._publication_link(
            prog_kwargs, "opds:v2:position", Rel.PROGRESSION, MimeType.PROGRESSION
        )

        # Divina Manifest Link
        manifest_kwargs = {"pks": [obj.pk]}
        manifest_link = self._publication_link(
            manifest_kwargs, "opds:v2:manifest", Rel.SELF, MimeType.DIVINA
        )

        links = [
            acq_link,
            prog_link,
            manifest_link,
        ]
        pub["links"] = links

        return pub

    def _thumb(self, obj):
        images = []
        if not obj:
            return images
        ts = floor(datetime.timestamp(obj.updated_at))
        kwargs = {"group": obj.group, "pks": obj.ids}
        query_params = {
            "customCovers": True,
            "dynamicCovers": False,
            "ts": ts,
        }
        thumb_href_data = HrefData(
            kwargs,
            query_params,
            url_name="opds:bin:cover",
        )
        thumb_link_data = LinkData(
            Rel.THUMBNAIL,
            thumb_href_data,
            mime_type=MimeType.WEBP,
            height=THUMBNAIL_HEIGHT,
            width=THUMBNAIL_WIDTH,
            authenticate=self.auth_link,
        )

        thumb_link = self.link(thumb_link_data)
        images.append(thumb_link)
        return images


class OPDS2PublicationsView(OPDS2PublicationBaseView):
    """Publication Methods for OPDS 2.0 feed."""

    @override
    def _publication(self, obj, zero_pad):
        pub = super()._publication(obj, zero_pad)
        if images := self._thumb(obj):
            pub["images"] = images
        return pub

    def _get_publications_links(self, link_spec):
        if not link_spec:
            return []
        kwargs = {"group": link_spec.group, "pks": (0,), "page": 1}
        href_data = HrefData(kwargs, link_spec.query_params, inherit_query_params=True)
        # Must be rel="self" for Stump to add View All
        link_data = LinkData(Rel.SELF, href_data=href_data, title=link_spec.title)
        return [self.link(link_data)]

    def _get_publication_section_metadata(
        self, title, subtitle, number_of_items, items_per_page
    ):
        current_page = self.kwargs.get("page", 1)
        if number_of_items is None:
            number_of_items = self._opds_number_of_books
        metadata = {
            "title": title,
            "current_page": current_page,
            "items_per_page": items_per_page,
            "number_of_items": number_of_items,
        }
        if subtitle:
            metadata["subtitle"] = subtitle
        return metadata

    def get_publications(
        self,
        book_qs: Iterable,
        zero_pad: int,
        title: str,
        subtitle: str = "",
        items_per_page=MAX_OBJ_PER_PAGE,
        link_spec=None,
        number_of_items: int | None = None,
    ):
        """Get publications section."""
        publications = []
        for obj in book_qs:
            pub = self._publication(obj, zero_pad)
            publications.append(pub)

        groups = []
        if not publications:
            return groups

        metadata = self._get_publication_section_metadata(
            title, subtitle, number_of_items, items_per_page
        )
        pub_group: dict[str, list | dict] = {
            "metadata": metadata,
        }
        if links := self._get_publications_links(link_spec):
            pub_group["links"] = links
        pub_group["publications"] = publications
        groups.append(pub_group)
        return groups

    def _get_publications_preview_feed_view(self, link_spec: Link):
        feed_view = OPDS2FeedLinksView()
        feed_view.request = self.request
        group = link_spec.group
        feed_view.kwargs = {"group": group, "pks": [0], "page": 1}
        params = {}
        if link_spec.query_params:
            for key, value in link_spec.query_params.items():
                params[snakecase(key)] = value
        params["show"] = {"p": True, "s": True}
        params["limit"] = _PUBLICATION_PREVIEW_LIMIT

        feed_view.set_params(params)
        return feed_view

    def get_publications_preview(self, link_spec: Link):
        """Get a limited preview of publications outside the main query."""
        feed_view = self._get_publications_preview_feed_view(link_spec)
        book_qs, book_count, zero_pad = feed_view.get_book_qs()
        if not book_count:
            return []

        return self.get_publications(
            book_qs,
            zero_pad,
            link_spec.title,
            "",
            _PUBLICATION_PREVIEW_LIMIT,
            link_spec,
            number_of_items=book_count,
        )
