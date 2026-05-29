"""Browser Choices."""

from types import MappingProxyType

from comicbox.enums.maps.identifiers import ID_SOURCE_NAME_MAP

from codex.views.browser.const import BROWSER_FILTER_KEYS

BROWSER_BOOKMARK_FILTER_CHOICES = MappingProxyType(
    {
        "": "All",
        "IN_PROGRESS": "In Progress",
        "READ": "Read",
        "UNREAD": "Unread",
    },
)
BROWSER_ORDER_BY_CHOICES = MappingProxyType(
    {
        "created_at": "Added Time",
        "age_rating": "Age Rating",
        "characters": "Characters",
        "child_count": "Child Count",
        "country": "Country",
        "credits": "Credits",
        "critical_rating": "Critical Rating",
        "day": "Day",
        "favorite": "Favorite",
        "filename": "Filename",
        "size": "File Size",
        "file_type": "File Type",
        "original_format": "Format",
        "genres": "Genres",
        "identifiers": "Identifiers",
        "imprint_name": "Imprint",
        "issue": "Issue",
        "language": "Language",
        "bookmark_updated_at": "Last Read",
        "locations": "Locations",
        "main_character": "Main Character",
        "main_team": "Main Team",
        "metadata_mtime": "Tags Updated",
        "month": "Month",
        "monochrome": "Monochrome",
        "sort_name": "Name",
        "page_count": "Page Count",
        "publisher_name": "Publisher",
        "date": "Publish Date",
        "reading_direction": "Reading Direction",
        "scan_info": "Scan Info",
        "search_score": "Search Score",
        "series_name": "Series",
        "series_groups": "Series Groups",
        "stories": "Stories",
        "story_arc_number": "Story Arc Number",
        "story_arcs": "Story Arcs",
        "tags": "Tags",
        "tagger": "Tagger",
        "teams": "Teams",
        "universes": "Universes",
        "updated_at": "Updated Time",
        "volume_name": "Volume",
        "year": "Year",
    }
)
_GROUP_NAMES = MappingProxyType(
    {
        "p": "Publishers",
        "i": "Imprints",
        "s": "Series",
        "v": "Volumes",
    }
)
BROWSER_TOP_GROUP_CHOICES = MappingProxyType(
    {
        **_GROUP_NAMES,
        "c": "Issues",
        "f": "Folders",
        "a": "Story Arcs",
    },
)
# Subset of order-by keys that make sense in cover view's dropdown.
# The full enum (33 keys) is needed for the table view's header-click
# sorting, but most of the table-only additions (reading_direction,
# monochrome, country, language, the FK-name keys for browsing
# metadata, etc.) don't drive a useful cover-grid sort. The dropdown
# in the cover-view toolbar filters down to this set; anything not
# listed here is still a valid order_by value, it just isn't surfaced
# as a dropdown option when the cover grid is rendering.
BROWSER_COVER_ORDER_BY_KEYS = frozenset(
    {
        "created_at",
        "age_rating",
        "child_count",
        "critical_rating",
        "filename",
        "size",
        "bookmark_updated_at",
        "sort_name",
        "page_count",
        "date",
        "search_score",
        "story_arc_number",
        "updated_at",
    }
)

# Sort keys that aren't valid as multi-sort *extras* (the secondary
# / tertiary chain reachable via shift-click on a table header).
# They sort fine as the primary, but the per-extra annotation
# pipeline can't safely produce a value for them on every model
# / context: ``story_arc_number`` requires StoryArc-context ``pks``
# to resolve which arc's number to pick, and ``search_score``'s
# ``ComicFTSRank`` only resolves when an FTS subquery is joined.
# Mirrored on the frontend so the table headers can grey out the
# affected columns and refuse the shift-click.
BROWSER_EXTRA_SORT_UNSUPPORTED_KEYS = frozenset(
    {
        "story_arc_number",
        "search_score",
    }
)

