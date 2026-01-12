"""Publication Methods for OPDS v2.0 feed."""

from collections.abc import Iterable
from datetime import datetime
from math import floor
from types import MappingProxyType
from urllib.parse import quote_plus

from caseconverter import snakecase
from typing_extensions import override

from codex.choices.admin import AdminFlagChoices
from codex.librarian.covers.create import THUMBNAIL_HEIGHT, THUMBNAIL_WIDTH
from codex.models import AdminFlag, Comic
from codex.models.groups import BrowserGroupModel, Folder
from codex.settings import FALSY, MAX_OBJ_PER_PAGE
from codex.views.browser.browser import BrowserView
from codex.views.opds.const import AUTHOR_ROLES, MimeType, Rel
from codex.views.opds.util import get_credits, get_m2m_objects
from codex.views.opds.v2.const import Link, LinkGroup
from codex.views.opds.v2.feed.feed_links import OPDS2FeedLinksView
from codex.views.opds.v2.feed.links import LinkData
from codex.views.opds.v2.href import HrefData

_MD_CREDIT_MAP = MappingProxyType(
    # If OPDS2 is ever popular, make this comprehensive by using comicbox role enums
    {
        "author": AUTHOR_ROLES,
        "translator": {"Translator"},
        "editor": {"Editor"},
        "artist": {"CoverArtist", "Cover", "Artist"},
        "illustrator": {"Illustrator"},
        "letterer": {"Letterer"},
        "penciller": {"Penciller"},
        "colorist": {"Colorist", "Colors"},
        "inker": {"Inker", "Inks"},
        "contributor": {"Contributor"},
        "narrator": {"Narrator"},
    }
)
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

    @staticmethod
    def _add_credits(md, pks, key, roles):
        """Add credits to metadata."""
        if credit_objs := get_credits(pks, roles, exclude=False):
            md[key] = credit_objs

    def _publication_extended_metadata(self, md, obj):
        """Publication m2m metadata only on the metadata alternate link."""
        if desc := obj.summary:
            md["description"] = desc
        if lang := obj.language:
            md["language"] = lang.name
        if publisher := obj.publisher_name:
            md["publisher"] = publisher
        if imprint := obj.imprint_name:
            md["imprint"] = imprint
        for key, roles in _MD_CREDIT_MAP.items():
            self._add_credits(md, obj.ids, key, roles)

        # Subjects can also have links
        # https://readium.org/webpub-manifest/schema/subject-object.schema.json
        m2m_objs = get_m2m_objects(obj.ids)
        subject = [subj.name for subjs in m2m_objs.values() for subj in subjs]
        if subject:
            md["subject"] = subject

        if layout := obj.reading_direction:
            md["layout"] = layout if layout != "ttb" else "scrolled"

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

        if self.request.GET.get("opdsMetadata", "").lower() not in FALSY:
            self._publication_extended_metadata(md, obj)
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

    def _publication_alt(self, obj):
        self_kwargs = {"group": "c", "pks": [obj.pk], "page": 1}

        alt_kwargs = self_kwargs
        alt_href_data = HrefData(
            alt_kwargs,
            {"opdsMetadata": 1},
            url_name="opds:v2:feed",
        )
        return LinkData(
            Rel.ALTERNATE,
            alt_href_data,
            mime_type=MimeType.OPDS_PUB,
            authenticate=self.auth_link,
        )

    def _publication(self, obj, zero_pad):
        pub = {}
        pub["metadata"] = self._publication_metadata(obj, zero_pad)

        fn = quote_plus(obj.get_filename())
        acq_kwargs = {"pk": obj.pk, "filename": fn}
        acq_href_data = HrefData(
            acq_kwargs,
            url_name="opds:bin:download",
        )
        download_mime_type = MimeType.FILE_TYPE_MAP.get(obj.file_type, MimeType.OCTET)
        acq_link_data = LinkData(
            Rel.ACQUISITION,
            acq_href_data,
            mime_type=download_mime_type,
            authenticate=self.auth_link,
            size=obj.size,
        )

        prog_kwargs = {"group": "c", "pk": obj.pk}
        prog_href_data = HrefData(prog_kwargs, url_name="opds:v2:position")
        prog_link_data = LinkData(
            Rel.PROGRESSION,
            prog_href_data,
            mime_type=MimeType.PROGRESSION,
            authenticate=self.auth_link,
        )

        manifest_kwargs = {"pks": [obj.pk]}
        manifest_href_data = HrefData(
            manifest_kwargs,
            url_name="opds:v2:manifest",
            query_params={"opdsMetadata": 1},
        )

        manifest_link_data = LinkData(
            Rel.SELF,
            manifest_href_data,
            mime_type=MimeType.DIVINA,
            authenticate=self.auth_link,
        )

        links = [
            # X self.link(self._publication_alt(obj)),
            self.link(acq_link_data),
            self.link(prog_link_data),
            self.link(manifest_link_data),
        ]
        pub["links"] = links

        return pub

    def _thumb(self, obj):
        images = []
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

    def _cover(self, obj):
        images = []
        ts = floor(datetime.timestamp(obj.updated_at))
        pk = obj.ids[0]
        kwargs = {"pk": pk, "page": 0}
        query_params = {"ts": ts, "bookmark": False, "pixmap": True}

        image_href_data = HrefData(
            kwargs,
            query_params,
            url_name="opds:bin:page",
            min_page=0,
        )
        image_link_data = LinkData(
            Rel.IMAGE,
            image_href_data,
            mime_type=MimeType.JPEG,
            # Include dummy heights just to pass client validation
            height=0,
            width=0,
            authenticate=self.auth_link,
        )
        image_link = self.link(image_link_data)
        images.append(image_link)
        return images


