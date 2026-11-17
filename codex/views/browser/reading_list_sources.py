"""Name a page of reading list cards' sources, which tells same-named lists apart."""

from collections import defaultdict
from types import MappingProxyType
from typing import Final

from django.db.models import QuerySet

from codex.models.readinglist import ReadingListSource

_SHORT_LABELS: Final = MappingProxyType(
    {
        "tags": "Tags",
        "upload": "Upload",
        "url": "URL",
        "catalog": "DieselTech",
        "metron_list": "Metron",
        "metron_arc": "Metron Arc",
        "comicvine_arc": "Comic Vine Arc",
    }
)


def _label(kind: str, attribution: str) -> str:
    label = _SHORT_LABELS.get(kind, kind)
    return f"{label} · {attribution.upper()}" if attribution else label


def attach_list_sources(collection_qs: QuerySet) -> None:
    """
    Set ``list_sources`` on each reading list of a page: ``Tags + Metron · CBRO``.

    Iterating the paginated queryset primes its result cache, so the
    serializer reads these same instances. One query for the page's sources.
    """
    rows = list(collection_qs)
    if not rows:
        return
    labels: defaultdict[int, list[str]] = defaultdict(list)
    sources = (
        ReadingListSource.objects.filter(reading_list_id__in=[row.pk for row in rows])
        .order_by("rank", "pk")
        .values_list("reading_list_id", "kind", "attribution_source")
    )
    for list_pk, kind, attribution in sources:
        label = _label(kind, attribution)
        if label not in labels[list_pk]:
            labels[list_pk].append(label)
    for row in rows:
        row.list_sources = " + ".join(labels.get(row.pk, ()))
