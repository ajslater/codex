"""
Codex Serializers for the metadata box.

``credits`` ships as an ordered dict ``{role: [person, ...]}``,
with roles in :data:`HEAD_ROLES` precedence then alphabetical, and
persons sorted by last name (matching the v3 frontend behavior).

``identifiers`` ships as a list of
``{type, code, displayName, pk, url}`` — ``type`` and ``code`` are
parsed out of the model-side ``Identifier.name``
(``"source:id_type:key"``); ``displayName`` resolves the source
display label backend-side via the comicbox ID-source map.
"""

from collections.abc import Mapping
from typing import Any, override

from comicbox.enums.maps.identifiers import ID_SOURCE_NAME_MAP
from rest_framework.fields import CharField, SerializerMethodField
from rest_framework.serializers import IntegerField, ListField, Serializer, URLField

from codex.serializers.browser.mixins import BrowserAggregateSerializerMixin
from codex.serializers.models.comic import ComicSerializer
from codex.serializers.models.named import StoryArcNumberSerializer

PREFETCH_PREFIX = "attached_"

# Backend mirror of the frontend's HEAD_ROLES precedence — kept in
# sync manually since the v3 frontend constant lives in
# ``frontend/src/stores/metadata.js``. The values are lowercase for
# case-insensitive matching against ``CreditRole.name``.
HEAD_ROLES: tuple[str, ...] = (
    "writer",
    "author",
    "plotter",
    "plot",
    "script",
    "scripter",
    "story",
    "interviewer",
    "translator",
    "artist",
    "penciller",
    "breakdowns",
    "pencils",
    "illustrator",
    "layouts",
    "inker",
    "finishes",
    "inks",
    "embellisher",
    "inkassists",
    "colorist",
    "colorer",
    "colourer",
    "colors",
    "colours",
    "colordesigner",
    "colorflats",
    "colorseparations",
    "designer",
    "digitalarttechnician",
    "graytone",
    "letterer",
    "cover",
    "covers",
    "coverartist",
    "editor",
    "edits",
    "editing",
)
_HEAD_ROLES_INDEX: Mapping[str, int] = {
    role: idx for idx, role in enumerate(HEAD_ROLES)
}

# IdentifierSource.name → display label (e.g. ``"comicvine"`` →
# ``"ComicVine"``). Resolved from comicbox so a stale label can be
# fixed in one place. Empty source falls through to "".
_SOURCE_DISPLAY_MAP: Mapping[str, str] = {
    key.value: value for key, value in ID_SOURCE_NAME_MAP.items()
}


def _last_name_key(person_name: str) -> str:
    """Sort key: last whitespace-delimited token, lowercased."""
    if not person_name:
        return ""
    return person_name.rsplit(" ", 1)[-1].lower()


def _role_sort_key(role: str) -> tuple[int, str]:
    """Sort roles by HEAD_ROLES precedence; everything else alphabetical."""
    bucket = _HEAD_ROLES_INDEX.get(role.lower(), len(HEAD_ROLES))
    return (bucket, role.lower())


def _person_payload(person) -> dict[str, Any]:
    if person is None:
        return {}
    return {
        "pk": person.pk,
        "name": person.name,
        "url": getattr(person, "url", "") or "",
    }


def pivot_credits(credit_rows) -> dict[str, list[dict[str, Any]]]:
    """Pivot ``[Credit]`` → ``{role_name: [person, ...]}``, sorted."""
    bucket: dict[str, list[dict[str, Any]]] = {}
    for credit in credit_rows or ():
        role = getattr(credit, "role", None)
        person = getattr(credit, "person", None)
        if person is None:
            continue
        role_name = role.name if role and role.name else "Other"
        bucket.setdefault(role_name, []).append(_person_payload(person))

    ordered: dict[str, list[dict[str, Any]]] = {}
    for role_name in sorted(bucket.keys(), key=_role_sort_key):
        persons = sorted(bucket[role_name], key=lambda p: _last_name_key(p["name"]))
        ordered[role_name] = persons
    return ordered


