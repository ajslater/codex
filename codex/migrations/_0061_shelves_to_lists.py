"""
Migration 0061's last data step: shelves become reading lists.

Kept apart so the migration stays readable; the loader skips modules whose
name starts with an underscore. Like the migration, it reads historical
models only, and is frozen with it.

Each shelf becomes a personal reading list of the same name. Its comics
become entries added by hand; every other item becomes a collection item
whose comics are written in the same step, laid out as the live sync lays
them out, so the first sync finds nothing to change. A stored shelves
filter becomes a Reading Lists filter on those lists and the ``shelved``
sort key and column become ``reading_lists``. The reverse rebuilds shelves,
best effort.
"""

import json
import uuid
from collections import defaultdict
from importlib import import_module
from itertools import batched

from django.conf import settings

_ARCS = "arcs"
_BATCH = 1000
# Values bound per query: a stock SQLite allows 32,766 variables.
_PK_BATCH = 10000
_READING_LISTS_KEY = "reading_lists"
_POST_V2_6_0 = import_module("codex.migrations.0060_post_v2_6_0_schema")
_rename_sort_key = _POST_V2_6_0._rename_sort_key  # noqa: SLF001

_SHELVED_KEY = "shelved"
_COMICS = "comics"
_COLLECTION = "collection"
_FALLBACK_LIST_NAME = "Reading List"
_YEAR_LEN = 4
# ``get_sort_name``'s leading articles, frozen here with the rule below.
_ARTICLES = frozenset(
    {
        # en
        "a", "an", "the",
        # es
        "un", "unos", "unas", "el", "los", "la", "las",
        # fr (l' is shared with it)
        "une", "le", "les", "l'",
        # pt
        "o", "os",
        # de (den & die conflict with English)
        "der", "dem", "des", "das",
        # it (i conflicts with English)
        "il", "lo", "gli",
        # nl
        "de", "het", "een",
        # sw / no / da
        "en", "ett", "ei", "et",
        # ct
        "els", "una", "uns", "unes", "na",
    }
)  # fmt: skip
# Each item collection's identity parts, frozen from
# ``codex.user_data.identifiers``: the name chain, a folder's path, or a
# list's name and UUID.
_IDENTITY_PARTS = {
    "publishers": lambda obj: [obj.name],
    "imprints": lambda obj: [obj.publisher.name, obj.name],
    "series": lambda obj: [obj.publisher.name, obj.imprint.name, obj.name],
    "volumes": lambda obj: [
        obj.publisher.name,
        obj.imprint.name,
        obj.series.name,
        obj.name,
        obj.number_to,
    ],
    "folders": lambda obj: [str(obj.path)],
    _ARCS: lambda obj: [obj.name, str(obj.uuid)],
}
# The collections a list holds whole, and the model each names.
_ITEM_MODELS = {
    "publishers": "Publisher",
    "imprints": "Imprint",
    "series": "Series",
    "volumes": "Volume",
    "folders": "Folder",
    _ARCS: "ReadingList",
}
_COMIC_FIELD = {
    "publishers": "publisher_id",
    "imprints": "imprint_id",
    "series": "series_id",
    "volumes": "volume_id",
}
_COMIC_ORDER = (
    "series__sort_name",
    "volume__name",
    "volume__number_to",
    "issue_number",
    "issue_suffix",
    "sort_name",
    "pk",
)
_RELATED = {
    "imprints": ("publisher",),
    "series": ("publisher", "imprint"),
    "volumes": ("publisher", "imprint", "series"),
}


def _list_names(apps, shelves) -> dict:
    """
    Name each shelf's list: cleaned as list names are, never empty, unique.

    A list name is cleaned on save and a shelf name never was, so two
    shelves can clean to one name, or to nothing. Repeats are numbered per
    user, in shelf order.
    """
    reading_list_model = apps.get_model("codex", "ReadingList")
    clean = reading_list_model._meta.get_field("name").get_prep_value
    taken: dict = defaultdict(set)
    for user_id, name in reading_list_model.objects.filter(
        user__isnull=False
    ).values_list("user_id", "name"):
        taken[user_id].add(name)
    names = {}
    for shelf in shelves:
        base = (clean(shelf.name) or "").strip() or _FALLBACK_LIST_NAME
        name, number = base, 2
        while name in taken[shelf.user_id]:
            suffix = f" ({number})"
            name = clean(base[: 128 - len(suffix)] + suffix)
            number += 1
        taken[shelf.user_id].add(name)
        names[shelf.pk] = name
    return names


