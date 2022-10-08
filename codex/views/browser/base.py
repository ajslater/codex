"""Views for browsing comic library."""
import json

from copy import deepcopy
from distutils.util import strtobool
from urllib.parse import unquote_plus

from dateutil.parser import parse as du_parse
from django.contrib.auth.models import User
from django.db.models import F, Q
from django.db.models.functions import Now
from djangorestframework_camel_case.settings import api_settings
from djangorestframework_camel_case.util import underscoreize
from haystack.query import SearchQuerySet
from humanfriendly import parse_size
from rest_framework.exceptions import ValidationError
from xapian_backend import DATETIME_FORMAT

from codex.librarian.queue_mp import LIBRARIAN_QUEUE
from codex.librarian.search.tasks import SearchIndexJanitorUpdateTask
from codex.models import Comic, SearchQuery, SearchResult
from codex.serializers.browser import BrowserSettingsSerializer
from codex.serializers.choices import CHOICES
from codex.settings.logging import get_logger
from codex.views.mixins import GroupACLMixin
from codex.views.session import BrowserSessionViewBase


LOG = get_logger(__name__)
DATE_FORMAT = DATETIME_FORMAT.removesuffix("%H%M%S")
RANGE_DELIMITER = ".."
XAPIAN_UPPERCASE_OPERATORS = frozenset(["AND", "OR", "XOR", "NEAR", "ADJ"])


