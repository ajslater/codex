"""Reader Fields."""

from codex.collection import READER_REPRINT_COLLECTION, Collection
from codex.models.choices import ReadingDirectionChoices
from codex.models.settings import FitToChoices
from codex.serializers.fields.base import CodexChoiceField

# Collections a comic can be read "within". Mostly browse collections;
# p/i/root have no arc of their own (params collapses them to series).
# ``reprints`` is the one reader-only entry — a reprint series is a
# reading order without a browse route.
VALID_ARC_COLLECTIONS = (
    Collection.SERIES,
    Collection.VOLUME,
    Collection.FOLDER,
    Collection.ARC,
    READER_REPRINT_COLLECTION,
)


class FitToField(CodexChoiceField):
    """Reader FitTo Field."""

    class_choices = FitToChoices.values


class ReadingDirectionField(CodexChoiceField):
    """Reading Direction Field."""

    class_choices = ReadingDirectionChoices.values


class ArcCollectionField(CodexChoiceField):
    """Arc Collection Field."""

    class_choices = VALID_ARC_COLLECTIONS
