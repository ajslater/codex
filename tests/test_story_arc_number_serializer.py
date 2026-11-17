"""The metadata payload names an arc apart from its display form."""

from django.test import TestCase

from codex.models import StoryArc, StoryArcNumber
from codex.serializers.models.named import StoryArcNumberSerializer


class StoryArcNumberSerializerTestCase(TestCase):
    """The tag editor needs the arc's own name and its number."""

    def test_arc_name_and_number(self) -> None:
        """``name`` reads ``Arc:3``; ``arc_name`` is the arc itself."""
        arc = StoryArc.objects.create(name="Civil War")
        number = StoryArcNumber.objects.create(story_arc=arc, number=3)
        data = StoryArcNumberSerializer(number).data
        assert data["name"] == "Civil War:3"
        assert data["arc_name"] == "Civil War"
        assert data["number"] == 3  # noqa: PLR2004