def _issue_name(number, suffix) -> str:
    text = "" if number is None else format(number.normalize(), "f")
    return f"{text}{suffix or ''}"


def _in_batches(queryset, pks):
    """Yield the rows of the pks, a batch a query: a stock SQLite binds 32,766."""
    for batch in batched(pks, _PK_BATCH):
        yield from queryset.filter(pk__in=batch)


def _comic_references(comic_model, pks) -> dict:
    """Return a comicbox entry per comic, so a hand entry can be found again."""
    references = {}
    rows = _in_batches(
        comic_model.objects.values_list(
            "pk",
            "series__name",
            "series__start_year",
            "volume__name",
            "issue_number",
            "issue_suffix",
            "year",
            "month",
            "day",
        ),
        sorted(pks),
    )
    for pk, series, start, volume, number, suffix, year, month, day in rows:
        reference: dict = {}
        if series:
            reference["series"] = {"name": series}
            if start:
                reference["series"]["start_year"] = start
        if volume is not None:
            reference["volume"] = {"number": volume}
        if issue := _issue_name(number, suffix):
            reference["issue"] = {"name": issue}
        date = {
            key: value
            for key, value in (("year", year), ("month", month), ("day", day))
            if value
        }
        if date:
            reference["date"] = date
        references[pk] = reference
    return references


def _item_members(apps, collection, target_id) -> list:
    """Return a collection's comics in reading order, as the live sync does."""
    comic_model = apps.get_model("codex", "Comic")
    if collection == _ARCS:
        entry_model = apps.get_model("codex", "ReadingListEntry")
        rows = (
            entry_model.objects.filter(
                reading_list_id=target_id, ignored=False, comic__isnull=False
            )
            .order_by("position", "pk")
            .values_list("comic_id", flat=True)
        )
        return list(dict.fromkeys(rows))
    if collection == "folders":
        comics = comic_model.objects.filter(folders=target_id).order_by("path", "pk")
    else:
        comics = comic_model.objects.filter(
            **{_COMIC_FIELD[collection]: target_id}
        ).order_by(*_COMIC_ORDER)
    return list(comics.values_list("pk", flat=True))


def _volume_str(volume) -> str:
    """``Volume.to_str``, frozen here: ``v2``, ``v1-3``, ``(2006)``."""
    if volume.name is None:
        return ""
    numbers = str(volume.name)
    is_year = len(numbers) == _YEAR_LEN
    if volume.number_to is not None:
        numbers = f"{numbers}-{volume.number_to}"
    return f"({numbers})" if is_year else f"v{numbers}"


def _sort_name(name: str) -> str:
    """``get_sort_name``, frozen here: a leading article moves to the end."""
    lower_name = name.lower()
    name_parts = lower_name.split()
    if len(name_parts) > 1 and (first_word := name_parts[0]) in _ARTICLES:
        return f"{' '.join(name_parts[1:])}, {first_word}"
    return lower_name


def _item_identity(collection, target) -> tuple:
    """Return an item's ``ref`` and ``document``: its identity and its label."""
    # ``encode_identifier``, frozen here: compact JSON of the collection and
    # its parts. The live sync refreshes it while the item is bound.
    parts = _IDENTITY_PARTS[collection](target)
    identity = json.dumps([collection, *parts], separators=(",", ":"))
    if collection == "volumes":
        label = f"{target.series.name} {_volume_str(target)}".strip()
    else:
        label = str(getattr(target, "name", "") or getattr(target, "path", ""))
    return identity[:1024], {"identity": identity, "label": label}


def _load_target(apps, collection, target_id):
    model = apps.get_model("codex", _ITEM_MODELS[collection])
    queryset = model.objects.filter(pk=target_id)
    if related := _RELATED.get(collection):
        queryset = queryset.select_related(*related)
    return queryset.first()