class OPDS2PublicationsView(OPDS2PublicationBaseView):
    """Publication Methods for OPDS 2.0 feed."""

    @override
    def _publication(self, obj, zero_pad):
        pub = super()._publication(obj, zero_pad)
        pub["images"] = self._thumb(obj)
        return pub

    def _get_publications_links(self, link_spec):
        if not link_spec:
            return []
        kwargs = {"group": link_spec.group, "pks": "0", "page": 1}
        href_data = HrefData(kwargs, link_spec.query_params, inherit_query_params=True)
        # Must be rel="self" for Stump to add View All
        link_data = LinkData(Rel.SELF, href_data=href_data, title=link_spec.title)
        return [self.link(link_data)]

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
        groups = []
        publications = []
        for obj in book_qs:
            pub = self._publication(obj, zero_pad)
            publications.append(pub)

        if not publications:
            return groups

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
        pub_group: dict[str, list | dict] = {
            "metadata": metadata,
        }
        if links := self._get_publications_links(link_spec):
            pub_group["links"] = links
        pub_group["publications"] = publications
        groups.append(pub_group)
        return groups

    def get_publications_preview(
        self, link_spec: Link | BrowserGroupModel, group_spec: LinkGroup
    ):
        """Get a limited preview of publications outside the main query."""
        browser_view = BrowserView()
        browser_view.request = self.request
        group = (
            link_spec.group
            if isinstance(link_spec, Link)
            else link_spec.__class__.__name__[0].lower()
        )
        browser_view.kwargs = {"group": group, "pks": [0], "page": 1}
        params = {}
        if isinstance(link_spec, Link) and link_spec.query_params:
            for key, value in link_spec.query_params.items():
                params[snakecase(key)] = value
        params["show"] = {"p": True, "s": True}
        params["limit"] = _PUBLICATION_PREVIEW_LIMIT

        browser_view.set_params(params)
        book_qs, book_count, zero_pad = browser_view.get_book_qs()
        if not book_count:
            return []

        link_spec = next(iter(group_spec.links))
        return self.get_publications(
            book_qs,
            zero_pad,
            group_spec.title,
            "",
            _PUBLICATION_PREVIEW_LIMIT,
            link_spec,
            number_of_items=book_count,
        )