class BrowserBaseView(BrowserSessionViewBase, GroupACLMixin):
    """Browse comics with a variety of filters and sorts."""

    input_serializer_class = BrowserSettingsSerializer

    _SEARCH_FIELD_ALIASES = {
        "ltr": "read_ltr",
        "title": "name",
        "scan": "scan_info",
        "character": "characters",
        "creator": "creators",
        "created": "created_at",
        "finished": "unread",
        "genre": "genres",
        "location": "locations",
        "read": "unread",
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
    _BOOKMARK_FILTERS = frozenset(set(CHOICES["bookmarkFilter"].keys()) - set(("ALL",)))
    _GET_JSON_KEYS = frozenset(("filters", "show"))

    def __init__(self, *args, **kwargs):
        """Set params for the type checker."""
        super().__init__(*args, **kwargs)
        self._is_admin = None
        self.params = {}

    def _filter_by_comic_field(self, field, is_model_comic):
        """Filter by a comic any2many attribute."""
        filter_list = self.params["filters"].get(field)
        filter_query = Q()
        if filter_list:
            if is_model_comic:
                query_prefix = ""
            else:
                query_prefix = "comic__"

            if field == self.CREDIT_PERSON_UI_FIELD:
                rel = f"{query_prefix}credits__person"
            else:
                rel = f"{query_prefix}{field}"

            for index, val in enumerate(filter_list):
                # None values in a list don't work right so test for them separately
                if val is None:
                    del filter_list[index]
                    filter_query |= Q(**{f"{rel}__isnull": True})
            if filter_list:
                filter_query |= Q(**{f"{rel}__in": filter_list})
        return filter_query

    def _get_comic_field_filter(self, is_model_comic):
        """Filter the comics based on the form filters."""
        comic_field_filter = Q()
        for attribute in self.FILTER_ATTRIBUTES:
            comic_field_filter &= self._filter_by_comic_field(attribute, is_model_comic)
        return comic_field_filter

    def get_bm_rel(self, is_model_comic):
        """Create bookmark relation."""
        bm_rel = "bookmark"
        if not is_model_comic:
            bm_rel = "comic__" + bm_rel
        return bm_rel

    def _get_my_bookmark_filter(self, bm_rel):
        """Get a filter for my session or user defined bookmarks."""
        if self.request.user.is_authenticated:
            my_bookmarks_kwargs = {f"{bm_rel}__user": self.request.user}
        else:
            my_bookmarks_kwargs = {
                f"{bm_rel}__session__session_key": self.request.session.session_key
            }
        return Q(**my_bookmarks_kwargs)

    def _get_bookmark_filter(self, is_model_comic, choice):
        """Build bookmark query."""
        if choice is None:
            choice = self.params["filters"].get("bookmark", "ALL")
        if choice in self._BOOKMARK_FILTERS:
            bm_rel = self.get_bm_rel(is_model_comic)
            my_bookmark_filter = self._get_my_bookmark_filter(bm_rel)
            if choice in ("UNREAD", "IN_PROGRESS"):
                my_not_finished_filter = my_bookmark_filter & Q(
                    **{f"{bm_rel}__finished__in": (False, None)}
                )
                if choice == "UNREAD":
                    bookmark_filter = Q(**{bm_rel: None}) | my_not_finished_filter
                else:  # IN_PROGRESS
                    bookmark_filter = my_not_finished_filter & Q(
                        **{f"{bm_rel}__page__gt": 0}
                    )
            else:  # READ
                bookmark_filter = my_bookmark_filter & Q(
                    **{f"{bm_rel}__finished": True}
                )
        else:
            bookmark_filter = Q()
        return bookmark_filter

    def _get_folders_filter(self):
        """Get a filter for ALL parent folders not just immediate one."""
        pk = self.kwargs.get("pk")
        if pk:
            folders_filter = Q(folders__in=[pk])
        else:
            folders_filter = Q()

        return folders_filter

    def _get_browser_group_filter(self):
        """Get the objects we'll be displaying."""
        # Get the instances that are children of the group_instance
        # And the filtered comics that are children of the group_instance
        group_filter = Q()
        pk = self.kwargs.get("pk")
        group = self.kwargs.get("group")
        if pk or group == self.FOLDER_GROUP:
            if not pk:
                pk = None
            group_relation = self.GROUP_RELATION[group]
            group_filter |= Q(**{group_relation: pk})

        return group_filter

    @staticmethod
    def _parse_datetime(value, format=DATETIME_FORMAT):
        try:
            dttm = du_parse(value)
            if dttm:
                value = dttm.strftime(format)
            return value
        except Exception as exc:
            LOG.warning(exc)
            LOG.exception(exc)
            return ""

    @classmethod
    def _parse_date(cls, value):
        return cls._parse_datetime(value, format=DATE_FORMAT)

    @staticmethod
    def _parse_size(value):
        try:
            size = parse_size(value)
        except Exception as exc:
            LOG.warning(exc)
            LOG.exception(exc)
            size = ""
        return str(size)

    @staticmethod
    def _parse_search_token_value(convert_func, token_value):
        try:
            token_value_bits = []
            for token_value_bit in token_value.split(RANGE_DELIMITER):
                if token_value_bit in ("", "*"):
                    token_value_bits.append(token_value_bit)
                    continue
                xapian_value_str = convert_func(token_value_bit)
                token_value_bits.append(xapian_value_str)
            token_value = RANGE_DELIMITER.join(token_value_bits)
        except Exception as exc:
            LOG.warning(exc)
            LOG.exception(exc)
        return token_value

    def _parse_search_field_token(self, token, is_model_comic):
        """Convert aliased search fields and extract the bookmark query."""
        bookmark_field = False
        bookmark_filter = Q()
        try:
            token_field, token_value = token.split(":")

            # Alias field searches
            index_token_field = self._SEARCH_FIELD_ALIASES.get(token_field)
            if index_token_field:
                token_field = index_token_field

            # Parse Dates, Datetimes, and Integers
            if token_field == "date":
                token_value = self._parse_search_token_value(
                    self._parse_date, token_value
                )
            elif token_field in ("updated_at", "created_at"):
                token_value = self._parse_search_token_value(
                    self._parse_datetime, token_value
                )
            elif token_field == "size":
                token_value = self._parse_search_token_value(
                    self._parse_size, token_value
                )

            # Seems to fix a haystack xapian-backend range bug?
            # https://github.com/notanumber/xapian-haystack/issues/217
            if token_value.endswith(".."):
                token_value += "*"

            # bookmark fields
            if token_field in ("unread", "in_progress"):
                token_value_bool = strtobool(token_value)
                reverse_filter = False
                if token_field == "unread":
                    reverse_filter = True
                if token_field in ("unread", "in_progress"):
                    choice = token_field.upper()
                    reverse_filter = bool(reverse_filter * token_value_bool)
                else:
                    choice = ""

                bookmark_filter = self._get_bookmark_filter(is_model_comic, choice)
                if bookmark_filter != Q() and reverse_filter:
                    bookmark_filter = ~Q(bookmark_filter)
                bookmark_field = True

            token = ":".join((token_field, token_value))
        except ValueError:
            pass

        return token, bookmark_field, bookmark_filter

    def _parse_unsearchable_fields(self, query_tokens, is_model_comic):
        """Preprocess query string by aliasing fields and extracting bookmark query."""
        bookmark_filter = Q()
        search_query_tokens = []

        for token in query_tokens:
            bookmark_field = False
            if not token:
                continue

            if token.find(":") and not (token.startswith('"') and token.endswith('"')):
                # is a field search token
                (
                    token,
                    bookmark_field,
                    field_bookmark_filter,
                ) = self._parse_search_field_token(token, is_model_comic)
                if bookmark_field:
                    bookmark_filter &= field_bookmark_filter

            if not bookmark_field:
                search_query_tokens.append(token)

        return search_query_tokens, bookmark_filter

    def _cache_haystack_query(self, query_obj):
        """Do the actual  Search."""
        try:
            sqs = SearchQuerySet().auto_query(query_obj.text)
            comic_scores = sqs.values("pk", "score")
            search_results = []
            # Detect out of date search engine
            sqs_pks = set()
            for comic_score in comic_scores:
                sqs_pks.add(comic_score["pk"])
            # No acl filter. I don't think this is a leak because its only as a filter
            # with other filters.
            valid_pks = Comic.objects.filter(pk__in=sqs_pks).values_list(
                "pk", flat=True
            )
            search_engine_out_of_date = False
            for comic_score in comic_scores:
                if comic_score["pk"] not in valid_pks:
                    search_engine_out_of_date = True
                    continue
                sr = SearchResult(
                    query_id=query_obj.pk,
                    comic_id=comic_score["pk"],
                    score=comic_score["score"],
                )
                search_results.append(sr)
            if search_engine_out_of_date:
                LOG.warning("Search index out of date. Scoring non-existent comics.")
                task = SearchIndexJanitorUpdateTask(False)
                LIBRARIAN_QUEUE.put(task)
            SearchResult.objects.bulk_create(search_results)
        except Exception as exc:
            # Don't save queries with errors
            query_obj.delete()
            raise exc

    def _get_search_query_filter(self, autoquery_tokens, is_model_comic):
        """Do the haystack query."""
        search_filter = Q()
        autoquery_pk = None
        if not autoquery_tokens:
            return search_filter, autoquery_pk

        defaults = {"used_at": Now()}
        text = " ".join(autoquery_tokens)
        query_obj, created = SearchQuery.objects.update_or_create(
            defaults=defaults, text=text
        )
        if created or not SearchResult.objects.filter(query=query_obj).exists():
            self._cache_haystack_query(query_obj)

        prefix = ""
        if not is_model_comic:
            prefix = "comic__"

        query_dict = {
            f"{prefix}pk__in": F(f"{prefix}searchresult__comic_id"),
            f"{prefix}searchresult__query": query_obj.pk,
        }
        search_filter = Q(**query_dict)
        return search_filter, query_obj.pk

    def _fix_xapian_flag_boolean_any_case(self):
        """
        Fix Xapian QueryParser.FLAG_BOOLEAN_ANY_CASE not working.

        Also saves the query with whitespace removed.
        """
        autoquery_tokens_raw = self.params.get("q", "").split(" ")

        autoquery_tokens = []
        for token in autoquery_tokens_raw:
            if not token:
                continue
            token_upper = token.upper()
            if token_upper in XAPIAN_UPPERCASE_OPERATORS:
                token = token_upper
            autoquery_tokens.append(token)
        return autoquery_tokens

    def _get_search_filter(self, is_model_comic):
        """Search filters."""
        search_filter = Q()
        autoquery_pk = None
        try:
            autoquery_tokens = self._fix_xapian_flag_boolean_any_case()
            # Parse out the bookmark filter and get the remaining tokens
            (
                haystack_autoquery_tokens,
                bookmark_filter,
            ) = self._parse_unsearchable_fields(autoquery_tokens, is_model_comic)
            search_filter &= bookmark_filter

            # Query haystack
            (
                haystack_search_filter,
                autoquery_pk,
            ) = self._get_search_query_filter(haystack_autoquery_tokens, is_model_comic)
            search_filter &= haystack_search_filter
            self.params["q"] = " ".join(autoquery_tokens)
        except Exception as exc:
            LOG.warning(exc)
        return search_filter, autoquery_pk

    def _get_group_filter(self, choices):
        """Get filter for the displayed group."""
        is_folder_view = self.kwargs.get("group") == self.FOLDER_GROUP
        if is_folder_view and choices:
            # Choice view needs to get all descendant comic attributes
            # So filter by all the folders
            group_filter = self._get_folders_filter()
        else:
            # The browser filter is the same for all views
            group_filter = self._get_browser_group_filter()

        return group_filter

    def is_admin(self):
        """Is the current user an admin."""
        if self._is_admin is None:
            user = self.request.user
            self._is_admin = user and isinstance(user, User) and user.is_staff
        return self._is_admin

    def get_aggregate_filter(self, is_model_comic):
        """Return the filter for making aggregates."""
        bookmark_filter_join = self._get_bookmark_filter(is_model_comic, None)
        comic_field_filter = self._get_comic_field_filter(is_model_comic)
        aggregate_filter = bookmark_filter_join & comic_field_filter
        return aggregate_filter

    def get_query_filters_without_group(self, is_model_comic):
        """Return all the filters except the group filter."""
        object_filter = self.get_group_acl_filter(is_model_comic)

        search_filter, autoquery_pk = self._get_search_filter(is_model_comic)
        object_filter &= search_filter

        object_filter &= self.get_aggregate_filter(is_model_comic)
        return object_filter, autoquery_pk

    def get_query_filters(self, is_model_comic, choices=False):
        """Return the main object filter and the one for aggregates."""
        object_filter, autoquery_pk = self.get_query_filters_without_group(
            is_model_comic
        )

        object_filter &= self._get_group_filter(choices)

        return object_filter, autoquery_pk

    def _parse_query_params(self, query_params):
        """Parse GET query parameters: filter object & snake case."""
        result = {}
        for key, val in query_params.items():
            if key in self._GET_JSON_KEYS:
                val = unquote_plus(val)  # for pocketbooks reader
                parsed_val = json.loads(val)
                if not parsed_val:
                    continue
            else:
                parsed_val = val

            result[key] = parsed_val
        result = underscoreize(result, **api_settings.JSON_UNDERSCOREIZE)

        return result

    def parse_params(self):
        """Validate sbmitted settings and apply them over the session settings."""
        self.params = deepcopy(self.SESSION_DEFAULTS)
        if self.request.method == "GET":
            data = self._parse_query_params(self.request.GET)
        elif hasattr(self.request, "data"):
            data = self._parse_query_params(self.request.data)
        else:
            return

        serializer = self.input_serializer_class(data=data)

        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as exc:
            LOG.error(serializer.errors)
            raise exc
        self.params.update(serializer.validated_data)