BROWSER_ROUTE_CHOICES = MappingProxyType({**BROWSER_TOP_GROUP_CHOICES, "r": "Root"})
BROWSER_VIEW_MODE_CHOICES = MappingProxyType(
    {
        "cover": "Cover",
        "table": "Table",
    }
)
BROWSER_TABLE_COVER_SIZE_CHOICES = MappingProxyType(
    {
        # Single-entry tuple for now. The field stays in place so md/lg
        # can be added later without a migration; v1 ships only "sm"
        # (~32px) — the larger of the two originally proposed sizes.
        "sm": "Small",
    }
)
VUETIFY_NULL_CODE = -1
_IDENTIFIER_SOURCES = MappingProxyType(
    {key.value: value for key, value in ID_SOURCE_NAME_MAP.items()}
)
BROWSER_CHOICES = MappingProxyType(
    {
        "BOOKMARK_FILTER": BROWSER_BOOKMARK_FILTER_CHOICES,
        "ORDER_BY": BROWSER_ORDER_BY_CHOICES,
        "COVER_ORDER_BY_KEYS": tuple(sorted(BROWSER_COVER_ORDER_BY_KEYS)),
        "EXTRA_SORT_UNSUPPORTED_KEYS": tuple(
            sorted(BROWSER_EXTRA_SORT_UNSUPPORTED_KEYS)
        ),
        "TOP_GROUP": BROWSER_TOP_GROUP_CHOICES,
        "VIEW_MODE": BROWSER_VIEW_MODE_CHOICES,
        "TABLE_COVER_SIZE": BROWSER_TABLE_COVER_SIZE_CHOICES,
        "VUETIFY_NULL_CODE": VUETIFY_NULL_CODE,
        "SETTINGS_GROUP": {**_GROUP_NAMES},
        "IDENTIFIER_SOURCES": _IDENTIFIER_SOURCES,
    }
)

# Subset of BROWSER_CHOICES keys included in the Vuetify-list dump
# (``browser-choices.json``). ``IDENTIFIER_SOURCES`` is omitted — the
# frontend only consumes its raw-map form from ``browser-map.json``.
# ``VIEW_MODE`` and ``TABLE_COVER_SIZE`` are not consumed by the
# frontend in either form; their backing constants are used by the
# backend (models / serializers) but no JSON dump is needed.
BROWSER_CHOICES_VUETIFY_KEYS = frozenset(
    {
        "BOOKMARK_FILTER",
        "ORDER_BY",
        "COVER_ORDER_BY_KEYS",
        "EXTRA_SORT_UNSUPPORTED_KEYS",
        "TOP_GROUP",
        "VUETIFY_NULL_CODE",
        "SETTINGS_GROUP",
    }
)

# Subset of BROWSER_CHOICES keys included in the raw-map dump
# (``browser-map.json``). The frontend only destructures these three
# keys from ``browser-map.json``; the others are consumed via their
# Vuetify-list forms from ``browser-choices.json``.
BROWSER_CHOICES_MAP_KEYS = frozenset(
    {
        "ORDER_BY",
        "TOP_GROUP",
        "IDENTIFIER_SOURCES",
    }
)

DEFAULT_BROWSER_ROUTE = MappingProxyType({"group": "r", "pks": (0,), "page": 1})

# Top-group values that own a dedicated browser route. For these,
# the URL ``group`` matches the ``top_group``. Everything else
# (publishers / imprints / series / volumes / issues) routes through
# the canonical ``r`` (Root) URL — the per-user ``top_group`` setting
# is what selects the displayed view inside that URL.
_FLAG_GROUP_HAS_OWN_ROUTE = frozenset({"f", "a"})


def admin_default_route_for(top_group: str) -> dict:
    """
    Translate a ``BROWSER_DEFAULT_GROUP`` flag value into a route dict.

    Used by :class:`codex.views.frontend.IndexView` to redirect the bare
    ``/`` URL when no per-user ``last_route`` row exists.
    """
    group = top_group if top_group in _FLAG_GROUP_HAS_OWN_ROUTE else "r"
    return {"group": group, "pks": (0,), "page": 1}


