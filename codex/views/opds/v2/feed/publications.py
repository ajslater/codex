"""Publication Methods for OPDS v2.0 feed."""

from collections.abc import Collection, Iterable
from datetime import datetime
from math import floor
from types import MappingProxyType, SimpleNamespace
from typing import Final, override
from urllib.parse import quote_plus

from caseconverter import snakecase
from django.db.models import CharField, F, Value

from codex.librarian.covers.create import THUMBNAIL_HEIGHT, THUMBNAIL_WIDTH
from codex.models import Comic
from codex.models.groups import BrowserGroupModel, Folder
from codex.models.named import Credit
from codex.settings import BROWSER_MAX_OBJ_PER_PAGE
from codex.views.auth import GroupACLMixin
from codex.views.opds.const import (
    AUTHOR_ROLES,
    OPDS_M2M_MODELS,
    MimeType,
    Rel,
)
from codex.views.opds.v2.const import HrefData, Link, LinkData
from codex.views.opds.v2.feed.feed_links import OPDS2FeedLinksView

_PUBLICATION_PREVIEW_LIMIT: Final = 5
_PREVIEW_SHOW_PARAMS: Final[MappingProxyType[str, bool]] = MappingProxyType(
    {"p": True, "s": True}
)
# Direct ``Comic`` attribute → metadata key mapping. Mirrors the
# manifest-side map in ``codex/views/opds/v2/manifest.py``; kept
# in-module here because the publications feed shouldn't import view
# code from the manifest path (sibling branches).
_PUBLICATION_DIRECT_FIELDS: Final[MappingProxyType[str, str]] = MappingProxyType(
    {
        "description": "summary",
    }
)
# Publisher/imprint Contributor browse-group routing. Both render as
# Readium Contributor objects (name + links) per
# https://readium.org/webpub-manifest/schema/contributor.schema.json
# so OPDS2 clients can navigate to the publisher/imprint feed.
_CONTRIBUTOR_GROUP_MAP: Final[MappingProxyType[str, str]] = MappingProxyType(
    {
        "publisher": "p",
        "imprint": "i",
    }
)
# Role-name → metadata-key partition for OPDS2 contributor fields.
# The metadata serializer declares 11 contributor categories; rows
# with a role-name not in any bucket are dropped.
_MD_CREDIT_MAP: Final[MappingProxyType[str, frozenset[str]]] = MappingProxyType(
    {
        "author": frozenset(AUTHOR_ROLES),
        "translator": frozenset({"Translator"}),
        "editor": frozenset({"Editor"}),
        "artist": frozenset({"CoverArtist", "Cover", "Artist"}),
        "illustrator": frozenset({"Illustrator"}),
        "letterer": frozenset({"Letterer"}),
        "penciller": frozenset({"Penciller"}),
        "colorist": frozenset({"Colorist", "Colors"}),
        "inker": frozenset({"Inker", "Inks"}),
        "contributor": frozenset({"Contributor"}),
        "narrator": frozenset({"Narrator"}),
    }
)


