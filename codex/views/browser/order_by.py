"""Base view for ordering the query."""

from types import MappingProxyType

from codex.choices.browser import BROWSER_EXTRA_SORT_UNSUPPORTED_KEYS
from codex.models import Comic
from codex.models.groups import Volume
from codex.views.browser.columns import m2m_alias_for, m2m_columns
from codex.views.browser.group_mtime import BrowserGroupMtimeView

# Order keys that don't map directly to a Comic field name need an
# explicit ORM path. The map is consumed both by ``_add_comic_order_by``
# (the Comic ORDER BY clause) and by ``annotate_order_value`` (the
# ``order_value`` annotation used by serializers and group aggregates).
COMIC_ORDER_FIELD_PATHS = MappingProxyType(
    {
        "country": "country__name",
        "imprint_name": "imprint__name",
        # ``issue`` is a virtual order_by key that stands in for the
        # compound issue_number + issue_suffix sort. Its primary field
        # is ``issue_number``; ``_add_comic_order_by`` adds
        # ``issue_suffix`` as the secondary ORDER BY column.
        "issue": "issue_number",
        "language": "language__name",
        "main_character": "main_character__name",
        "main_team": "main_team__name",
        "original_format": "original_format__name",
        "publisher_name": "publisher__name",
        "scan_info": "scan_info__name",
        "series_name": "series__name",
        "tagger": "tagger__name",
        "volume_name": "volume__name",
    }
)


def comic_order_path(order_key: str) -> str:
    """Translate an ``order_by`` enum key to a Comic ORM path."""
    return COMIC_ORDER_FIELD_PATHS.get(order_key, order_key)


class BrowserOrderByView(BrowserGroupMtimeView):
    """Base class for views that need ordering."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize memoized vars."""
        super().__init__(*args, **kwargs)
        self._order_key: str = ""
        self._comic_sort_names: tuple[str, ...] = ()

    @property
    def order_key(self) -> str:
        """Get the default order key for the view."""
        if not self._order_key:
            order_key: str = self.params["order_by"]
            if (order_key == "search_score" and not self.fts_mode) or (
                (order_key == "filename" and not self.admin_flags["folder_view"])
                or (order_key == "child_count" and self.TARGET == "cover")
            ):
                order_key = "sort_name"
            self._order_key = order_key
        return self._order_key

    def _add_comic_order_by(
        self, order_key, comic_sort_names, *, for_cover: bool = False
    ) -> list:
        """Order by for comics (and covers)."""
        if not order_key:
            order_key = self.order_key
        if order_key == "child_count":
            order_key = "sort_name"
        # The cover subquery is a correlated Comic query that doesn't
        # carry the outer view's M2M / FK alias annotations, so an
        # M2M sort would reference a missing column. Cover-context
        # falls back to sort_name — pickling "the first comic" by
        # alphabetical title is what the cover subquery wants anyway.
        if for_cover and order_key in m2m_columns():
            order_key = "sort_name"
        if order_key == "sort_name":
            if not comic_sort_names:
                comic_sort_names = self._comic_sort_names
            order_fields_head = [
                *comic_sort_names,
                "issue_number",
                "issue_suffix",
                "collection_title",
                "sort_name",
            ]
        elif order_key == "issue":
            # Compound issue sort: number first, suffix as secondary.
            # The ``issue`` order_by enum value is virtual — it expands
            # to two real Comic fields here so SQL ORDER BY does the
            # natural multi-field sort that matches how the compound
            # ``Issue`` table column is rendered.
            order_fields_head = ["issue_number", "issue_suffix"]
        elif order_key in m2m_columns():
            # M2M sort: ``ORDER BY <alias>`` where the alias is the
            # JsonGroupArray annotation added by the table-view path.
            # Identical M2M sets yield identical aggregate strings,
            # so equivalent rows cluster together — the property the
            # user actually cares about.
            order_fields_head = [m2m_alias_for(order_key)]
        else:
            # Comic orders on indexed fields directly
            # Which is allegedly faster than using tmp b-trees (annotations)
            # And since that's every cover sort, it's worth it.
            order_fields_head = [comic_order_path(order_key)]
            # Comic order micro optimizations
            if order_key == "story_arc_number":
                order_fields_head += ["date"]
            elif order_key == "bookmark_updated_at":
                order_fields_head += ["bookmark_updated_at"]
        return order_fields_head

    @staticmethod
    def extra_order_value_alias(idx: int) -> str:
        """Return the queryset alias used for the n-th extra key on a group queryset."""
        return f"_table_extra_value_{idx}"

    def _add_extra_order_by(self, qs) -> list[str]:
        """
        Build the ``ORDER BY`` tail from ``order_extra_keys``.

        Active only when the request is in table mode — cover view's
        toolbar can't add extras and we don't want stored extras to
        silently affect cover-grid order. Comic-row queries chain
        each extra through :func:`_add_comic_order_by` so M2M and
        FK-name keys resolve to their upstream-annotated aliases.
        Group queries reference the per-extra ``order_value`` aliases
        annotated by ``annotate_extra_order_values`` upstream.
        """
        extras = self.params.get("order_extra_keys") or ()
        if not extras or self.params.get("view_mode") != "table":
            return []
        tail: list[str] = []
        if qs.model is Comic:
            for entry in extras:
                key = entry.get("key")
                if not key:
                    continue
                if key in BROWSER_EXTRA_SORT_UNSUPPORTED_KEYS or key == "child_count":
                    # ``child_count`` doesn't apply on Comic rows
                    # (every comic has implicit count 1). The
                    # frontend grays out the unsupported keys, but
                    # a stored payload could still hit; fall back to
                    # ``sort_name`` so the ORDER BY tail still binds.
                    extra_fields = ["sort_name"]
                else:
                    extra_fields = self._add_comic_order_by(key, None)
                prefix = "-" if entry.get("reverse") else ""
                tail.extend(prefix + field for field in extra_fields)
            return tail
        for idx, entry in enumerate(extras):
            key = entry.get("key")
            if not key:
                continue
            prefix = "-" if entry.get("reverse") else ""
            tail.append(prefix + self.extra_order_value_alias(idx))
        return tail

    def add_order_by(
        self, qs, order_key="", comic_sort_names=None, *, for_cover: bool = False
    ):
        """Create the order_by list."""
        if qs.model is Comic:
            order_fields_head = self._add_comic_order_by(
                order_key, comic_sort_names, for_cover=for_cover
            )
        elif qs.model is Volume and order_key == "sort_name":
            order_fields_head = ["name", "number_to"]
        else:
            order_fields_head = ["order_value"]

        # Empty prefix yields the same field name; the comprehension
        # works for both reversed and forward order without branching.
        prefix = "-" if self.params.get("order_reverse") else ""
        order_by = [prefix + field for field in order_fields_head]
        # Multi-column sort experiment: append per-key extras between
        # the primary fields and the pk tiebreaker. Each entry carries
        # its own direction so the user can mix asc / desc per column.
        if not for_cover:
            order_by.extend(self._add_extra_order_by(qs))
        order_by.append(prefix + "pk")

        return qs.order_by(*order_by)
