"""Search Filters Methods."""

import re
from functools import cached_property, lru_cache
from types import MappingProxyType

from django.db.models.query_utils import Q
from loguru import logger

from codex.choices.admin import AdminFlagChoices
from codex.choices.search import FIELDMAP
from codex.models import AdminFlag
from codex.models.comic import Comic, ComicFTS
from codex.settings.db import get_browser_max_obj_per_page
from codex.views.browser.filters.search.fts import BrowserFTSFilter

# Targets whose statements carry the search filter at most twice (the
# main query plus the cover subquery), so a materialized pk IN-list is
# safe under SQLite's 32,766-variable limit with the cap below.
# choices/metadata statements repeat the filter per probe arm and must
# keep the constant-size MATCH form.
_FTS_PK_SWAP_TARGETS = frozenset({"browser", "mtime"})
# Half the variable limit, allowing two list copies per statement.
_FTS_PK_SWAP_MAX = 15_000

_FTS_COLUMNS = frozenset(
    {field.name for field in ComicFTS._meta.get_fields()}
    - {"comic", "updated_at", "created_at"}
)
_NON_FTS_COLUMNS = frozenset(
    {
        "created_at",
        "critical_rating",
        "date",
        "day",
        "decade",
        "file_type",
        "identifiers",
        "issue",
        "issue_number",
        "issue_suffix",
        "main_character",
        "main_team",
        "month",
        "monochrome",
        "notes",
        "path",
        "page_count",
        "reading_direction",
        "size",
        "updated_at",
        "volume",
        "volume_to",
        "year",
    }
)
_VALID_COLUMNS = frozenset(_FTS_COLUMNS | _NON_FTS_COLUMNS)
_QUOTES_REXP = r"\".*?\""
_COLUMN_EXPRESSION_OPERATORS_REXP = (
    rf"(?:{_QUOTES_REXP})|(?P<star>\B[\*\<\>]\w|\.{(2,)}|\w\*\w)"
)
_COLUMN_EXPRESSION_OPERATORS_RE = re.compile(_COLUMN_EXPRESSION_OPERATORS_REXP)
_FTS_OPERATORS = frozenset({"and", "not", "or", "near"})
_FTS_OPERATOR_REXP = rf"(?P<operator>\b{'|'.join(_FTS_OPERATORS)}\b)"
_FTS_OPERATOR_RE = re.compile(_FTS_OPERATOR_REXP, flags=re.IGNORECASE)
_MULTI_COL_REXP = r"(?P<multi_col>\{.*?\})"
_SINGLE_COL_REXP = r"(?P<col>[a-z_]+)"
_EXP_REXP = rf"\s*(?P<exp>\(.*?\)|{_QUOTES_REXP}|\S+)"
_COL_REXP = rf"({_MULTI_COL_REXP}|{_SINGLE_COL_REXP}):{_EXP_REXP}"
_TOKEN_PRE_OP_REXP = r"(?:(?P<preop>and|or|not)\s+)?"  # noqa: S105
_TOKEN_REXP = rf"(?P<token>{_TOKEN_PRE_OP_REXP}{_COL_REXP}|\S+)"
_TOKEN_RE = re.compile(_TOKEN_REXP, flags=re.IGNORECASE)
_ALIAS_FIELD_MAP = MappingProxyType(
    {value: key for key, values in FIELDMAP.items() for value in values}
)
# Compound aliases expand into OR queries across multiple columns.
# Individual aliases (protag, lead) are resolved to "protagonist" by
# _ALIAS_FIELD_MAP via FIELDMAP before reaching this map.
_COMPOUND_COLUMN_MAP = MappingProxyType(
    {
        "protagonist": ("main_character", "main_team"),
    }
)


def _is_column_operators_used(exp) -> bool:
    """Detect column expression operators, but not inside quotes."""
    for match in _COLUMN_EXPRESSION_OPERATORS_RE.finditer(exp):
        if match.group("star"):
            return True
    return False


def _add_field_token(preop, col, exp, field_tokens) -> None:
    """Add a field token entry with the given preop."""
    if not preop:
        preop = "and"
    if preop not in field_tokens:
        field_tokens[preop] = set()
    field_tokens[preop].add((col, exp))


