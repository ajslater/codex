"""Search Filters Methods."""

import re
from types import MappingProxyType

from django.db.models.query import Q

from codex.logger.logging import get_logger
from codex.models import AdminFlag
from codex.models.comic import ComicFTS
from codex.views.browser.filters.search.aliases import ALIAS_FIELD_MAP
from codex.views.browser.filters.search.fts import BrowserFTSFilter
from codex.views.const import MAX_OBJ_PER_PAGE

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
_QUOTES_REXP = r"\".*?\""
_COLUMN_EXPRESSION_OPERATORS_REXP = (
    rf"(?:{_QUOTES_REXP})|(?P<star>\B[\*\<\>]\w|\.{2,}|\w\*\w)"
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


class SearchFilterView(BrowserFTSFilter):
    """Search Query Parser."""

    ADMIN_FLAG_VALUE_KEY_MAP = MappingProxyType(
        {
            AdminFlag.FlagChoices.FOLDER_VIEW.value: "folder_view",
        }
    )

    def __init__(self, *args, **kwargs):
        """Initialize search variables."""
        super().__init__(*args, **kwargs)
        self._admin_flags: MappingProxyType[str, bool] | None = None
        self.fts_mode = False
        self.search_mode = False
        self.search_error = ""

    @property
    def admin_flags(self) -> MappingProxyType[str, bool]:
        """Set browser relevant admin flags."""
        if self._admin_flags is None:
            if self.ADMIN_FLAG_VALUE_KEY_MAP:
                admin_pairs = AdminFlag.objects.filter(
                    key__in=self.ADMIN_FLAG_VALUE_KEY_MAP.keys()
                ).values_list("key", "on")
            else:
                admin_pairs = ()
            admin_flags = {}
            for key, on in admin_pairs:
                export_key = self.ADMIN_FLAG_VALUE_KEY_MAP[key]
                admin_flags[export_key] = on
            self._admin_flags = MappingProxyType(admin_flags)
        return self._admin_flags

    def _is_path_column_allowed(self):
        """Is path column allowed."""
        return self.is_admin or bool(self.admin_flags["folder_view"])

    @staticmethod
    def _is_column_operators_used(exp) -> bool:
        """Detect column expression operators, but not inside quotes."""
        for match in _COLUMN_EXPRESSION_OPERATORS_RE.finditer(exp):
            if match.group("star"):
                return True
        return False

    def _parse_column_match(self, preop, col, exp, field_tokens):  # , fts_tokens):
        col = ALIAS_FIELD_MAP.get(col, col)
        if col not in _VALID_COLUMNS:
            return True
        if col == "path" and not self._is_path_column_allowed():
            return True
        if col in _NON_FTS_COLUMNS or self._is_column_operators_used(exp):
            if not preop:
                preop = "and"
            if preop not in field_tokens:
                field_tokens[preop] = set()
            field_tokens[preop].add((col, exp))
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

    def _preparse_search_query_token(self, match, field_tokens, fts_tokens):
        token = match.group("token")
        if not token:
            return

        multi_col = match.group("multi_col")
        col = match.group("col")
        exp = match.group("exp")
        if multi_col or not col or not exp:
            # I could add multi-col to field groups, but nobody will care.
            self._add_fts_token(fts_tokens, token)
            return

        preop = match.group("preop")
        if not self._parse_column_match(preop, col, exp, field_tokens):
            self._add_fts_token(fts_tokens, token)

    def _preparse_search_query(self):
        """Preparse search fields out of query text."""
        text = self.params.get("q")  # type: ignore
        field_tokens = {}
        if not text:
            return field_tokens, text

        fts_tokens = []
        for match in _TOKEN_RE.finditer(text):
            try:
                self._preparse_search_query_token(match, field_tokens, fts_tokens)
            except Exception as exc:
                tok = match.group(0) if match else "<unmatched>"
                LOG.debug(f"Error preparsing search query token {tok}: {exc}")
                self.search_error = "Syntax error"
        text = " ".join(fts_tokens)

        return field_tokens, text

    def _create_search_filters(self, model):
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
                # XXX cannot do OR queries with MATCH, it decontextualizes MATCH somehow.
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
        else:
            fts_q = Q()

        return field_filter_q_list, field_exclude_q_list, fts_q

    def _create_search_filter(self, filter_list):
        """Apply search filter lists. Separate filter clauses are employed for m2m searches."""
        combined_q = Q()
        for q in filter_list:
            if not q:
                continue
            combined_q &= q
            self.search_mode = True

        return combined_q

    def get_search_filters(self, model):
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
            LOG.exception(msg)
            msg = f"{msg} - {exc}"
            self.search_error = msg

        return include_q, exclude_q, fts_q

    def _is_search_results_limited(self) -> bool:
        """Get search result limit from params."""
        # user = self.request.user  # type: ignore
        # if user and user.is_authenticated:
        #    limited = bool(
        #        self.params.get(  # type: ignore
        #            "search_results_limit",
        #            MAX_OBJ_PER_PAGE,
        #        )
        #    )
        # else:
        #    limited = True
        # return limited
        return True

    def get_search_limit(self):
        """Get search scores for choices and metadata."""
        if not self.search_mode or not self._is_search_results_limited():
            return 0
        page = self.kwargs.get("page", 1)  # type: ignore
        return page * MAX_OBJ_PER_PAGE + 1
