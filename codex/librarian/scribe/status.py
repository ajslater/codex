"""Librarian Status for scribe bulk writes."""

from django.db.models import TextChoices


class ScribeStatusTypes(TextChoices):
    """
    Keys for Scribe tasks.

    Actual text is taken by titlecasing the left side.
    """

    UPDATE_GROUP_TIMESTAMPS = "IGU"