def _add_fts_token(fts_tokens, token) -> None:
    token = _FTS_OPERATOR_RE.sub(lambda op: op.group("operator").upper(), token)

    if ":" in token:
        col, value = token.split(":")
        col = _ALIAS_FIELD_MAP.get(col.lower(), col)
        token = f"{col}:{value}"
    elif token.lower() not in _FTS_OPERATORS and not (
        token.startswith('"') and token.endswith('"')
    ):
        token = f'"{token}"'

    fts_tokens.append(token)


def _parse_column_match(preop, col, exp, field_tokens, *, path_allowed) -> bool:
    col = _ALIAS_FIELD_MAP.get(col.lower(), col.lower())

    # Compound aliases expand into OR queries across multiple columns.
    # Store the tuple of cols as the field_token key; filter.py ORs them.
    if compound_cols := _COMPOUND_COLUMN_MAP.get(col):
        _add_field_token(preop, compound_cols, exp, field_tokens)
        return True

    if col not in _VALID_COLUMNS:
        return True
    if col == "path" and not path_allowed:
        return True
    if col in _NON_FTS_COLUMNS or _is_column_operators_used(exp):
        _add_field_token(preop, col, exp, field_tokens)
        return True
    return False


def _preparse_token(match, field_tokens, fts_tokens, *, path_allowed) -> None:
    token = match.group("token")
    if not token:
        return

    multi_col = match.group("multi_col")
    col = match.group("col")
    exp = match.group("exp")
    if exp:
        exp = exp.strip("'").strip('"')
    if multi_col or not col or not exp:
        # I could add multi-col to field groups, but nobody will care.
        _add_fts_token(fts_tokens, token)
        return

    preop = match.group("preop")
    if not _parse_column_match(
        preop, col, exp, field_tokens, path_allowed=path_allowed
    ):
        if col and exp:
            token = f"{col}:{exp}"
        _add_fts_token(fts_tokens, token)


@lru_cache(maxsize=256)
def _preparse_search_query_cached(
    text: str,
    path_allowed: bool,  # noqa: FBT001
) -> tuple[MappingProxyType, str, bool]:
    """
    Parse query text into field tokens and an FTS remainder.

    Pure function keyed on ``(text, path_allowed)``. Returns a
    ``MappingProxyType`` wrapping a dict of ``frozenset`` pairs so the
    cached value stays safe from caller mutation. ``had_error`` lets the
    caller mirror the previous side effect on ``self.search_error``
    without polluting the cache.
    """
    field_tokens: dict = {}
    fts_tokens: list = []
    had_error = False
    for match in _TOKEN_RE.finditer(text):
        try:
            _preparse_token(match, field_tokens, fts_tokens, path_allowed=path_allowed)
        except Exception as exc:
            tok = match.group(0) if match else "<unmatched>"
            logger.debug(f"Error preparsing search query token {tok}: {exc}")
            had_error = True
    fts_text = " ".join(fts_tokens)
    frozen_tokens = MappingProxyType(
        {preop: frozenset(pairs) for preop, pairs in field_tokens.items()}
    )
    return frozen_tokens, fts_text, had_error


