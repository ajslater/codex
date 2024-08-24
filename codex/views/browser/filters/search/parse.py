"""Search Filters Methods."""

import re

from codex.logger.logging import get_logger
from codex.models.comic import ComicFTS
from codex.views.browser.filters.search.aliases import ALIAS_FIELD_MAP
from codex.views.browser.filters.search.fts import BrowserFTSFilter

LOG = get_logger(__name__)
_FTS_COLUMNS = frozenset(
    {field.name for field in ComicFTS._meta.get_fields()}
    - {"comic", "updated_at", "created_at"}
)
_NON_FTS_COLUMNS = frozenset(
    {
        "volume",
        "created_at",
        "updated_at",
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
        "path",
        "identifier",
        "identifier_type",
    }
)
_VALID_COLUMNS = frozenset(_FTS_COLUMNS | _NON_FTS_COLUMNS)
_COLUMN_EXPRESSION_OPERATORS_RE = re.compile(r"\B[\*\!\<\>]\w|\.{2,}|\w\*\w")
_FTS_OPERATORS = frozenset({"and", "not", "or", "near"})
_FTS_OPERATOR_REXP = rf"(?P<operator>\b{'|'.join(_FTS_OPERATORS)}\b)"
_FTS_OPERATOR_RE = re.compile(_FTS_OPERATOR_REXP, flags=re.IGNORECASE)
_MULTI_COL_REXP = r"(?P<multi_col>\{.*?\})"
_SINGLE_COL_REXP = r"(?P<col>\w+)"
_EXP_REXP = r"(?P<exp>\s*\(.*?\)|\S+)"
_COL_REXP = rf"({_MULTI_COL_REXP}|{_SINGLE_COL_REXP}):{_EXP_REXP}"
_TOKEN_REXP = rf"(?P<token>{_COL_REXP}|\S+)"
_TOKEN_RE = re.compile(_TOKEN_REXP, flags=re.IGNORECASE)


class SearchFilterView(BrowserFTSFilter):
    """Search Query Parser."""

    def _is_path_column_allowed(self):
        """Is path column allowed."""
        if not self.is_admin():  # type: ignore
            if not "folder_view" not in self.admin_flags:  # type: ignore
                # Ensure admin flags for Cover View
                self.set_admin_flags()  # type: ignore
            return bool(self.admin_flags.get("folder_view"))  # type: ignore
        return True

    @staticmethod
    def _is_column_operators_used(exp):
        """Detect column expression operators, but not inside quotes."""
        # TODO optimize regex
        clean_exp = re.sub(r"\".*?\"", "", exp)
        return _COLUMN_EXPRESSION_OPERATORS_RE.search(clean_exp)

    def _parse_column_match(self, col, exp, field_tokens):  # , fts_tokens):
        col = ALIAS_FIELD_MAP.get(col, col)
        if col not in _VALID_COLUMNS:
            return True
        if col == "path" and not self._is_path_column_allowed():
            return True
        if col in _NON_FTS_COLUMNS or self._is_column_operators_used(exp):
            field_tokens.add((col, exp))
            return True

        return False

    @staticmethod
    def _add_fts_token(fts_tokens, token):
        token = _FTS_OPERATOR_RE.sub(lambda op: op.group("operator").upper(), token)
        if (
            token.lower() not in _FTS_OPERATORS
            and not (token.startswith('"') and token.endswith('"'))
            and ":" not in token
        ):
            token = f'"{token}"'
        fts_tokens.append(token)

    def _preparse_search_query(self):
        """Preparse search fields out of query text."""
        text = self.params.get("q")  # type: ignore
        field_tokens = set()
        if not text:
            return field_tokens, text

        fts_tokens = []
        for match in _TOKEN_RE.finditer(text):
            token = match.group("token")
            if not token:
                continue

            multi_col = match.group("multi_col")
            col = match.group("col")
            exp = match.group("exp")
            if multi_col or not col or not exp:
                # XXX Could add mulit-col to field groups, but nobody will care.
                self._add_fts_token(fts_tokens, token)
                continue

            if not self._parse_column_match(col, exp, field_tokens):  # , fts_tokens):
                self._add_fts_token(fts_tokens, token)

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
