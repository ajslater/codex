"""View for marking comics read and unread."""
import pycountry
from caseconverter import snakecase
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from codex.logger.logging import get_logger
from codex.models import Comic, CreatorPerson, StoryArc
from codex.serializers.browser import (
    BrowserChoicesSerializer,
    BrowserFilterChoicesSerializer,
)
from codex.serializers.models import PyCountrySerializer
from codex.views.auth import IsAuthenticatedOrEnabledNonUsers
from codex.views.browser.base import BrowserBaseView

LOG = get_logger(__name__)


class BrowserChoicesViewBase(BrowserBaseView):
    """Get choices for filter dialog."""

    permission_classes = [IsAuthenticatedOrEnabledNonUsers]

    _CREATORS_PERSON_REL = "creators__person"
    _STORY_ARC_REL = "story_arc_numbers__story_arc"
    _NULL_NAMED_ROW = {"pk": -1, "name": "_none_"}

    def get_field_choices_query(self, field_name, comic_qs):
        """Get distinct values for the field."""
        return comic_qs.values_list(field_name, flat=True).distinct()

    @classmethod
    def get_m2m_field_query(cls, comic_qs, model):
        """Get distinct m2m value objects for the relation."""
        return model.objects.filter(pk__in=comic_qs).values("pk", "name").distinct()

    @staticmethod
    def does_m2m_null_exist(comic_qs, rel):
        """Get if null values exists for an m2m field."""
        return comic_qs.filter(**{f"{rel}__isnull": True}).exists()

    def _get_rel_and_model(self, field_name):
        """Return the relation and model for the field name."""
        if field_name == self.CREATOR_PERSON_UI_FIELD:
            rel = self._CREATORS_PERSON_REL
            model = CreatorPerson
        elif field_name == self.STORY_ARC_UI_FIELD:
            rel = self._STORY_ARC_REL
            model = StoryArc
        else:
            remote_field = getattr(
                Comic._meta.get_field(field_name), "remote_field", None
            )
            rel = field_name
            model = remote_field.model if remote_field else None

        rel = self.rel_prefix + rel

        return rel, model

    def get_object(self):
        """Get the comic subquery use for the choices."""
        object_filter, _ = self.get_query_filters(self.model, True)
        return self.model.objects.filter(object_filter)

    def _set_model(self):
        """Set the model to query."""
        group = self.kwargs["group"]
        if group == self.ROOT_GROUP:
            group = self.params.get("top_group", "p")
        self.model = self.GROUP_MODEL_MAP[group]

class BrowserChoicesAvailableView(BrowserChoicesViewBase):
    """Get choices for filter dialog."""

    serializer_class = BrowserFilterChoicesSerializer

    def _get_field_choices_count(self, field_name, comic_qs):
        """Create a pk:name object for fields without tables."""
        return self.get_field_choices_query(field_name, comic_qs).count()

    @classmethod
    def _get_m2m_field_choices_count(cls, rel, comic_qs, model):
        """Get choices with nulls where there are nulls."""
        count = cls.get_m2m_field_query(comic_qs, model).count()

        # Detect if there are null choices.
        # Regretabbly with another query, but doing a forward query
        # on the comic above restricts all results to only the filtered
        # rows. :(
        if cls.does_m2m_null_exist(comic_qs, rel):
            count += 1

        return count

    @extend_schema(request=BrowserBaseView.input_serializer_class)
    def get(self, *args, **kwargs):
        """Return all choices with more than one choice."""
        self.parse_params()
        self._set_model()
        self.set_rel_prefix(self.model)
        comic_qs = self.get_object()

        data = {}
        for field_name in self.serializer_class().get_fields():  # type: ignore
            if field_name == "story_arcs" and self.model == StoryArc:
                # don't allow filtering on story arc in story arc view.
                continue
            rel, m2m_model = self._get_rel_and_model(field_name)

            if m2m_model:
                count = self._get_m2m_field_choices_count(rel, comic_qs, m2m_model)
            else:
                count = self._get_field_choices_count(rel, comic_qs)

            filters = self.params.get("filters", {})
            data[field_name] = count > 1 or field_name in filters

        serializer = self.get_serializer(data)
        return Response(serializer.data)


class BrowserChoicesView(BrowserChoicesViewBase):
    """Get choices for filter dialog."""

    serializer_class = BrowserChoicesSerializer

    def _get_field_choices(self, field_name, comic_qs):
        """Create a pk:name object for fields without tables."""
        qs = self.get_field_choices_query(field_name, comic_qs)

        if field_name == "country":
            lookup = pycountry.countries
        elif field_name == "language":
            lookup = pycountry.languages
        else:
            lookup = None

        choices = []
        for val in qs:
            name = PyCountrySerializer.lookup_name(lookup, val) if lookup else val
            choices.append({"pk": val, "name": name})

        return choices

    @classmethod
    def _get_m2m_field_choices(cls, rel, comic_qs, model):
        """Get choices with nulls where there are nulls."""
        qs = cls.get_m2m_field_query(comic_qs, model)

        # Detect if there are null choices.
        # Regretabbly with another query, but doing a forward query
        # on the comic above restrcts all results to only the filtered
        # rows. :(
        if cls.does_m2m_null_exist(comic_qs, rel):
            choices = list(qs)
            choices.append(cls._NULL_NAMED_ROW)
        else:
            choices = qs
        return choices

    @extend_schema(request=BrowserBaseView.input_serializer_class)
    def get(self, *args, **kwargs):
        """Return all choices with more than one choice."""
        self.parse_params()
        self._set_model()
        self.set_rel_prefix(self.model)

        field_name = snakecase(self.kwargs["field_name"])

        rel, m2m_model = self._get_rel_and_model(field_name)

        comic_qs = self.get_object()
        if m2m_model:
            choices = self._get_m2m_field_choices(rel, comic_qs, m2m_model)
        else:
            choices = self._get_field_choices(rel, comic_qs)

        serializer = self.get_serializer(choices, many=True)
        return Response(serializer.data)
