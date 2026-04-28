"""Admin flag serializers."""

from typing import override

from rest_framework.serializers import PrimaryKeyRelatedField, ValidationError

from codex.choices.admin import AdminFlagChoices
from codex.choices.browser import BROWSER_TOP_GROUP_CHOICES
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

    @override
    def validate(self, attrs):
        """
        Per-flag value validation.

        ``BROWSER_DEFAULT_GROUP`` constrains ``value`` to one of the
        ``BROWSER_TOP_GROUP_CHOICES`` keys; the route URL is derived
        from the value at read time via ``admin_default_route_for``.
        Note we validate against the top-group set, not
        ``BROWSER_ROUTE_CHOICES`` — the ``r`` (Root) pseudo-group is
        not a valid flag value, only a derived URL.
        """
        if (
            self.instance
            and self.instance.key == AdminFlagChoices.BROWSER_DEFAULT_GROUP.value
        ):
            value = attrs.get("value", self.instance.value)
            if value not in BROWSER_TOP_GROUP_CHOICES:
                valid = tuple(BROWSER_TOP_GROUP_CHOICES)
                reason = f"value must be one of {valid}"
                raise ValidationError({"value": reason})
        return attrs

    class Meta(BaseModelSerializer.Meta):
        """Specify Model."""

        model = AdminFlag
        fields = ("key", "on", "value", "age_rating_metron")
        read_only_fields = ("key",)
