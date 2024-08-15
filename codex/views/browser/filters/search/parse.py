"""Search Filters Methods."""

import re
import shlex

from codex.logger.logging import get_logger
from codex.models.comic import ComicFTS
from codex.views.browser.filters.search.fts import BrowserFTSFilter

LOG = get_logger(__name__)
_FTS_COLUMNS = frozenset(
    {field.name for field in ComicFTS._meta.get_fields()}
    - {"comic", "updated_at", "created_at"}
)
_NON_FTS_COLUMNS = frozenset(
    {
        "created_at",
        "updated_at",
        "path",
        "sort_name",
        "issue_number",
        "issue_suffix",
        "year",
        "month",
        "day",
        "community_rating",
        "criticial_rating",
        "page_count",
        "monochrome",
        "date",
        "decade",
        "size",
    }
)
_VALID_COLUMNS = frozenset(_FTS_COLUMNS | _NON_FTS_COLUMNS)
_EXPRESSION_OPERATOR_RE = re.compile(r"^[\*\!\<\>]")
_FTS_OPERATORS = frozenset({"or", "and", "not", "near"})


class SearchFilterView(BrowserFTSFilter):
    """Search Query Parser."""

    def _preparse_token(self, token, field_tokens, fts_tokens):
        """Preparse one search token."""
        if not token:
            return
        parts = token.split(":")
        if len(parts) > 1:
            col, exp = parts
            if col not in _VALID_COLUMNS:
                return
            if col in _NON_FTS_COLUMNS or _EXPRESSION_OPERATOR_RE.search(exp):
                field_tokens.add((col, exp))
                return

        # Allow lowercase FTS operators
        cased_token = token.upper() if token.lower() in _FTS_OPERATORS else token
        fts_tokens.append(cased_token)

    def _preparse_search_query(self):
        """Preparse search fields out of query text."""
        q = self.params.get("q")  # type: ignore
        field_tokens = set()
        if not q:
            return field_tokens, q

        tokens = shlex.split(q)
        fts_tokens = []
        for token in tokens:
            self._preparse_token(token, field_tokens, fts_tokens)

        preparsed_search_query = " ".join(fts_tokens).strip()
        return field_tokens, preparsed_search_query

    def apply_search_filter(self, qs, model):
        """Preparse search, search and return the filter and scores."""
        try:
            field_tokens, text = self._preparse_search_query()
            qs = self.apply_field_query_filters(qs, model, field_tokens)
            qs = self.apply_fts_filter(qs, model, text)
        except Exception:
            LOG.exception("Creating the search filter")

        return qs
