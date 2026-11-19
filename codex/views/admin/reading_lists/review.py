"""Combine lists, suggest combinations, and save series mappings."""

from typing import Any

from comicbox.readinglists import ReadingListError, combine
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from codex.librarian.mp_queue import LIBRARIAN_QUEUE
from codex.librarian.scribe.readinglists.combine import document_of, recombine
from codex.librarian.scribe.readinglists.matcher import series_key
from codex.librarian.scribe.readinglists.service import combine_lists, suggestions
from codex.librarian.scribe.readinglists.tasks import ReadingListRematchTask
from codex.models import Series
from codex.models.readinglist import (
    ReadingList,
    ReadingListEntry,
    ReadingListMatchTier,
    ReadingListSeriesMapping,
)
from codex.views.admin.auth import AdminAPIView
from codex.views.admin.reading_lists.table import get_list


def _dry_run(lists: list[ReadingList]) -> dict[str, Any]:
    """Report what combining would give, without saving it."""
    documents = [document_of(reading_list) for reading_list in lists]
    try:
        result = combine([document for document in documents if document["entries"]])
    except ReadingListError as exc:
        raise ValidationError(str(exc)) from exc
    return {
        "total": len(result.reading_list.get("entries") or ()),
        "only_in": [
            {"pk": reading_list.pk, "count": len(only)}
            for reading_list, only in zip(lists, result.only_in, strict=False)
        ],
        "order_conflicts": len(result.order_conflicts),
        "id_conflicts": len(result.id_conflicts),
        "name_joins": len(result.name_joins),
    }


class AdminReadingListCombineView(AdminAPIView):
    """
    POST ``{primary, others, dryRun}``: combine lists into the primary.

    The primary's order wins. A dry run reports the result and saves
    nothing; otherwise the others' sources move into the primary and the
    others are deleted. Removing a source later undoes it.
    """

    def post(self, *_args, **_kwargs) -> Response:
        """Combine, or preview combining."""
        data = self.request.data
        try:
            primary_pk = int(str(data.get("primary")))
            other_pks = [int(pk) for pk in data.get("others") or ()]
        except (TypeError, ValueError) as exc:
            reason = "primary and others must be reading list pks."
            raise ValidationError(reason) from exc
        primary = get_list(primary_pk)
        others = list(
            ReadingList.objects.filter(pk__in=other_pks).exclude(pk=primary_pk)
        )
        if not others:
            reason = "Choose at least one other list."
            raise ValidationError(reason)
        if data.get("dry_run"):
            return Response(_dry_run([primary, *others]))
        combined = combine_lists(primary, others)
        return Response({"pk": combined.pk})


class AdminReadingListSuggestionsView(AdminAPIView):
    """GET pairs of lists that look like one reading order."""

    def get(self, *_args, **_kwargs) -> Response:
        """Return the suggested combinations."""
        found = suggestions()
        names = dict(ReadingList.objects.values_list("pk", "name"))
        return Response(
            {
                "suggestions": [
                    {
                        "pk": item.pk,
                        "name": names.get(item.pk, ""),
                        "other_pk": item.other_pk,
                        "other_name": names.get(item.other_pk, ""),
                        "verdict": item.verdict,
                        "overlap": item.overlap,
                    }
                    for item in found
                ]
            }
        )


def _mapping_repr(mapping: ReadingListSeriesMapping) -> dict[str, Any]:
    series = mapping.series
    return {
        "pk": mapping.pk,
        "series_key": mapping.series_key,
        "year": mapping.year or None,
        "series": {
            "pk": series.pk,
            "name": series.name,
            "start_year": series.start_year,
            "publisher": series.publisher.name if series.publisher_id else "",  # pyright: ignore[reportAttributeAccessIssue]
        },
    }


class AdminReadingListSeriesMappingsView(AdminAPIView):
    """
    GET, POST or DELETE saved series mappings.

    POST ``{list, entry, series}`` says this entry's series is that library
    series. It applies to every list: the list's rows of that series match
    again now, and every other list's missing rows soon after.
    """

    def get(self, *_args, **_kwargs) -> Response:
        """Return every mapping."""
        mappings = ReadingListSeriesMapping.objects.select_related(
            "series", "series__publisher"
        ).order_by("series_key", "year")
        return Response({"mappings": [_mapping_repr(m) for m in mappings]})

    def post(self, *_args, **_kwargs) -> Response:
        """Save a mapping from a review row and rematch its series."""
        data = self.request.data
        reading_list = get_list(data.get("list"))
        entry = ReadingListEntry.objects.filter(
            reading_list=reading_list, pk=data.get("entry")
        ).first()
        series = Series.objects.filter(pk=data.get("series")).first()
        if entry is None or series is None:
            reason = "No such entry or series."
            raise NotFound(reason)
        key = series_key(entry.reference or {})
        if key is None:
            reason = "This entry names no series."
            raise ValidationError(reason)
        name, year = key
        mapping, _ = ReadingListSeriesMapping.objects.update_or_create(
            series_key=name, year=year, defaults={"series": series}
        )
        # Let this list's rows of the series match through the mapping.
        same_series = [
            row.pk
            for row in ReadingListEntry.objects.filter(
                reading_list=reading_list, manual=False
            ).exclude(
                match_tier__in=(
                    ReadingListMatchTier.MANUAL,
                    ReadingListMatchTier.MARKED_MISSING,
                    ReadingListMatchTier.TAGGED,
                )
            )
            if series_key(row.reference or {}) == key
        ]
        ReadingListEntry.objects.filter(pk__in=same_series).update(
            comic=None, match_tier=ReadingListMatchTier.NONE, needs_review=False
        )
        recombine(reading_list)
        LIBRARIAN_QUEUE.put(ReadingListRematchTask())
        return Response(_mapping_repr(mapping), status=201)

    def delete(self, *_args, **_kwargs) -> Response:
        """Forget a mapping. Rows it matched keep their comics."""
        pk = self.request.query_params.get("pk") or self.request.data.get("pk")
        count, _ = ReadingListSeriesMapping.objects.filter(pk=pk).delete()
        return Response({"deleted": count})
