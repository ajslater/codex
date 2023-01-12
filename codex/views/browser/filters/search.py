"""Search Filters Methods."""
import re

from dateutil.parser import ParserError
from dateutil.parser import parse as du_parse
from django.db.models import Q
from haystack.query import SearchQuerySet
from humanfriendly import InvalidSize, parse_size
from xapian_backend import DATETIME_FORMAT

from codex.librarian.queue_mp import LIBRARIAN_QUEUE
from codex.librarian.search.tasks import SearchIndexJanitorUpdateTask
from codex.settings.logging import get_logger
from codex.views.browser.filters.bookmark import BookmarkFilterMixin


LOG = get_logger(__name__)


class SearchFilterPreparserMixin(BookmarkFilterMixin):
    """Preparse Search query text."""

    # Ideally this would be part of a custom XapianBackend

    DATE_FORMAT = DATETIME_FORMAT.removesuffix("%H%M%S")
    RANGE_OPERATOR_LT_RE = re.compile("^<=?")
    RANGE_OPERATOR_GT_RE = re.compile("^>=?")
    RANGE_DELIMITER = ".."

    _SEARCH_FIELD_ALIASES = {
        "ltr": "read_ltr",
        "title": "name",
        "scan": "scan_info",
        "character": "characters",
        "creator": "creators",
        "created": "created_at",
        "finished": "read",
        "genre": "genres",
        "location": "locations",
        "reading": "in_progress",
        "series_group": "series_groups",
        "story_arc": "story_arcs",
        "tag": "tags",
        "team": "teams",
        "updated": "updated_at",
        # OPDS
        "author": "creators",
        "contributor": "creators",
        "category": "characters",  # the most common category, probably
    }

    @staticmethod
    def _parse_datetime(value, format=DATETIME_FORMAT):
        """Parse liberal datetime values."""
        try:
            dttm = du_parse(value, fuzzy=True)
            value = dttm.strftime(format)
        except (OverflowError, ParserError) as exc:
            LOG.debug(exc)
            value = ""
        except Exception as exc:
            LOG.warning(exc)
            LOG.exception(exc)
            value = ""
        return value

    @classmethod
    def _parse_date(cls, value):
        """Parse liberal date values."""
        return cls._parse_datetime(value, format=cls.DATE_FORMAT)

    @staticmethod
    def _parse_size(value):
        """Parse humanized file size values."""
        try:
            size = str(parse_size(value))
        except InvalidSize as exc:
            LOG.debug(exc)
            size = ""
        except Exception as exc:
            LOG.warning(exc)
            LOG.exception(exc)
            size = ""
        return size

    @classmethod
    def _parse_search_token_value(cls, convert_func, token_value):
        """Parse a token value."""
        try:
            token_value_bits = []
            for token_value_bit in token_value.split(cls.RANGE_DELIMITER):
                if token_value_bit in ("", "*"):
                    token_value_bits.append(token_value_bit)
                    continue
                xapian_value_str = convert_func(token_value_bit)
                token_value_bits.append(xapian_value_str)
            token_value = cls.RANGE_DELIMITER.join(token_value_bits)
        except Exception as exc:
            LOG.warning(exc)
            LOG.exception(exc)
        return token_value

    @classmethod
    def _alias_token_field(cls, token_field):
        """Alias field searches."""
        # TODO: could add to XapianSearchBackend.parse()
        # TODO: look for how to add Synonyms
        index_token_field = cls._SEARCH_FIELD_ALIASES.get(token_field)
        if index_token_field:
            token_field = index_token_field
        return token_field

    @classmethod
    def _parse_range_value(cls, token_value):
        """Parse custom range values."""
        # Range TODO: patch XHValueRangeProcessor
        token_value = cls.RANGE_OPERATOR_LT_RE.sub(
            cls.RANGE_DELIMITER, token_value, count=1
        )
        token_value, number_of_subs_made = cls.RANGE_OPERATOR_GT_RE.subn(
            "", token_value, count=1
        )
        if number_of_subs_made:
            token_value += cls.RANGE_DELIMITER + "*"
        # TODO: patch XHValueRangeProcessor
        # Fix a haystack xapian-backend.XHValueRangeProcessor range bug?
        # https://github.com/notanumber/xapian-haystack/issues/217
        if token_value.endswith(cls.RANGE_DELIMITER):
            token_value += "*"
        return token_value

    @classmethod
    def _parse_special_values(cls, token_field, token_value):
        """Parse Dates, Datetimes, and File Size."""
        # TODO: patch xapian-backend._term_to_xapian_value
        if token_field == "date":
            token_value = cls._parse_search_token_value(cls._parse_date, token_value)
        elif token_field in ("updated_at", "created_at"):
            token_value = cls._parse_search_token_value(
                cls._parse_datetime, token_value
            )
        elif token_field == "size":
            token_value = cls._parse_search_token_value(cls._parse_size, token_value)
        return token_value

    @classmethod
    def _parse_token(cls, token):
        """Convert aliased search fields and extract the bookmark query."""
        try:
            # Parse token as a field
            token_parts = token.split(":")
            token_field = token_parts[0]
            if len(token_parts) > 1:
                token_value = token_parts[1]
            else:
                token_value = ""

            token_field = cls._alias_token_field(token_field)

            if token_value:
                # is a field
                token_value = cls._parse_range_value(token_value)
                token_value = cls._parse_special_values(token_field, token_value)

            if token_field and token_value:
                token = ":".join((token_field, token_value))
            else:
                token = token_field
        except ValueError as exc:
            LOG.warning(exc)
            LOG.exception(exc)
            pass

        return token

    def _preparse_query_text(self):
        """Preprocess query string by aliasing fields and extracting bookmark query."""
        haystack_tokens = []

        query_tokens = self.params.get("q", "").split(" ")  # type: ignore
        for token in query_tokens:
            if not token:
                continue

            if token.find(":") and not (token.startswith('"') and token.endswith('"')):
                # is a field search token
                token = self._parse_token(token)

            if token:
                haystack_tokens.append(token)

        haystack_text = " ".join(haystack_tokens)
        return haystack_text


