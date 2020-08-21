"""Codex django forms."""
from django.db.models import CharField
from django.db.models import F
from django.db.models.functions import Cast


class VueModelChoice:
    """A model choice that will go to vue."""

    @staticmethod
    def encode_query_for_vue(choices):
        """Encode choices for vue."""
        choices = list(choices)

        # Vue (and html) handle null values very poorly. Use -1.
        for index, choice in enumerate(choices):
            if choice.get("value") is None:
                choices[index] = {"value": -1, "text": "None"}
        return choices


class DecadeFilterChoice(VueModelChoice):
    """Choices for the decade filter."""

    @classmethod
    def get_vue_choices(cls, model):
        """Get the decades in the db."""
        choices = (
            model.distinct()
            .annotate(value=F("comic__decade"), text=Cast("comic__decade", CharField()))
            .order_by("comic__decade")
            .values("value", "text")
        )
        return cls.encode_query_for_vue(choices)


class CharactersFilterChoice(VueModelChoice):
    """Choices for character filter."""

    @classmethod
    def get_vue_choices(cls, model):
        """Get the characters from the db."""
        choices = (
            model
            # model should not allow null, wtf?
            .exclude(comic__characters__name=None)
            .distinct()
            .annotate(
                value=F("comic__characters__pk"), text=F("comic__characters__name")
            )
            .order_by("text")
            .values("value", "text")
        )
        return cls.encode_query_for_vue(choices)
