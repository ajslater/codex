"""Name a page of reading list cards' sources, which tells same-named lists apart."""

from collections import defaultdict

from django.db.models import Count, Q, QuerySet

from codex.choices.readinglists import SOURCE_SHORT_LABELS
from codex.models.readinglist import ReadingListEntry, ReadingListSource
from codex.views.readinglists.access import shown_entries_q


def _label(kind: str, attribution: str) -> str:
    label = SOURCE_SHORT_LABELS.get(kind, kind)
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


def attach_list_coverage(acl, user, collection_qs: QuerySet) -> None:
    """
    Set ``list_in_library`` and ``list_total`` on each list of a page.

    How much of the list this viewer has: "31 of 98" on the card of a list
    with gaps. Counts the entries the viewer sees, a missing issue for
    everyone. One query for the page.
    """
    rows = list(collection_qs)
    if not rows:
        return
    counts = {
        list_pk: (in_library, total)
        for list_pk, in_library, total in ReadingListEntry.objects.filter(
            shown_entries_q(acl, user), reading_list_id__in=[row.pk for row in rows]
        )
        .values("reading_list_id")
        .annotate(
            in_library=Count("pk", filter=Q(comic__isnull=False)), total=Count("pk")
        )
        .values_list("reading_list_id", "in_library", "total")
        .order_by()
    }
    for row in rows:
        row.list_in_library, row.list_total = counts.get(row.pk, (0, 0))