class _ShelfList:
    """One shelf's list: its entries and items, laid out in shelf order."""

    def __init__(self, apps, reading_list, items) -> None:
        self.apps = apps
        self.reading_list = reading_list
        self.items = items
        self.rows: list = []
        self.dropped = 0

    def build(self) -> None:
        comic_model = self.apps.get_model("codex", "Comic")
        comic_pks = [pk for collection, pk in self.items if collection == _COMICS]
        live = set(
            _in_batches(comic_model.objects.values_list("pk", flat=True), comic_pks)
        )
        references = _comic_references(comic_model, live)
        delivered = set(live)
        others = 0
        rank = 0
        for collection, target_id in self.items:
            if collection == _COMICS:
                if target_id in live:
                    self.rows.append(("manual", target_id, references[target_id]))
                    others += 1
                else:
                    self.dropped += 1
                continue
            target = _load_target(self.apps, collection, target_id)
            if target is None:
                self.dropped += 1
                continue
            source = self._item(collection, target, rank, others)
            rank += 1
            for comic_pk in _item_members(self.apps, collection, target_id):
                if comic_pk not in delivered:
                    delivered.add(comic_pk)
                    self.rows.append(("live", comic_pk, source))
        self._write()

    def _item(self, collection, target, rank, others):
        source_model = self.apps.get_model("codex", "ReadingListSource")
        ref, document = _item_identity(collection, target)
        return source_model.objects.create(
            reading_list=self.reading_list,
            kind=_COLLECTION,
            collection=collection,
            target_id=target.pk,
            ref=ref,
            document=document,
            revision="",
            rank=rank,
            position=others,
        )

    def _write(self) -> None:
        entry_model = self.apps.get_model("codex", "ReadingListEntry")
        comic_model = self.apps.get_model("codex", "Comic")
        manual_pks = [pk for kind, pk, _ in self.rows if kind == "manual"]
        comics = {
            comic.pk: comic
            for comic in _in_batches(
                comic_model.objects.select_related("series"), manual_pks
            )
        }
        entries = []
        for position, (kind, comic_pk, extra) in enumerate(self.rows):
            if kind == "live":
                entries.append(
                    entry_model(
                        reading_list=self.reading_list,
                        position=position,
                        comic_id=comic_pk,
                        live_source=extra,
                        match_tier=_COLLECTION,
                    )
                )
                continue
            comic = comics[comic_pk]
            entries.append(
                entry_model(
                    reading_list=self.reading_list,
                    position=position,
                    comic_id=comic_pk,
                    reference=extra,
                    series_name=comic.series.name if comic.series_id else "",
                    issue=_issue_name(comic.issue_number, comic.issue_suffix)[:32],
                    year=comic.year,
                    match_tier="manual",
                    manual=True,
                )
            )
        entry_model.objects.bulk_create(entries, batch_size=_BATCH)


def _shelf_items(apps, shelf_pks) -> dict:
    """Each shelf's items in the order they were shelved, deduplicated."""
    shelf_item_model = apps.get_model("codex", "ShelfItem")
    items: dict = defaultdict(list)
    seen = set()
    rows = (
        shelf_item_model.objects.filter(shelf_id__in=shelf_pks)
        .order_by("pk")
        .values_list("shelf_id", "collection", "target_id")
    )
    for shelf_pk, collection, target_id in rows:
        key = (shelf_pk, collection, target_id)
        if key in seen or (collection != _COMICS and collection not in _ITEM_MODELS):
            continue
        seen.add(key)
        items[shelf_pk].append((collection, target_id))
    return items


def _fold_shelf_filters(apps, shelf_to_list: dict) -> None:
    """Make a stored shelves filter a Reading Lists filter on their lists."""
    filters_model = apps.get_model("codex", "SettingsBrowserFilters")
    update = []
    for row in filters_model.objects.exclude(shelves=[]):
        current = row.reading_lists or []
        lists = [shelf_to_list[pk] for pk in row.shelves or () if pk in shelf_to_list]
        merged = list(
            dict.fromkeys([*(pk for pk in current if pk is not None), *lists])
        )
        if None in current:
            # The "in no list" choice stays last, as the arcs step leaves it.
            merged.append(None)
        if merged != current:
            row.reading_lists = merged
            update.append(row)
    filters_model.objects.bulk_update(update, ("reading_lists",), batch_size=_BATCH)