class SearchFilterView(BrowserFTSFilter):
    """Search Query Parser."""

    ADMIN_FLAGS: tuple[AdminFlagChoices, ...] = (AdminFlagChoices.FOLDER_VIEW,)

    def __init__(self, *args, **kwargs) -> None:
        """Initialize search variables."""
        super().__init__(*args, **kwargs)
        self._admin_flags: MappingProxyType[str, bool] | None = None
        self.fts_mode = False
        self.search_mode = False
        self.search_error = ""
        # True when the FTS filter was swapped for the materialized
        # pk-set; the cover subquery reads it to skip its own wrap.
        self.fts_q_is_pk_set = False

    @property
    def admin_flags(self) -> MappingProxyType[str, bool]:
        """Set browser relevant admin flags."""
        if self._admin_flags is None:
            if self.ADMIN_FLAGS:
                admin_pairs = AdminFlag.objects.filter(
                    key__in=(enum.value for enum in self.ADMIN_FLAGS)
                ).values_list("key", "on")
            else:
                admin_pairs = ()
            admin_flags = {}
            for key, on in admin_pairs:
                export_key = AdminFlagChoices(key).name.lower()
                admin_flags[export_key] = on
            self._admin_flags = MappingProxyType(admin_flags)
        return self._admin_flags

    def _is_path_column_allowed(self) -> bool:
        """Is path column allowed."""
        return self.is_admin or bool(self.admin_flags["folder_view"])

    def _preparse_search_query(self) -> tuple:
        """Preparse search fields out of query text."""
        text = self.params.get("search")
        if not text:
            return {}, text

        field_tokens, fts_text, had_error = _preparse_search_query_cached(
            text, self._is_path_column_allowed()
        )
        if had_error:
            self.search_error = "Syntax error"
        return field_tokens, fts_text

    @cached_property
    def _fts_match_pks(self) -> tuple[int, ...] | None:
        """
        Comic pks matching the FTS query, materialized once per request.

        The raw MATCH otherwise re-executes the FTS5 scan in every
        statement that carries the filter (counts, mtime probe,
        pagination, intersections — 5-6 scans per browse request,
        measured ~870ms of a 1.3s search request at 17k matches). One
        Python-side materialization makes the rest indexed IN-list
        membership tests. Returns None (keep raw MATCH) for very large
        match sets — the list binds one SQL variable per pk and may
        appear twice per statement (main query + cover subquery).
        """
        _, fts_text = self._preparse_search_query()
        if not fts_text:
            return None
        pks = tuple(
            Comic.objects.filter(comicfts__match=fts_text).values_list("pk", flat=True)
        )
        if len(pks) > _FTS_PK_SWAP_MAX:
            return None
        return pks

    @property
    def _fts_swap_allowed(self) -> bool:
        """True when this view's statements may swap MATCH for the pk-list."""
        # Rank-ordered requests need MATCH active in the scored statement
        # to resolve ComicFTSRank; choices/metadata repeat the filter per
        # probe arm (variable-limit hazard) and keep the subquery form.
        return self.TARGET in _FTS_PK_SWAP_TARGETS and (
            getattr(self, "order_key", None) != "search_score"
        )

    def _create_search_filters(self, model) -> tuple[list, list, Q]:
        field_tokens_dict, fts_text = self._preparse_search_query()
        field_filter_q_list = []
        field_exclude_q_list = []
        for preop, field_token_pairs in field_tokens_dict.items():
            if preop == "not":
                exclude_q_list, include_q_list = self.get_search_field_filters(
                    model, field_token_pairs
                )
            else:
                # AND and OR
                # Cannot do OR queries with MATCH, it decontextualizes MATCH somehow.
                if preop == "or":
                    self.search_error = "OR preceding column tokens with operator expressions will act as AND"
                include_q_list, exclude_q_list = self.get_search_field_filters(
                    model, field_token_pairs
                )
            field_filter_q_list += include_q_list
            field_exclude_q_list += exclude_q_list

        fts_filter_dict = self.get_fts_filter(model, fts_text)
        if fts_filter_dict:
            self.fts_mode = True
            fts_q = Q(**fts_filter_dict)
            if self._fts_swap_allowed and (pks := self._fts_match_pks) is not None:
                fts_q = Q(**{self.get_rel_prefix(model) + "pk__in": pks})
                self.fts_q_is_pk_set = True
        else:
            fts_q = Q()

        return field_filter_q_list, field_exclude_q_list, fts_q

    def _create_search_filter(self, filter_list) -> Q:
        """Apply search filter lists. Separate filter clauses are employed for m2m searches."""
        combined_q = Q()
        for q in filter_list:
            if not q:
                continue
            combined_q &= q
            self.search_mode = True

        return combined_q

    def get_search_filters(self, model) -> tuple[Q, Q, Q]:
        """Preparse search, search and return the filter and scores."""
        include_q = Q()
        exclude_q = Q()
        fts_q = Q()
        try:
            field_filter_q_list, field_exclude_q_list, fts_q = (
                self._create_search_filters(model)
            )
            # Apply filters
            include_q = self._create_search_filter(field_filter_q_list)
            exclude_q = self._create_search_filter(field_exclude_q_list)

        except Exception as exc:
            msg = "Creating search filters"
            logger.exception(msg)
            msg = f"{msg} - {exc}"
            self.search_error = msg

        return include_q, exclude_q, fts_q

    def get_search_limit(self) -> int:
        """Get search scores for choices and metadata."""
        if not self.search_mode:
            return 0
        page = self.kwargs.get("page", 1)
        return page * get_browser_max_obj_per_page() + 1
