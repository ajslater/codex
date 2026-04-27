"""Reader settings views."""

from types import MappingProxyType

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from codex.models import Comic, Folder, Series
from codex.models.named import StoryArc
from codex.models.settings import ClientChoices, SettingsReader
from codex.serializers.reader import (
    ReaderScopedUpdateSerializer,
    ReaderSettingsSerializer,
)
from codex.views.settings import NULL_VALUES, SettingsBaseView

# scope letter → (SettingsReader FK field, Comic FK for auto-resolve, Model for name)
# "g" = global (no FK).  "c" = comic.
# p/i/s/v all resolve to series scope.  "f" = folder.  "a" = story_arc.
#
_GLOBAL_SCOPE = "g"
_COMIC_SCOPE = "c"
_SCOPE_MAP = MappingProxyType(
    {
        _GLOBAL_SCOPE: (None, None, None),
        _COMIC_SCOPE: ("comic_id", None, None),
        "p": ("series_id", "series_id", Series),
        "i": ("series_id", "series_id", Series),
        "s": ("series_id", "series_id", Series),
        "v": ("series_id", "series_id", Series),
        "f": ("folder_id", "parent_folder_id", Folder),
        "a": ("story_arc_id", None, StoryArc),
    }
)


class ReaderSettingsBaseView(SettingsBaseView):
    """Reader settings — model config, defaults, reset, and scope lookups."""

    MODEL = SettingsReader
    CLIENT = ClientChoices.API
    FILTER_ARGS = MappingProxyType(
        {
            "comic__isnull": True,
            "series__isnull": True,
            "folder__isnull": True,
            "story_arc__isnull": True,
        }
    )
    CREATE_ARGS = MappingProxyType(
        {"comic": None, "series": None, "folder": None, "story_arc": None}
    )

    # ── Defaults & reset ────────────────────────────────────────────

    @classmethod
    def get_reader_default_params(cls) -> dict:
        """Derive reader default params from model field metadata."""
        return {
            key: cls._get_field_default(SettingsReader, key)
            for key in SettingsReader.DIRECT_KEYS
        }

    @classmethod
    def reset_reader_settings(cls, instance: SettingsReader) -> dict:
        """Reset reader DIRECT_KEYS to model defaults and return the params dict."""
        defaults = cls.get_reader_default_params()
        for key in SettingsReader.DIRECT_KEYS:
            setattr(instance, key, defaults[key])
        instance.save()
        return defaults

    # ── Auth + scope lookups ────────────────────────────────────────
    # (inlined from the former _ReaderSettingsAuthMixin / BookmarkAuthMixin)

    def _get_bookmark_auth_filter(self) -> dict[str, int | str | None]:
        """Filter only the current user's settings rows."""
        if self.request.user.is_authenticated:
            return {"user_id": self.request.user.pk}
        return {"session_id": self._ensure_session_key()}

    def _get_settings_lookup(self, **extra):
        """Build the base lookup for a SettingsReader query."""
        auth_filter = self._get_bookmark_auth_filter()
        return {"client": ClientChoices.API, **auth_filter, **extra}

    @staticmethod
    def _instance_to_dict(instance: SettingsReader | None) -> dict | None:
        """Convert a SettingsReader to a settings dict, or None."""
        if instance is None:
            return None
        return {key: getattr(instance, key) for key in instance.DIRECT_KEYS}

    def _get_global_settings(self) -> SettingsReader:
        """Get or create the global reader settings row."""
        base_lookup = self._get_settings_lookup()
        filter_kwargs = {
            **base_lookup,
            **self.FILTER_ARGS,
        }

        instance = SettingsReader.objects.filter(**filter_kwargs).first()
        if instance is not None:
            return instance
        return SettingsReader.objects.create(**base_lookup, **self.CREATE_ARGS)

    def _get_scoped_settings(self, scope_fk_field: str, scope_pk: int):
        """Get a scoped SettingsReader row or None."""
        lookup = self._get_settings_lookup(**{scope_fk_field: scope_pk})
        return SettingsReader.objects.filter(**lookup).first()

    def _get_or_create_scoped_settings(
        self, scope_fk_field: str, scope_pk: int
    ) -> SettingsReader:
        """Get or create a scoped SettingsReader row."""
        lookup = self._get_settings_lookup(**{scope_fk_field: scope_pk})
        instance = SettingsReader.objects.filter(**lookup).first()
        if instance is not None:
            return instance
        return SettingsReader.objects.create(**lookup)


