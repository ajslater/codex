"""Backend search that gets the reverse variable as a parameter."""

import warnings
from datetime import date, datetime

from django.conf import settings
from django.utils.encoding import force_str

# Bubble up the correct error.
from whoosh.sorting import Count, DateRangeFacet, FieldFacet
from whoosh.support.relativedelta import relativedelta as RelativeDelta

from codex._vendor.haystack.backends import log_query
from codex._vendor.haystack.constants import DJANGO_CT
from codex._vendor.haystack.exceptions import SearchBackendError
from codex._vendor.haystack.utils import get_model_ct


class CodexBackendSearchMixin:
    @log_query
    def search(
        self,
        query_string,
        sort_by=None,
        start_offset=0,
        end_offset=None,
        fields="",
        highlight=False,
        facets=None,
        date_facets=None,
        query_facets=None,
        narrow_queries=None,
        spelling_query=None,
        within=None,
        dwithin=None,
        distance_point=None,
        models=None,
        limit_to_registered_models=None,
        result_class=None,
        reverse=False,
        **kwargs,
    ):
        if not self.setup_complete:
            self.setup()

        # A zero length query should return no results.
        if len(query_string) == 0:
            return {"results": [], "hits": 0}

        query_string = force_str(query_string)

        # A one-character query (non-wildcard) gets nabbed by a stopwords
        # filter and should yield zero results.
        if len(query_string) <= 1 and query_string != "*":
            return {"results": [], "hits": 0}

        # reverse = False # old reverse flag

        if sort_by is not None:
            # Determine if we need to reverse the results and if Whoosh can
            # handle what it's being asked to sort by. Reversing is an
            # all-or-nothing action, unfortunately.
            sort_by_list = []
            reverse_counter = 0

            for order_by in sort_by:
                if order_by.startswith("-"):
                    reverse_counter += 1
            if reverse_counter and reverse_counter != len(sort_by):
                raise SearchBackendError(
                    "Whoosh requires all order_by fields"
                    " to use the same sort direction"
                )

            for order_by in sort_by:
                if order_by.startswith("-"):
                    sort_by_list.append(order_by[1:])

                    if len(sort_by_list) == 1:
                        reverse = True
                else:
                    sort_by_list.append(order_by)

                    if len(sort_by_list) == 1:
                        reverse = False

            sort_by = sort_by_list

        group_by = []
        facet_types = {}
        if facets is not None:
            group_by += [
                FieldFacet(facet, allow_overlap=True, maptype=Count) for facet in facets
            ]
            facet_types.update({facet: "fields" for facet in facets})

        if date_facets is not None:

            def _fixup_datetime(dt):
                if isinstance(dt, datetime):
                    return dt
                if isinstance(dt, date):
                    return datetime(dt.year, dt.month, dt.day)
                raise ValueError

            for key, value in date_facets.items():
                start = _fixup_datetime(value["start_date"])
                end = _fixup_datetime(value["end_date"])
                gap_by = value["gap_by"]
                gap_amount = value.get("gap_amount", 1)
                gap = RelativeDelta(**{"%ss" % gap_by: gap_amount})
                group_by.append(DateRangeFacet(key, start, end, gap, maptype=Count))
                facet_types[key] = "dates"

        if query_facets is not None:
            warnings.warn(
                "Whoosh does not handle query faceting.", Warning, stacklevel=2
            )

        narrowed_results = None
        self.index = self.index.refresh()

        if limit_to_registered_models is None:
            limit_to_registered_models = getattr(
                settings, "HAYSTACK_LIMIT_TO_REGISTERED_MODELS", True
            )

        if models and len(models):
            model_choices = sorted(get_model_ct(model) for model in models)
        elif limit_to_registered_models:
            # Using narrow queries, limit the results to only models handled
            # with the current routers.
            model_choices = self.build_models_list()
        else:
            model_choices = []

        if len(model_choices) > 0:
            if narrow_queries is None:
                narrow_queries = set()

            narrow_queries.add(
                " OR ".join(["%s:%s" % (DJANGO_CT, rm) for rm in model_choices])
            )

        narrow_searcher = None

        if narrow_queries is not None:
            # Potentially expensive? I don't see another way to do it in Whoosh...
            narrow_searcher = self.index.searcher()

            for nq in narrow_queries:
                recent_narrowed_results = narrow_searcher.search(
                    self.parser.parse(force_str(nq)), limit=None
                )

                if len(recent_narrowed_results) <= 0:
                    return {"results": [], "hits": 0}

                if narrowed_results is not None:
                    narrowed_results.filter(recent_narrowed_results)
                else:
                    narrowed_results = recent_narrowed_results

        self.index = self.index.refresh()

        if self.index.doc_count():
            searcher = self.index.searcher()
            parsed_query = self.parser.parse(query_string)

            # In the event of an invalid/stopworded query, recover gracefully.
            if parsed_query is None:
                return {"results": [], "hits": 0}

            page_num, page_length = self.calculate_page(start_offset, end_offset)

            search_kwargs = {
                "pagelen": page_length,
                "sortedby": sort_by,
                "reverse": reverse,
                "groupedby": group_by,
            }

            # Handle the case where the results have been narrowed.
            if narrowed_results is not None:
                search_kwargs["filter"] = narrowed_results

            try:
                raw_page = searcher.search_page(parsed_query, page_num, **search_kwargs)
            except ValueError:
                if not self.silently_fail:
                    raise

                return {"results": [], "hits": 0, "spelling_suggestion": None}

            # Because as of Whoosh 2.5.1, it will return the wrong page of
            # results if you request something too high. :(
            if raw_page.pagenum < page_num:
                return {"results": [], "hits": 0, "spelling_suggestion": None}

            results = self._process_results(
                raw_page,
                highlight=highlight,
                query_string=query_string,
                spelling_query=spelling_query,
                result_class=result_class,
                facet_types=facet_types,
            )
            searcher.close()

            if hasattr(narrow_searcher, "close"):
                narrow_searcher.close()

            return results
        else:
            if self.include_spelling:
                if spelling_query:
                    spelling_suggestion = self.create_spelling_suggestion(
                        spelling_query
                    )
                else:
                    spelling_suggestion = self.create_spelling_suggestion(query_string)
            else:
                spelling_suggestion = None

            return {
                "results": [],
                "hits": 0,
                "spelling_suggestion": spelling_suggestion,
            }