def shape_identifiers(identifiers) -> list[dict[str, Any]]:
    """Reshape ``[Identifier]`` → ``[{type, code, displayName, pk, url}]``."""
    out: list[dict[str, Any]] = []
    for identifier in identifiers or ():
        source = getattr(identifier, "source", None)
        source_name = source.name if source else ""
        display_name = _SOURCE_DISPLAY_MAP.get(source_name, source_name)
        out.append(
            {
                "pk": identifier.pk,
                "type": identifier.id_type,
                "code": identifier.key,
                "displayName": display_name,
                "url": identifier.url or "",
            }
        )
    return out


class CollectionSerializer(Serializer):
    """Serialize a group pk and name."""

    ids = ListField(child=IntegerField(), read_only=True)
    name = CharField(read_only=True)
    number_to = CharField(read_only=True)
    url = URLField(read_only=True)


class MetadataSerializer(BrowserAggregateSerializerMixin, ComicSerializer):
    """
    Aggregate stats for the comics selected in the metadata dialog.

    ``credits`` and ``identifiers`` ship in the backend-pivoted shapes
    described in :mod:`codex.serializers.browser.metadata`.
    """

    file_name = CharField(read_only=True)
    parent_folder_id = IntegerField(read_only=True, required=False)
    series_volume_count = IntegerField(read_only=True)
    volume_issue_count = IntegerField(read_only=True)

    # cover_pk and cover_custom_pk are annotated on group querysets by
    # BrowserAnnotateCoverView; Comic metadata skips the annotation and
    # falls back to ``obj.pk`` — so the frontend can always build a
    # ``/c/<pk>/cover.webp`` URL without a per-group branch.
    cover_pk = SerializerMethodField(read_only=True)
    cover_custom_pk = SerializerMethodField(read_only=True)

    def get_cover_pk(self, obj) -> int:
        """Return pre-computed cover pk, falling back to the object's own pk."""
        value = getattr(obj, "cover_pk", None)
        return value if value is not None else obj.pk

    def get_cover_custom_pk(self, obj) -> int | None:
        """Return the custom cover pk when present, else None."""
        return getattr(obj, "cover_custom_pk", None)

    publisher_list = CollectionSerializer(many=True, required=False)
    imprint_list = CollectionSerializer(many=True, required=False)
    series_list = CollectionSerializer(many=True, required=False)
    volume_list = CollectionSerializer(many=True, required=False)
    folder_list = CollectionSerializer(many=True, required=False)
    story_arc_list = CollectionSerializer(many=True, required=False)
    publisher = None  # pyright: ignore[reportIncompatibleUnannotatedOverride]
    imprint = None  # pyright: ignore[reportIncompatibleUnannotatedOverride]
    series = None  # pyright: ignore[reportIncompatibleUnannotatedOverride]
    volume = None  # pyright: ignore[reportIncompatibleUnannotatedOverride]

    credits = SerializerMethodField()  # pyright: ignore[reportIncompatibleUnannotatedOverride]
    identifiers = SerializerMethodField()  # pyright: ignore[reportIncompatibleUnannotatedOverride]
    story_arc_numbers = StoryArcNumberSerializer(
        source=f"{PREFETCH_PREFIX}story_arc_numbers", many=True, allow_null=True
    )

    @override
    def get_fields(self):
        """
        Reset ``source_attrs`` on the method fields.

        ``ModelSerializer`` resolves field sources at metaclass time;
        replacing ``credits``/``identifiers`` with
        :class:`SerializerMethodField` at the class level is not
        enough on its own because the parent ``ComicSerializer.Meta``
        machinery still wires up a ``source_attrs`` derived from the
        attached_* prefetch path. Clearing them here ensures the
        method bodies receive the Comic instance directly.
        """
        fields = super().get_fields()
        for name in ("credits", "identifiers"):
            field = fields.get(name)
            if field is not None:
                field.source_attrs = []  # type: ignore[assignment]
        return fields

    def get_credits(self, obj):
        """Pivot the prefetched credits list."""
        return pivot_credits(getattr(obj, "attached_credits", None))

    def get_identifiers(self, obj):
        """Reshape the prefetched identifiers list."""
        return shape_identifiers(getattr(obj, "attached_identifiers", None))

    class Meta(ComicSerializer.Meta):
        """Configure the model."""

        exclude = (  # pyright: ignore[reportIncompatibleUnannotatedOverride]
            *ComicSerializer.Meta.exclude,
            "publisher",
            "imprint",
            "series",
            "volume",
        )
