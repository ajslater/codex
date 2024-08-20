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
_COLUMN_EXPRESSION_OPERATORS_RE = re.compile(r"^[\*\!\<\>]")
_FTS_OPERATORS = frozenset({"and", "not", "or", "near"})
_FTS_BARE_TOKENS = "(),"
_FTS_PAREN_COMMAS_RE = re.compile(r"([()|])")
_FTS_MULTI_COL_RE = re.compile(r"{.*}:")
_QUOTED_RE = re.compile(r'^".*"$|^\'.*\'$')


class SearchFilterView(BrowserFTSFilter):
    """Search Query Parser."""

    def _preparse_paren_commas(self, token, field_tokens, fts_tokens):
        """Not a column token, but has grouping chars."""
        # Surround parents and commas with spaces and re shlex and parse them.
        sub_phrase = _FTS_PAREN_COMMAS_RE.sub(r" \g<1> ", token)
        tokens = shlex.split(sub_phrase)
        for sub_token in tokens:
            self._preparse_token(sub_token, field_tokens, fts_tokens)

    @staticmethod
    def _quote_token(token):
        """Quote most tokens to allow special characters."""
        # but preserve prefix star notation
        suffix = ""
        while token.endswith("*"):
            suffix = "*"
            token = token[:-1]
        return f'"{token}"{suffix}'

    @classmethod
    def _preparse_column_search(cls, token, field_tokens, fts_tokens):
        """Preparse column search."""
        column_parts = token.split(":", 1)
        if len(column_parts) <= 1:
            return False
        # Column token
        col, exp = column_parts
        if col not in _VALID_COLUMNS:
            return True
        if col in _NON_FTS_COLUMNS or _COLUMN_EXPRESSION_OPERATORS_RE.search(exp):
            field_tokens.add((col, exp))
            return True

        exp = cls._quote_token(exp)
        token = ":".join((col, exp))
        fts_tokens.append(token)
        return True

    def _preparse_token(self, token, field_tokens, fts_tokens):
        """Preparse one search token."""
        if not token:
            return

        if token.lower() in _FTS_OPERATORS:
            # Allow lowercase FTS operators
            token = token.upper()
        elif (
            token not in _FTS_BARE_TOKENS
            and not token.isdigit()
            and not _QUOTED_RE.search(token)
        ):
            if self._preparse_column_search(token, field_tokens, fts_tokens):
                return
                # Else send the column token to fts
            if _FTS_PAREN_COMMAS_RE.search(token):
                self._preparse_paren_commas(token, field_tokens, fts_tokens)
                return
            token = self._quote_token(token)

        fts_tokens.append(token)

    def _preparse_search_query(self):
        """Preparse search fields out of query text."""
        q = self.params.get("q")  # type: ignore
        field_tokens = set()
        if not q:
            return field_tokens, q

        # Remove multi column specifiers rather than accommodating them.
        # For simplicity
        q = _FTS_MULTI_COL_RE.sub("", q)

        tokens = shlex.split(q)
        fts_tokens = []
        for token in tokens:
            self._preparse_token(token, field_tokens, fts_tokens)

        text = " ".join(fts_tokens)
        return field_tokens, text

    def apply_search_filter(self, qs, model):
        """Preparse search, search and return the filter and scores."""
        try:
            field_tokens, text = self._preparse_search_query()
            qs = self.apply_field_query_filters(qs, model, field_tokens)
            qs = self.apply_fts_filter(qs, model, text)
        except Exception:
            LOG.exception("Creating the search filter")

        return qs