_DEFAULT_SHOW = MappingProxyType({"i": False, "p": True, "s": True, "v": False})
_DEFAULT_FILTERS = MappingProxyType(
    {
        "bookmark": "",
        "favorite": False,
        **dict.fromkeys(BROWSER_FILTER_KEYS, ()),
    }
)
# ──────────────────────────────────────────────────────────────────────
# Browser table-view column registry
#
# Drives the table-view presentation:
#   - the column-picker dialog (every key here is a pickable column),
#   - the ``columns=`` query-param validator on the browser endpoint,
#   - the per-row serializer (which fields to project and how),
#   - the ordering pipeline (clicking a sortable column header sets
#     ``order_by`` to ``sort_key``).
#
# ``sort_key`` MUST resolve to an entry in :data:`BROWSER_ORDER_BY_CHOICES`
# for the column to be effectively sortable. ``m2m`` flags columns whose
# values come from a Many-to-Many relation and must be aggregated; these
# are display-only in v1 (sort_key is ``None``). ``editable`` and
# ``edit_widget`` are reserved for a later phase that will allow inline
# tag-cell editing.
BROWSER_TABLE_COLUMNS = MappingProxyType(
    {
        # Identity
        "cover": {
            "label": "Cover",
            "sort_key": None,
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "name": {
            "label": "Title",
            "sort_key": "sort_name",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "issue": {
            # Compound table-view column: ``issue_number`` +
            # ``issue_suffix`` rendered as one cell. The ``issue``
            # order_by enum entry is the public sort key;
            # ``_add_comic_order_by`` expands it to ``[issue_number,
            # issue_suffix]`` for the actual ORDER BY.
            "label": "Issue",
            "sort_key": "issue",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        # Group hierarchy
        "publisher_name": {
            "label": "Publisher",
            "sort_key": "publisher_name",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "imprint_name": {
            "label": "Imprint",
            "sort_key": "imprint_name",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "series_name": {
            "label": "Series",
            "sort_key": "series_name",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "volume_name": {
            "label": "Volume",
            "sort_key": "volume_name",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        # Counts
        "child_count": {
            "label": "Children",
            "sort_key": "child_count",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        # Files
        "file_name": {
            "label": "Filename",
            "sort_key": "filename",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "size": {
            "label": "Size",
            "sort_key": "size",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "page_count": {
            "label": "Pages",
            "sort_key": "page_count",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "file_type": {
            "label": "Type",
            "sort_key": "file_type",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        # Publishing dates
        "year": {
            "label": "Year",
            "sort_key": "year",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "month": {
            "label": "Month",
            "sort_key": "month",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "day": {
            "label": "Day",
            "sort_key": "day",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "date": {
            "label": "Date",
            "sort_key": "date",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        # Tagging metadata (single-value FKs)
        "country": {
            "label": "Country",
            "sort_key": "country",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "language": {
            "label": "Language",
            "sort_key": "language",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "original_format": {
            "label": "Format",
            "sort_key": "original_format",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "tagger": {
            "label": "Tagger",
            "sort_key": "tagger",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "scan_info": {
            "label": "Scan Info",
            "sort_key": "scan_info",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "age_rating": {
            "label": "Age Rating",
            "sort_key": "age_rating",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "main_character": {
            "label": "Main Character",
            "sort_key": "main_character",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "main_team": {
            "label": "Main Team",
            "sort_key": "main_team",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        # Reader / misc
        "reading_direction": {
            "label": "Reading Direction",
            "sort_key": "reading_direction",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "monochrome": {
            "label": "Monochrome",
            "sort_key": "monochrome",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "critical_rating": {
            "label": "Critical Rating",
            "sort_key": "critical_rating",
            "m2m": False,
            "editable": True,
            # 0.0-5.0 decimal stepper. Renderer wired up by the eventual
            # inline-table edit UI; the dialog editor uses its own input
            # in components/metadata/edit-mode/edit-panel.vue.
            "edit_widget": "decimal",
        },
        # Timestamps
        "created_at": {
            "label": "Added",
            "sort_key": "created_at",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "updated_at": {
            "label": "Updated",
            "sort_key": "updated_at",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "metadata_mtime": {
            "label": "Tags Updated",
            "sort_key": "metadata_mtime",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        "bookmark_updated_at": {
            "label": "Last Read",
            "sort_key": "bookmark_updated_at",
            "m2m": False,
            "editable": False,
            "edit_widget": None,
        },
        # Per-user state. ``favorite`` is the only currently-editable
        # cell — clicking the star toggles via ``PUT|DELETE
        # /api/v4/favorites/<collection>/<pk>``. The annotation
        # ``favorite=Exists(Favorite.objects.filter(user, group,
        # target_id))`` is added in
        # ``BrowserView._add_table_view_favorite_annotation`` for both
        # group and Comic querysets so the column is sortable and
        # renderable across all browsable models.
        "favorite": {
            "label": "Favorite",
            "sort_key": "favorite",
            "m2m": False,
            "editable": True,
            "edit_widget": "checkbox",
        },
        # M2M relations — sortable as of Phase 7 M2M-sort experiment.
        # ``sort_key`` matches the column key so header clicks set
        # ``order_by`` to the same string the backend recognizes.
        "characters": {
            "label": "Characters",
            "sort_key": "characters",
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
        "credits": {
            "label": "Credits",
            "sort_key": "credits",
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
        "genres": {
            "label": "Genres",
            "sort_key": "genres",
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
        "identifiers": {
            "label": "Identifiers",
            "sort_key": "identifiers",
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
        "locations": {
            "label": "Locations",
            "sort_key": "locations",
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
        "series_groups": {
            "label": "Series Groups",
            "sort_key": "series_groups",
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
        "stories": {
            "label": "Stories",
            "sort_key": "stories",
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
        "story_arcs": {
            "label": "Story Arcs",
            "sort_key": "story_arcs",
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
        "tags": {
            "label": "Tags",
            "sort_key": "tags",
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
        "teams": {
            "label": "Teams",
            "sort_key": "teams",
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
        "universes": {
            "label": "Universes",
            "sort_key": "universes",
            "m2m": True,
            "editable": False,
            "edit_widget": None,
        },
    }
)

# Default visible columns per top-group when the user hasn't set
# their own. Layout follows the per-top-group default sort:
# columns referenced by the default ``order_by`` (primary + extras)
# appear first — after ``cover``, which always anchors the row —
# so row content visually tracks the sort order. ``sort_name``
# (the default sort key) maps to the ``name`` column for display
# purposes; ``publisher_name`` / ``imprint_name`` / ``series_name``
# map to their like-named columns. The frontend's
# ``_DEFAULT_TABLE_ORDER`` lookup must stay in sync with this map
# — both define the per-top-group baseline the cancel button and
# the initial-render path lean on.
# Per-column relative cost rating shown next to picker rows so
# users on huge libraries can see at a glance which columns are
# cheap vs. expensive to display + sort. Only non-``low`` entries
# appear here; everything not listed defaults to ``low`` (no badge
# rendered). The rating reflects the worse of display vs. sort
# cost for the column on group-row queries (the most expensive
# query shape):
#
# - ``low`` (default, omitted): the column reads from the group's
#   own field, an already-annotated alias, or batches into the
#   single per-page scalar / FK-name aggregate query. One query
#   regardless of how many low-cost columns are visible.
# - ``medium``: simple-M2M columns whose display batches via the
#   ``UNION ALL`` through-table helper but whose sort still runs a
#   per-outer-row correlated subquery (the ``_build_simple_m2m_…``
#   shape). Display is one query for the whole page; sort scales
#   with the filtered group count when the user clicks the header.
# - ``high``: composite-M2M columns (``credits`` / ``identifiers``
#   / ``universes`` / ``story_arcs``). Display issues its own
#   per-column query (composite display strings can't share the
#   simple-M2M union shape); sort runs a per-outer-row correlated
#   subquery that JOINs the bespoke composite expression. Both
#   display and sort scale with library size when visible.
#
# The frontend renders an icon + tooltip in the column picker for
# medium / high entries; low entries are unannotated.
BROWSER_TABLE_COLUMN_COSTS: MappingProxyType[str, str] = MappingProxyType(
    {
        # Simple M2M — display batches, sort is per-row correlated
        # subquery.
        "characters": "medium",
        "genres": "medium",
        "locations": "medium",
        "series_groups": "medium",
        "stories": "medium",
        "tags": "medium",
        "teams": "medium",
        # Composite M2M — display + sort both per-column / per-row.
        "credits": "high",
        "identifiers": "high",
        "story_arcs": "high",
        "universes": "high",
    }
)


BROWSER_TABLE_DEFAULT_COLUMNS = MappingProxyType(
    {
        # Sort: sort_name. → name first.
        "p": ("cover", "name", "child_count"),
        # Sort: publisher_name, sort_name. → publisher_name, name.
        "i": ("cover", "publisher_name", "name", "child_count"),
        # Sort: publisher_name, imprint_name, sort_name.
        "s": (
            "cover",
            "publisher_name",
            "imprint_name",
            "name",
            "year",
            "child_count",
        ),
        # Sort: publisher_name, imprint_name, series_name, sort_name
        # (Volume.sort_name expands to ``name, number_to``).
        "v": (
            "cover",
            "publisher_name",
            "imprint_name",
            "series_name",
            "name",
            "year",
            "child_count",
        ),
        # Sort: sort_name (Comic's sort_name expands inside
        # ``_add_comic_order_by`` to publisher_sort_name →
        # imprint_sort_name → series_sort_name → volume_name →
        # volume_number_to → issue_number → issue_suffix →
        # collection_title → sort_name). The visible column set
        # mirrors that ladder so the row order tracks the sort.
        "c": (
            "cover",
            "publisher_name",
            "imprint_name",
            "series_name",
            "volume_name",
            "issue",
            "name",
            "year",
            "page_count",
            "size",
        ),
        # Sort: sort_name. Folder rows show their own name first.
        "f": ("cover", "name", "child_count"),
        # Sort: sort_name. Story arc rows show their own name first.
        "a": ("cover", "name", "publisher_name", "child_count"),
    }
)

BROWSER_DEFAULTS = MappingProxyType(
    {
        "custom_covers": True,
        "dynamic_covers": True,
        "filters": _DEFAULT_FILTERS,
        "order_by": "sort_name",
        "order_reverse": False,
        "order_extra_keys": (),
        "search": "",
        "show": _DEFAULT_SHOW,
        "top_group": "p",
        "twenty_four_hour_time": False,
        "always_show_filename": False,
        "last_route": DEFAULT_BROWSER_ROUTE,
        "view_mode": "cover",
        "table_columns": {},
        "table_cover_size": "sm",
    }
)

DUMMY_NULL_NAME = "_none_"
