"""
Regression tests for the OPDS v2 publication serializer.

The OPDS2 manifest view emits role-bucketed credits whose dict keys
match the names in :data:`codex.views.opds.v2.manifest._MD_CREDIT_MAP`.
:class:`OPDS2PublicationMetadataSerializer` must declare a serializer
field for every one of those keys — DRF silently drops any mismatched
key. A typo in either side ⇒ that role's credits never surface in the
manifest payload.
"""

from types import SimpleNamespace

from django.test import SimpleTestCase

from codex.serializers.opds.v2.publication import (
    OPDS2PublicationMetadataSerializer,
)
from codex.views.opds.v2.manifest import _MD_CREDIT_MAP


class OPDS2PublicationMetadataSerializerCreditFieldsTestCase(SimpleTestCase):
    """Lock the view ↔ serializer credit-bucket contract."""

    def test_every_credit_bucket_key_has_a_serializer_field(self) -> None:
        """
        Every key in ``_MD_CREDIT_MAP`` must be a field on the serializer.

        This guards the typo class of bug: if the view emits ``penciller``
        but the serializer field is ``peniciller`` (or vice versa), DRF
        drops the bucket and the credit never reaches the client.
        """
        fields = OPDS2PublicationMetadataSerializer().fields
        missing = [key for key in _MD_CREDIT_MAP if key not in fields]
        assert not missing, (
            f"OPDS2PublicationMetadataSerializer missing fields for "
            f"_MD_CREDIT_MAP keys: {missing}"
        )

    def test_penciller_credit_surfaces_in_serialized_output(self) -> None:
        """
        A ``penciller`` bucket round-trips through the serializer.

        Mirrors the manifest view's emit shape: a dict with the
        ``penciller`` key holding an iterable of credit-like objects
        whose attributes match the contributor serializer fields.
        Pre-fix the field was named ``peniciller`` and this assertion
        failed.
        """
        credit = SimpleNamespace(
            name="Joe Penciller",
            role_name="Penciller",
            identifier="",
            links=(),
        )
        instance = {"title": "Test Issue", "penciller": [credit]}
        data = OPDS2PublicationMetadataSerializer(instance=instance).data
        assert "penciller" in data, (
            "penciller bucket dropped — serializer field name mismatch"
        )
        assert data["penciller"][0]["name"] == "Joe Penciller"
        assert data["penciller"][0]["role"] == "Penciller"
