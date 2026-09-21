"""Admin flag serializers."""

from types import MappingProxyType
from typing import override

from rest_framework.serializers import PrimaryKeyRelatedField, ValidationError

from codex.choices.admin import AdminFlagChoices
from codex.choices.browser import BROWSER_TOP_COLLECTION_CHOICES
from codex.choices.limits import (
    BROWSER_MAX_OBJ_PER_PAGE,
    CUSTOM_COVER_MAX_UPLOAD_MB,
)
from codex.models import AdminFlag, AgeRatingMetron
from codex.serializers.models.base import BaseModelSerializer


class AdminFlagSerializer(BaseModelSerializer):
    """Admin Flag Serializer."""

    # The two age-rating flags (``AR`` / ``AA``) use this FK; other
    # flags leave it NULL and stick with ``on`` / ``value``.
    age_rating_metron = PrimaryKeyRelatedField(
        queryset=AgeRatingMetron.objects.all(),
        allow_null=True,
        required=False,
    )

    #: Flags whose ``value`` is an integer, and the bounds it must fall
    #: in. They share a text column with every other flag, so a
    #: ``MinValueValidator`` cannot live on the field -- this method is
    #: the only place the bound can be expressed.
    _INT_RANGES = MappingProxyType(
        {
            AdminFlagChoices.CUSTOM_COVER_MAX_UPLOAD_MB.value: (
                CUSTOM_COVER_MAX_UPLOAD_MB
            ),
            AdminFlagChoices.BROWSER_MAX_OBJ_PER_PAGE.value: (BROWSER_MAX_OBJ_PER_PAGE),
        }
    )

    def _validate_collection(self, attrs) -> None:
        """
        ``BROWSER_DEFAULT_COLLECTION`` constrains ``value`` to a top collection.

        The route URL is derived from the value at read time via
        ``admin_default_route_for``. Note we validate against the
        top-collection set, not ``BROWSER_ROUTE_COLLECTION_CHOICES`` --
        the ``root`` pseudo-collection is not a valid flag value, only a
        derived URL.
        """
        value = attrs.get("value", self.instance.value)
        if value not in BROWSER_TOP_COLLECTION_CHOICES:
            valid = tuple(BROWSER_TOP_COLLECTION_CHOICES)
            reason = f"value must be one of {valid}"
            raise ValidationError({"value": reason})

    def _validate_int_range(self, attrs, bounds) -> None:
        """
        Bound an integer flag.

        ``get_admin_flag_int`` honours "0" and "-1" -- only an empty or
        unparseable value falls back to the default -- so nothing
        downstream rejects them. A saved ``-1`` for the upload cap makes
        every upload fail with "Upload exceeds -1 MB limit", and a saved
        ``0`` for the page size is a live 500: ``ceil(count / 0)``
        raises ZeroDivisionError and browsing stops working entirely
        until an admin fixes the flag.
        """
        raw = attrs.get("value", self.instance.value)
        low, high = bounds
        try:
            value = int(raw)
        except (TypeError, ValueError):
            reason = f"value must be a whole number between {low} and {high}"
            raise ValidationError({"value": reason}) from None
        if not low <= value <= high:
            reason = f"value must be between {low} and {high}"
            raise ValidationError({"value": reason})

    @override
    def validate(self, attrs):
        """Per-flag value validation."""
        if not self.instance:
            return attrs
        key = self.instance.key
        if key == AdminFlagChoices.BROWSER_DEFAULT_COLLECTION.value:
            self._validate_collection(attrs)
        elif bounds := self._INT_RANGES.get(key):
            self._validate_int_range(attrs, bounds)
        return attrs

    class Meta(BaseModelSerializer.Meta):
        """Specify Model."""

        model = AdminFlag
        fields = ("key", "on", "value", "age_rating_metron")
        read_only_fields = ("key",)

    class JSONAPIMeta:
        """JSON:API resource_name for the v4 admin renderer."""

        resource_name = "flags"
