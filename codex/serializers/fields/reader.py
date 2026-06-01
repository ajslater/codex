"""Reader Fields."""

from codex.group import Group
from codex.models.choices import ReadingDirectionChoices
from codex.models.settings import FitToChoices
from codex.serializers.fields.base import CodexChoiceField

# Browse groups a comic can be read "within". All collection-valued now;
# p/i/root have no arc of their own (params collapses them to series).
VALID_ARC_GROUPS = (Group.SERIES, Group.VOLUME, Group.FOLDER, Group.ARC)


class FitToField(CodexChoiceField):
    """Reader FitTo Field."""

    class_choices = FitToChoices.values


class ReadingDirectionField(CodexChoiceField):
    """Reading Direction Field."""

    class_choices = ReadingDirectionChoices.values


class ArcGroupField(CodexChoiceField):
    """Arc Group Field."""

    class_choices = VALID_ARC_GROUPS