class SearchFilterMixin(SearchFilterPreparserMixin):
    """Search Filters Methods."""

    def _get_search_scores(self, text):
        """Perform the search and return the scores as a dict."""
        sqs = SearchQuerySet().auto_query(text)
        comic_scores = sqs.values("pk", "score")
        search_scores = {}
        for comic_score in comic_scores:
            search_scores[comic_score["pk"]] = comic_score["score"]

        search_engine_out_of_date = False
        if search_engine_out_of_date:
            LOG.warning("Search index out of date. Scoring non-existent comics.")
            task = SearchIndexJanitorUpdateTask(False)
            LIBRARIAN_QUEUE.put(task)
        return search_scores

    def _get_search_query_filter(self, text, is_model_comic):
        """Get the search filter and scores."""
        search_filter = Q()
        if not text:
            return search_filter, {}

        # Get search scores
        search_scores = self._get_search_scores(text)

        # Create query
        prefix = ""
        if not is_model_comic:
            prefix = "comic__"
        query_dict = {f"{prefix}pk__in": search_scores.keys()}
        search_filter = Q(**query_dict)

        return search_filter, search_scores

    def get_search_filter(self, is_model_comic):
        """Preparse search, search and return the filter and scores."""
        try:
            # Parse out the bookmark filter and get the remaining tokens
            haystack_text = self._preparse_query_text()

            # Query haystack
            (
                search_filter,
                search_scores,
            ) = self._get_search_query_filter(haystack_text, is_model_comic)
        except Exception as exc:
            LOG.warning(exc)
            search_filter = Q()
            search_scores = {}

        return search_filter, search_scores
