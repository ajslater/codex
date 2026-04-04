"""Reader Fields."""

from codex.models.choices import ReadingDirectionChoices
from codex.models.settings import FitToChoices
from codex.serializers.fields.base import CodexChoiceField
from codex.views.const import FOLDER_GROUP, STORY_ARC_GROUP

VALID_ARC_GROUPS = ("s", "v", FOLDER_GROUP, STORY_ARC_GROUP)


class FitToField(CodexChoiceField):
    """Reader FitTo Field."""

    class_choices = FitToChoices.values


class ReadingDirectionField(CodexChoiceField):
    """Reading Direction Field."""

    class_choices = ReadingDirectionChoices.values


class ArcGroupField(CodexChoiceField):
    """Arc Group Field."""

    class_choices = VALID_ARC_GROUPS
