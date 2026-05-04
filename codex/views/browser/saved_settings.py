"""Saved browser settings views."""

from types import MappingProxyType

from loguru import logger
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from codex.models.age_rating import AgeRating, AgeRatingMetron
from codex.models.base import NamedModel
from codex.models.identifier import IdentifierSource
from codex.models.named import (
    Character,
    Country,
    CreditPerson,
    Genre,
    Language,
    Location,
    OriginalFormat,
    SeriesGroup,
    Story,
    StoryArc,
    Tag,
    Tagger,
    Team,
    Universe,
)
from codex.models.settings import (
    ClientChoices,
    SettingsBrowser,
    SettingsBrowserFilters,
    SettingsBrowserLastRoute,
)
from codex.serializers.browser.saved import (
    SavedBrowserSettingsListSerializer,
    SavedBrowserSettingsSaveSerializer,
    SavedSettingsLoadSerializer,
)
from codex.views.auth import AuthFilterGenericAPIView
from codex.views.settings import (
    BROWSER_CREATE_ARGS,
    BROWSER_FILTER_ARGS,
    SETTINGS_BROWSER_SELECT_RELATED,
    SettingsBaseView,
)

# Map filter field names to the model whose PKs they store.
_FILTER_FK_MODEL_MAP = MappingProxyType(
    {
        "age_rating_metron": AgeRatingMetron,
        "age_rating_tagged": AgeRating,
        "characters": Character,
        "country": Country,
        "credits": CreditPerson,
        "genres": Genre,
        "identifier_source": IdentifierSource,
        "language": Language,
        "locations": Location,
        "original_format": OriginalFormat,
        "series_groups": SeriesGroup,
        "stories": Story,
        "story_arcs": StoryArc,
        "tagger": Tagger,
        "tags": Tag,
        "teams": Team,
        "universes": Universe,
    }
)


def _validate_filter_field(
    filters_data: dict, field: str, model: type[NamedModel], warnings: list[str]
):
    """Validate one filter field by existing models."""
    pk_list = filters_data.get(field)
    if not pk_list or not isinstance(pk_list, list):
        return
    # Skip null sentinel values
    real_pks = frozenset({pk for pk in pk_list if pk is not None})
    if not real_pks:
        return
    existing_pks = frozenset(
        model.objects.filter(pk__in=real_pks).values_list("pk", flat=True)
    )
    if bad_pks := frozenset(real_pks - existing_pks):
        logger.info(
            f"Saved settings filter {field!r}: removing invalid PK(s): {sorted(bad_pks)}"
        )
        # Keep None sentinels plus valid PKs
        cleaned = frozenset(pk_list) - bad_pks
        filters_data[field] = cleaned
        warnings.append(field)


def _validate_filter_pks(
    filters_data: dict,
    filters_obj: SettingsBrowserFilters | None = None,
) -> list[str]:
    """
    Validate FK-based filter PKs and strip invalid ones.

    Modifies *filters_data* in place.  When *filters_obj* is provided the
    cleaned values are persisted back to the database so subsequent loads
    skip the validation.

    Returns a list of filter field names that had invalid PKs removed.
    """
    warnings: list[str] = []
    for field, model in _FILTER_FK_MODEL_MAP.items():
        _validate_filter_field(filters_data, field, model, warnings)
    # Persist the cleaned filters back to the row.
    if warnings and filters_obj is not None:
        for field in warnings:
            setattr(filters_obj, field, filters_data[field])
        filters_obj.save()

    return warnings


class _SavedSettingsOwnerMixin:
    """Shared user/session resolution for saved-settings views."""

    def _get_user_and_session(self):
        user = self.request.user  # pyright: ignore [reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        if user and getattr(user, "pk", None):
            return user, None
        if not self.request.session.session_key:  # pyright: ignore [reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
            self.request.session.save()  # pyright: ignore [reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        return None, self.request.session.session_key  # pyright: ignore [reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]

    def _owner_kwargs(self):
        user, session_key = self._get_user_and_session()
        if user:
            return {"user": user}
        return {"session_id": session_key}