def shelves_to_lists(apps, _schema_editor) -> None:
    """
    Make each shelf a personal reading list of the same name.

    Comic items become entries added by hand, with a reference to find them
    again; every other item becomes a collection item whose comics are
    written now, since nothing syncs lists at startup. Its revision is
    blank, so the first sync verifies it. Rows whose user, comic or target
    is gone are dropped and logged: SQLite checks foreign keys only when
    asked, and ``migrate`` ends by asking.
    """
    from loguru import logger

    shelf_model = apps.get_model("codex", "Shelf")
    reading_list_model = apps.get_model("codex", "ReadingList")
    user_model = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    users = set(user_model.objects.values_list("pk", flat=True))
    shelves = list(shelf_model.objects.order_by("pk"))
    orphaned = [shelf.pk for shelf in shelves if shelf.user_id not in users]
    shelves = [shelf for shelf in shelves if shelf.user_id in users]
    names = _list_names(apps, shelves)
    items = _shelf_items(apps, [shelf.pk for shelf in shelves])
    shelf_to_list = {}
    dropped = 0
    for shelf in shelves:
        reading_list = reading_list_model.objects.create(
            user_id=shelf.user_id,
            name=names[shelf.pk],
            sort_name=_sort_name(names[shelf.pk]),
            uuid=uuid.uuid4(),
        )
        shelf_to_list[shelf.pk] = reading_list.pk
        shelf_list = _ShelfList(apps, reading_list, items.get(shelf.pk, []))
        shelf_list.build()
        dropped += shelf_list.dropped
    _fold_shelf_filters(apps, shelf_to_list)
    _rename_sort_key(apps, _SHELVED_KEY, _READING_LISTS_KEY)
    if orphaned or dropped:
        counts = f"{len(orphaned)} shelves of gone users, {dropped} gone items"
        logger.info(f"Shelves to reading lists dropped {counts}.")


def lists_to_shelves(apps, _schema_editor) -> None:
    """
    Reverse, best effort: each personal list becomes a shelf again.

    Its hand-added comics and its collection items are shelved; a stored
    Reading Lists filter on a personal list becomes a shelves filter.
    Order, imported entries and hidden ones have no place on a shelf.
    """
    shelf_model = apps.get_model("codex", "Shelf")
    shelf_item_model = apps.get_model("codex", "ShelfItem")
    reading_list_model = apps.get_model("codex", "ReadingList")
    entry_model = apps.get_model("codex", "ReadingListEntry")
    source_model = apps.get_model("codex", "ReadingListSource")
    list_to_shelf = {}
    for reading_list in reading_list_model.objects.filter(user__isnull=False).order_by(
        "pk"
    ):
        shelf = shelf_model.objects.create(
            user_id=reading_list.user_id, name=reading_list.name[:128]
        )
        list_to_shelf[reading_list.pk] = shelf.pk
        targets = [
            (_COMICS, pk)
            for pk in entry_model.objects.filter(
                reading_list=reading_list,
                live_source__isnull=True,
                ignored=False,
                comic__isnull=False,
            )
            .order_by("position", "pk")
            .values_list("comic_id", flat=True)
        ]
        targets += list(
            source_model.objects.filter(
                reading_list=reading_list, kind=_COLLECTION, target_id__isnull=False
            )
            .order_by("rank", "pk")
            .values_list("collection", "target_id")
        )
        shelf_item_model.objects.bulk_create(
            [
                shelf_item_model(shelf_id=shelf.pk, collection=collection, target_id=pk)
                for collection, pk in dict.fromkeys(targets)
            ],
            batch_size=_BATCH,
        )
    filters_model = apps.get_model("codex", "SettingsBrowserFilters")
    for row in filters_model.objects.exclude(reading_lists=[]):
        shelves = [list_to_shelf[pk] for pk in row.reading_lists if pk in list_to_shelf]
        if shelves:
            row.shelves = shelves
            row.reading_lists = [
                pk for pk in row.reading_lists if pk not in list_to_shelf
            ]
            row.save(update_fields=("shelves", "reading_lists"))