class OPDS2PublicationBaseView(OPDS2FeedLinksView):
    """Base view for publication entries."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize vars."""
        self._auth_link = None
        super().__init__(*args, **kwargs)

    def is_allowed(self, link_spec: Link | BrowserGroupModel) -> bool:
        """
        Return if the link is allowed.

        Folder-style links are gated on the ``folder_view`` admin
        flag. Reads through ``self.admin_flags`` (request-cached
        ``MappingProxyType`` populated by ``SearchFilterView``) so the
        check is a dict lookup, not a fresh ``AdminFlag.objects.get``
        per call (sub-plan 04 #2).
        """
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
            return bool(self.admin_flags.get("folder_view"))
        return True

    @staticmethod
    def _obj_ts(obj) -> int:
        """
        Floor of unix timestamp for cache-busting query params.

        Used as the ``?ts=...`` value on cover / page / sub-feed links
        so a stale cached response is invalidated by mtime changes
        without inflicting cache-key churn at every microsecond.
        Centralized so the six sites that build ``ts`` aren't each
        re-deriving the same expression (sub-plan 04 #4 / 05 #6).
        """
        return floor(datetime.timestamp(obj.updated_at))

    def _publication_metadata(self, obj, zero_pad) -> dict:
        title_filename_fallback = bool(self.admin_flags.get("folder_view"))
        if self.kwargs.get("group") == "f":
            title = Comic.get_filename(obj)
        else:
            title = Comic.get_title(
                obj,
                volume=True,
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

    def _publication_contributor(self, obj, kind: str) -> dict | None:
        """Build a Readium Contributor for publisher/imprint with a browse link."""
        name = getattr(obj, f"{kind}_name", None)
        if not name:
            return None
        contributor: dict[str, str | list] = {"name": name}
        pk = getattr(obj, f"{kind}_id", None)
        if not pk:
            return contributor
        group = _CONTRIBUTOR_GROUP_MAP[kind]
        ts = self._obj_ts(obj)
        href_data = HrefData(
            {"group": group, "pks": (pk,), "page": 1},
            {"ts": ts, "topGroup": "p"},
            url_name="opds:v2:feed",
        )
        link_data = LinkData(Rel.SUB, href_data, mime_type=MimeType.OPDS_JSON)
        if link := self.link(link_data):
            contributor["links"] = [link]
        return contributor

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

    def _publication(self, obj, zero_pad) -> dict:
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

    def _thumb(self, obj) -> list:
        images = []
        if not obj:
            return images
        ts = self._obj_ts(obj)
        # Publications are Comic rows — obj.pk is the comic pk, which is
        # also the representative cover pk. Route to the thin per-pk
        # endpoint so the cover pipeline isn't re-run per request.
        kwargs = {"pk": obj.pk}
        query_params = {"ts": ts}
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

    def __init__(self, *args, **kwargs) -> None:
        """Initialize per-feed batch caches."""
        super().__init__(*args, **kwargs)
        # Populated by ``get_publications`` before the per-publication
        # loop. ``_publication_metadata`` reads them per ``obj.pk``.
        self._credits_by_pk: dict[int, dict[str, list]] = {}
        self._subjects_by_pk: dict[int, list] = {}

    @staticmethod
    def _build_credits_by_pk(comic_pks: Collection[int]) -> dict[int, dict[str, list]]:
        """
        Per-comic credit map keyed by metadata role bucket.

        Single batched query against ``Credit`` joined with ``person``
        and ``role``, partitioned in Python by ``_MD_CREDIT_MAP``. Rows
        with a role-name not in any bucket are dropped. Replaces a
        per-publication credit fan-out (the manifest path is still
        per-comic via ``_publication_credits`` — fine for that endpoint
        because it serves a single book per call).
        """
        if not comic_pks:
            return {}
        rows = (
            Credit.objects.filter(comic__in=comic_pks)
            .annotate(
                _comic_id=F("comic"),
                name=F("person__name"),
                role_name=F("role__name"),
            )
            .values("pk", "name", "role_name", "_comic_id")
            .order_by("_comic_id", "role_name", "name")
        )
        # Reverse-index role_name → bucket so the partition is O(1) per row.
        role_to_bucket: dict[str, str] = {
            role: bucket for bucket, roles in _MD_CREDIT_MAP.items() for role in roles
        }
        by_pk: dict[int, dict[str, list]] = {pk: {} for pk in comic_pks}
        for row in rows:
            bucket = role_to_bucket.get(row["role_name"])
            if bucket is None:
                continue
            cid = row["_comic_id"]
            if cid not in by_pk:
                continue
            credit = SimpleNamespace(
                pk=row["pk"],
                name=row["name"],
                role_name=row["role_name"],
                identifier="",
                links=(),
            )
            by_pk[cid].setdefault(bucket, []).append(credit)
        return by_pk

    @staticmethod
    def _build_subjects_by_pk(comic_pks: Collection[int]) -> dict[int, list]:
        """
        Per-comic subject (M2M) list as a flat union across model kinds.

        Single ``UNION ALL`` over the seven ``OPDS_M2M_MODELS`` filtered
        by comic pk. Mirrors the per-comic union in
        ``OPDS2ManifestMetadataView._publication_subject`` but indexed
        by comic pk for the feed path.
        """
        if not comic_pks or not OPDS_M2M_MODELS:
            return {}
        queries = []
        for model in OPDS_M2M_MODELS:
            rel = GroupACLMixin.get_rel_prefix(model)
            kind = model.__name__.lower()
            q = (
                model.objects.filter(**{rel + "in": comic_pks})
                .annotate(
                    _kind=Value(kind, output_field=CharField()),
                    _comic_id=F(rel + "id"),
                )
                .values("pk", "name", "_kind", "_comic_id")
            )
            queries.append(q)
        rows = (
            queries[0]
            .union(*queries[1:], all=True)
            .order_by("_comic_id", "_kind", "name")
        )
        by_pk: dict[int, list] = {pk: [] for pk in comic_pks}
        seen: dict[tuple[int, str], set[int]] = {}
        for row in rows:
            cid = row["_comic_id"]
            kind = row["_kind"]
            ipk = row["pk"]
            bucket_seen = seen.setdefault((cid, kind), set())
            if ipk in bucket_seen or cid not in by_pk:
                continue
            bucket_seen.add(ipk)
            by_pk[cid].append(SimpleNamespace(pk=ipk, name=row["name"], links=()))
        return by_pk

    def _publication_contributors(self, obj) -> dict:
        """Return the populated publisher/imprint Contributor map for ``obj``."""
        contributors = {}
        for kind in _CONTRIBUTOR_GROUP_MAP:
            if contributor := self._publication_contributor(obj, kind):
                contributors[kind] = contributor
        return contributors

    @override
    def _publication_metadata(self, obj, zero_pad) -> dict:
        """Build feed-side metadata enriched with batched credits + subjects."""
        md = super()._publication_metadata(obj, zero_pad)

        # Direct attribute → metadata key passthrough.
        for md_key, attr in _PUBLICATION_DIRECT_FIELDS.items():
            if value := getattr(obj, attr, None):
                md[md_key] = value

        # Publisher/imprint render as Contributor objects (name + browse link).
        md.update(self._publication_contributors(obj))

        # Special-case transforms (mirror manifest semantics).
        if lang := getattr(obj, "language", None):
            md["language"] = lang.name
        if layout := getattr(obj, "reading_direction", None):
            md["layout"] = "scrolled" if layout == "ttb" else layout

        # Pre-batched per-pk credit + subject hydration (set up by
        # ``get_publications`` before the loop).
        if credits_for_obj := self._credits_by_pk.get(obj.pk):
            md.update(credits_for_obj)
        if subjects_for_obj := self._subjects_by_pk.get(obj.pk):
            md["subject"] = subjects_for_obj

        return md

    @override
    def _publication(self, obj, zero_pad) -> dict:
        pub = super()._publication(obj, zero_pad)
        if images := self._thumb(obj):
            pub["images"] = images
        return pub

    def _get_publications_links(self, link_spec) -> list:
        if not link_spec:
            return []
        kwargs = {"group": link_spec.group, "pks": (0,), "page": 1}
        href_data = HrefData(kwargs, link_spec.query_params, inherit_query_params=True)
        # Must be rel="self" for Stump to add View All
        link_data = LinkData(Rel.SELF, href_data=href_data, title=link_spec.title)
        return [self.link(link_data)]

    def _get_publication_section_metadata(
        self,
        title: str,
        subtitle: str,
        number_of_items: int | None,
        items_per_page: int,
    ) -> dict:
        current_page = self.kwargs.get("page", 1)
        metadata = {
            "title": title,
            "current_page": current_page,
            "items_per_page": items_per_page,
        }
        if subtitle:
            metadata["subtitle"] = subtitle
        if number_of_items:
            metadata["number_of_items"] = self._opds_number_of_books
        return metadata

    def get_publications(
        self,
        book_qs: Iterable,
        zero_pad: int,
        title: str,
        subtitle: str = "",
        items_per_page=BROWSER_MAX_OBJ_PER_PAGE,
        link_spec=None,
        number_of_items: int | None = None,
    ) -> list:
        """Get publications section."""
        # Materialize once so we can pre-fetch credits + subjects for
        # the full pk slice before the per-publication loop. Without
        # this the loop's ``_publication_metadata`` would fan out into
        # 1 credit query + 7 m2m queries per book = 8N queries on a
        # full feed page. The two batched UNION queries collapse that
        # to 2 queries flat regardless of N.
        book_list = list(book_qs)
        pks = tuple(obj.pk for obj in book_list)
        self._credits_by_pk = self._build_credits_by_pk(pks)
        self._subjects_by_pk = self._build_subjects_by_pk(pks)
        publications = []
        for obj in book_list:
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
        # Share request-scoped caches with the parent so each preview
        # link_spec doesn't repeat the AdminFlag fetch + visible-library
        # ACL lookup. ``_admin_flags`` and ``_cached_visible_library_pks``
        # depend on (user, request) only, not on params/kwargs — safe to
        # share across the 3 preview iterations (sub-plan 02 #2 / 04 #3).
        feed_view._admin_flags = self.admin_flags  # noqa: SLF001
        feed_view._cached_visible_library_pks = self._cached_visible_library_pks  # noqa: SLF001
        group = link_spec.group
        feed_view.kwargs = {"group": group, "pks": [0], "page": 1}
        params = self.get_browser_default_params()
        if link_spec.query_params:
            for key, value in link_spec.query_params.items():
                params[snakecase(key)] = value
        params["show"].update(_PREVIEW_SHOW_PARAMS)
        params["limit"] = _PUBLICATION_PREVIEW_LIMIT

        feed_view.set_params(params)
        return feed_view

    def get_publications_preview(self, link_spec: Link) -> list:
        """Get a limited preview of publications outside the main query."""
        feed_view = self._get_publications_preview_feed_view(link_spec)
        book_qs, book_count, zero_pad = feed_view.get_book_qs()
        if not book_count:
            return []

        return self.get_publications(
            book_qs,
            zero_pad,
            link_spec.title,
            items_per_page=_PUBLICATION_PREVIEW_LIMIT,
            link_spec=link_spec,
            number_of_items=book_count,
        )
