"""Search Filters Methods."""

import shlex

from codex.logger.logging import get_logger
from codex.views.browser.filters.search.fts import BrowserFTSFilter

LOG = get_logger(__name__)


class SearchFilterView(BrowserFTSFilter):
    """Search Query Parser."""

    def _preparse_search_query(self):
        """Preparse search fields out of query text."""
        q = self.params.get("q")  # type: ignore
        field_tokens = set()
        if not q:
            return field_tokens, q

        parts = shlex.split(q)
        fts_tokens = []
        for part in parts:
            if ":" in part:
                field_tokens.add(part)
            elif part:
                # Allow lowercase FTS operators
                preparsed_part = (
                    part.upper() if part.lower() in ("or", "not", "and") else part
                )
                fts_tokens.append(preparsed_part)

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