class ReaderSettingsView(ReaderSettingsBaseView):
    """
    Consolidated reader settings endpoint.

    Mounted at both ``c/settings`` (no comic context) and
    ``c/<int:pk>/settings`` (comic context available).

    GET — request one or more scopes via ``?scopes=g,s,c``.
          When *pk* is in the URL the view can auto-resolve
          intermediate scope pks from the comic.
          ``?story_arc_pk=<id>`` is required for the *a* scope.

    PATCH — send ``scope`` (g/c/s/f/a) and, for every scope
            except *g*, ``scope_pk`` together with the settings
            fields to update.
    """

    serializer_class: type[BaseSerializer] | None = ReaderScopedUpdateSerializer

    # ── GET helpers ─────────────────────────────────────────────────

    def _resolve_scope_pk(
        self,
        scope: str,
        comic_fk: str | None,
        comic: Comic | None,
    ) -> int | None:
        """Return the scope pk for an intermediate scope, or None."""
        if scope == "a":
            raw = self.request.GET.get("story_arc_pk")
            return int(raw) if raw else None
        if comic and comic_fk:
            return getattr(comic, comic_fk, None)
        return None

    @staticmethod
    def _canonical_scope(scope: str) -> str:
        """Normalise arc-group aliases (p/i/v) to their canonical scope letter."""
        if scope in "piv":
            return "s"
        return scope

    def _get_scope(self, scope, scopes_out, comic, scope_info) -> None:
        config = _SCOPE_MAP.get(scope)
        if config is None:
            return
        fk_field, comic_fk, model = config
        canon = self._canonical_scope(scope)

        if scope == _GLOBAL_SCOPE:
            instance = self._get_global_settings()
            scopes_out[canon] = self._instance_to_dict(instance)

        elif scope == _COMIC_SCOPE:
            if comic:
                instance = self._get_scoped_settings("comic_id", comic.pk)
                scopes_out[canon] = self._instance_to_dict(instance)

        else:
            scope_pk = self._resolve_scope_pk(scope, comic_fk, comic)
            if scope_pk and fk_field:
                instance = self._get_scoped_settings(fk_field, scope_pk)
                scopes_out[canon] = self._instance_to_dict(instance)
                name = (
                    (
                        model.objects.filter(pk=scope_pk)
                        .values_list("name", flat=True)
                        .first()
                        or ""
                    )
                    if model
                    else ""
                )
                scope_info[canon] = {"pk": scope_pk, "name": name}

    # ── HTTP methods ────────────────────────────────────────────────

    @extend_schema(responses=None)
    def get(self, *args, **kwargs) -> Response:
        """Return settings for one or more scopes."""
        scopes_str = self.request.GET.get("scopes", _GLOBAL_SCOPE)
        requested = scopes_str.split(",")
        comic_pk: int | None = self.kwargs.get("pk")

        # Pre-fetch comic once if any non-g/c scope needs it.
        comic: Comic | None = None
        needed_comic_fks = set()
        for scope in requested:
            config = _SCOPE_MAP.get(scope)
            if config and config[1]:
                needed_comic_fks.add(config[1])
        if needed_comic_fks and comic_pk:
            comic = Comic.objects.only(*needed_comic_fks).get(pk=comic_pk)

        scopes_out: dict = {}
        scope_info: dict = {}

        for scope in requested:
            self._get_scope(scope, scopes_out, comic, scope_info)

        data = {"scopes": scopes_out, "scope_info": scope_info}
        return Response(data)

    @extend_schema(
        request=ReaderScopedUpdateSerializer,
        responses=ReaderSettingsSerializer,
    )
    def patch(self, *args, **kwargs) -> Response:
        """Update settings for a single scope."""
        serializer = self.get_serializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        scope = data.pop("scope")
        scope_pk = data.pop("scope_pk", None)

        config = _SCOPE_MAP.get(scope)
        if config is None:
            raise ValidationError({"scope": f"Invalid scope: {scope}"})

        if scope == _GLOBAL_SCOPE:
            # Reject null/blank updates for global to preserve defaults.
            data = {k: v for k, v in data.items() if v not in NULL_VALUES}
            instance = self._get_global_settings()
        else:
            if not scope_pk:
                raise ValidationError(
                    {"scope_pk": "scope_pk is required for non-global scopes."}
                )
            fk_field = config[0]
            instance = self._get_or_create_scoped_settings(fk_field, scope_pk)  # pyright: ignore[reportArgumentType], # ty: ignore[invalid-argument-type]

        for key, value in data.items():
            if key in instance.DIRECT_KEYS:
                setattr(instance, key, value)
        instance.save()

        result = self._instance_to_dict(instance)
        output_serializer = ReaderSettingsSerializer(result)
        return Response(output_serializer.data)

    @extend_schema(
        request=ReaderScopedUpdateSerializer,
        responses=ReaderSettingsSerializer,
    )
    def delete(self, *args, **kwargs) -> Response:
        """Reset settings for a single scope to model defaults."""
        serializer = self.get_serializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        scope = data.get("scope", _GLOBAL_SCOPE)
        scope_pk = data.get("scope_pk")

        config = _SCOPE_MAP.get(scope)
        if config is None:
            raise ValidationError({"scope": f"Invalid scope: {scope}"})

        if scope == _GLOBAL_SCOPE:
            # Global scope: reset to model defaults (can't delete).
            instance = self._get_global_settings()
            result = self.reset_reader_settings(instance)
        else:
            if not scope_pk:
                raise ValidationError(
                    {"scope_pk": "scope_pk is required for non-global scopes."}
                )
            fk_field = config[0]
            # Delete the scoped row entirely — absence means "inherit".
            lookup = self._get_settings_lookup(**{fk_field: scope_pk})  # pyright: ignore[reportCallIssue], # ty: ignore[invalid-argument-type]
            SettingsReader.objects.filter(**lookup).delete()
            result = None

        output_serializer = ReaderSettingsSerializer(result)
        return Response(output_serializer.data)
