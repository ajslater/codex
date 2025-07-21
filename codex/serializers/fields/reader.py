"""Reader Fields."""

from codex.models import Bookmark
from codex.models.comic import ReadingDirection
from codex.serializers.fields.base import CodexChoiceField
from codex.views.const import FOLDER_GROUP, STORY_ARC_GROUP

VALID_ARC_GROUPS = ("s", "v", FOLDER_GROUP, STORY_ARC_GROUP)


class FitToField(CodexChoiceField):
    """Bookmark FitTo Fieild."""

    class_choices = Bookmark.FitTo.values


class ReadingDirectionField(CodexChoiceField):
    """Reading Direction Field."""

    class_choices = ReadingDirection.values


class ArcGroupField(CodexChoiceField):
    """Arc Group Field."""

    class_choices = VALID_ARC_GROUPS