class SavedBrowserSettingsListView(_SavedSettingsOwnerMixin, AuthFilterGenericAPIView):
    """GET: list saved settings.  POST: save current settings with a name."""

    serializer_class: type[BaseSerializer] | None = SavedBrowserSettingsListSerializer

    def get(self, *args, **kwargs) -> Response:
        """Return list of saved setting names."""
        owner = self._owner_kwargs()
        qs = (
            SettingsBrowser.objects.filter(client=ClientChoices.API, **owner)
            .exclude(name="")
            .order_by("name")
            .values("pk", "name")
        )
        serializer = self.get_serializer({"savedSettings": list(qs)})
        return Response(serializer.data)

    @staticmethod
    def _copy_settings(source: SettingsBrowser, target: SettingsBrowser):
        """Copy all settings columns from source to target."""
        for key in SettingsBrowser.DIRECT_KEYS:
            setattr(target, key, getattr(source, key))
        target.search = source.search
        target.show = source.show
        target.save()

        # Copy filters
        src_filters = source.filters  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        tgt_filters = target.filters  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        for key in SettingsBrowserFilters.FILTER_KEYS:
            setattr(tgt_filters, key, getattr(src_filters, key))
        tgt_filters.save()

        # Copy last_route
        src_route = source.last_route  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        tgt_route = target.last_route  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        tgt_route.group = src_route.group
        tgt_route.pks = src_route.pks
        tgt_route.page = src_route.page
        tgt_route.save()

    def post(self, *args, **kwargs) -> Response:
        """Save current settings with a name.  Overwrites if name exists."""
        serializer = SavedBrowserSettingsSaveSerializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data["name"]

        user, session_key = self._get_user_and_session()
        owner = {"user": user} if user else {"session_id": session_key}

        # Find the current (unnamed) settings row.
        current = (
            SettingsBrowser.objects.filter(client=ClientChoices.API, name="", **owner)
            .select_related(*SETTINGS_BROWSER_SELECT_RELATED)
            .first()
        )
        if not current:
            return Response({"detail": "No current settings found."}, status=404)

        # Check for existing saved setting with the same name.
        existing = (
            SettingsBrowser.objects.filter(client=ClientChoices.API, name=name, **owner)
            .select_related(*SETTINGS_BROWSER_SELECT_RELATED)
            .first()
        )
        if existing:
            self._copy_settings(current, existing)
            created = False
        else:
            # Create new named setting by cloning the current row.
            new_sb = SettingsBrowser.objects.create(
                user=user,
                session_id=session_key,
                client=ClientChoices.API,
                name=name,
                top_group=current.top_group,
                order_by=current.order_by,
                order_reverse=current.order_reverse,
                search=current.search,
                custom_covers=current.custom_covers,
                dynamic_covers=current.dynamic_covers,
                twenty_four_hour_time=current.twenty_four_hour_time,
                always_show_filename=current.always_show_filename,
                show=current.show,
            )
            # Clone filters
            src_filters = current.filters  # pyright: ignore[reportAttributeAccessIssue]
            new_filters = SettingsBrowserFilters(browser=new_sb)
            for key in SettingsBrowserFilters.FILTER_KEYS:
                val = getattr(src_filters, key)
                if isinstance(val, list):
                    val = list(val)
                setattr(new_filters, key, val)
            new_filters.save()

            # Clone last_route
            src_route = current.last_route  # pyright: ignore[reportAttributeAccessIssue]
            SettingsBrowserLastRoute.objects.create(
                browser=new_sb,
                group=src_route.group,
                pks=list(src_route.pks) if src_route.pks else [0],
                page=src_route.page,
            )
            created = True

        return Response(
            {"name": name, "created": created},
            status=201 if created else 200,
        )


class SavedBrowserSettingsLoadView(SettingsBaseView):
    """GET: load a saved setting by pk.  DELETE: delete a saved setting."""

    MODEL = SettingsBrowser
    CLIENT = ClientChoices.API
    FILTER_ARGS = BROWSER_FILTER_ARGS
    CREATE_ARGS = BROWSER_CREATE_ARGS

    serializer_class: type[BaseSerializer] | None = SavedSettingsLoadSerializer

    def _owner_kwargs(self):
        user = self._get_request_user()
        session_key = self._ensure_session_key()
        if user:
            return {"user": user}
        return {"session_id": session_key}

    def get(self, *args, **kwargs) -> Response:
        """Load saved settings by pk and validate filter PKs."""
        pk = self.kwargs["pk"]
        owner = self._owner_kwargs()

        saved = (
            SettingsBrowser.objects.filter(pk=pk, client=ClientChoices.API, **owner)
            .exclude(name="")
            .select_related(*SETTINGS_BROWSER_SELECT_RELATED)
            .first()
        )
        if not saved:
            return Response({"detail": "Saved setting not found."}, status=404)

        # Build the settings dict.
        data = self.browser_instance_to_dict(saved)

        # Validate filter PKs, persist cleaned data, and collect warnings.
        filters_obj = saved.filters  # pyright: ignore[reportAttributeAccessIssue]
        filter_warnings = _validate_filter_pks(data.get("filters", {}), filters_obj)

        result = {
            "settings": data,
            "filterWarnings": filter_warnings,
        }
        serializer = self.get_serializer(result)
        return Response(serializer.data)

    def delete(self, *args, **kwargs) -> Response:
        """Delete saved settings by pk."""
        pk = self.kwargs["pk"]
        owner = self._owner_kwargs()

        deleted_count, _ = (
            SettingsBrowser.objects.filter(pk=pk, client=ClientChoices.API, **owner)
            .exclude(name="")
            .delete()
        )

        if not deleted_count:
            return Response({"detail": "Saved setting not found."}, status=404)
        return Response(status=204)
