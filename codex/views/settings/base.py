"""Base classes for settings."""

from abc import ABC
from collections.abc import Mapping, MutableMapping, Sequence
from copy import deepcopy
from types import MappingProxyType

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from loguru import logger

from codex.choices.browser import DEFAULT_BROWSER_ROUTE
from codex.models.settings import (
    ClientChoices,
    SettingsBase,
    SettingsBrowser,
    SettingsBrowserFilters,
    SettingsBrowserLastRoute,
    SettingsBrowserShow,
    SettingsReader,
)
from codex.views.auth import AuthFilterGenericAPIView
from codex.views.const import FOLDER_GROUP, STORY_ARC_GROUP
from codex.views.settings.const import (
    BROWSER_CREATE_ARGS,
    BROWSER_FILTER_ARGS,
    SETTINGS_BROWSER_SELECT_RELATED,
    SHOW_KEYS,
)


class SettingsReadView(AuthFilterGenericAPIView, ABC):
    """
    Core settings model access.

    Scope arguments shared by browser and reader settings classes. Provides the low-level read/write interface to the settings database
    models and the read-only public helpers that only need to *get*
    settings values (get_from_settings, get_last_route).

    Subclasses must set MODEL, CLIENT, FILTER_ARGS, and CREATE_ARGS.

    Views that only need to read settings (e.g. the frontend IndexView)
    should inherit from a concrete subclass like BrowserSettingsReadView.
    """

    # Must override these in concrete subclasses.
    MODEL: type[SettingsReader | SettingsBrowser]
    CLIENT: ClientChoices
    FILTER_ARGS: Mapping = MappingProxyType({})
    CREATE_ARGS: Mapping = MappingProxyType({})

    # Browser settings config for cross-reading (e.g. get_last_route from
    # a reader view).  Defaults to API browser settings; OPDS views
    # override BROWSER_CLIENT.
    BROWSER_MODEL: type[SettingsBrowser] = SettingsBrowser
    BROWSER_CLIENT: ClientChoices = ClientChoices.API

    # Settings model helpers

    def _ensure_session_key(self) -> str | None:
        """Ensure the Django session is saved and return its key."""
        if not self.request.session.session_key:
            self.request.session.save()
        return self.request.session.session_key

    def _get_request_user(self):
        """Return the authenticated user or None."""
        user = self.request.user
        if user and getattr(user, "pk", None):
            return user
        return None

    @staticmethod
    def _get_or_create_settings_user(
        model: type[SettingsReader | SettingsBrowser],
        user: AbstractBaseUser | AnonymousUser,
        session_key: str | None,
        base_filter: Mapping,
        only: Sequence[str] | None,
    ) -> SettingsBrowser | SettingsReader | None:
        instance = model.objects.filter(user=user, **base_filter)
        if model is SettingsBrowser:
            instance = instance.select_related(*SETTINGS_BROWSER_SELECT_RELATED)
        if only:
            instance = instance.only(*only)
        instance = instance.first()
        if instance is None:
            return None

        if session_key and instance.session_id != session_key:  # pyright: ignore[reportAttributeAccessIssue]
            # Discard any anonymous row that owns the new session so
            # the unique constraint isn't violated.
            model.objects.filter(
                session_id=session_key, user__isnull=True, **base_filter
            ).delete()
            instance.session_id = session_key  # pyright: ignore[reportAttributeAccessIssue]
            instance.save(update_fields=("session_id", "updated_at"))
        return instance

    @staticmethod
    def _get_or_create_settings_session(
        model: type[SettingsReader | SettingsBrowser],
        user: AbstractBaseUser | AnonymousUser | None,
        session_key: str,
        base_filter: Mapping,
        only: Sequence[str] | None,
    ):
        instance = model.objects.filter(session_id=session_key, **base_filter)
        if model is SettingsBrowser:
            instance = instance.select_related(*SETTINGS_BROWSER_SELECT_RELATED)
        elif only:
            instance = instance.only(*only)
        instance = instance.first()
        if instance is None:
            return None

        if user and instance.user_id is None:  # pyright: ignore[reportAttributeAccessIssue]
            # Promote anonymous row to a user row (first login).
            instance.user = user
            instance.save(update_fields=("user_id", "updated_at"))
        return instance

    @staticmethod
    def _create_browser_settings(user, session_key, client, create_args):
        """Create a SettingsBrowser with its related show/filters/last_route."""
        show, _ = SettingsBrowserShow.objects.get_or_create(
            p=True,
            i=False,
            s=True,
            v=False,
        )
        instance = SettingsBrowser.objects.create(
            user=user,
            session_id=session_key,
            client=client,
            show=show,
            **create_args,
        )
        SettingsBrowserFilters.objects.create(browser=instance)
        SettingsBrowserLastRoute.objects.create(browser=instance)
        # Re-fetch with select_related so the reverse OneToOne accessors work.
        return SettingsBrowser.objects.select_related(
            *SETTINGS_BROWSER_SELECT_RELATED
        ).get(pk=instance.pk)

    def _get_or_create_settings(
        self,
        model: type[SettingsReader | SettingsBrowser],
        client: ClientChoices,
        filter_args: Mapping,
        create_args: Mapping,
        only: Sequence[str] | None = None,
    ) -> SettingsBase:
        """
        Look up (or create) the settings row for the current user / session.

        Priority: authenticated user row > session row > create new.
        Handles login transitions (promoting anonymous session rows to user
        rows) and keeps the session FK current.
        """
        user = self._get_request_user()
        session_key = self._ensure_session_key()

        base_filter = {"client": client, **filter_args}

        # 1. Authenticated user — look up by user first.
        if user and (
            instance := self._get_or_create_settings_user(
                model, user, session_key, base_filter, only
            )
        ):
            return instance

        # 2. Try by session.
        if session_key and (
            instance := self._get_or_create_settings_session(
                model, user, session_key, base_filter, only
            )
        ):
            return instance

        # 3. Nothing found — create.
        if model is SettingsBrowser:
            return self._create_browser_settings(
                user,
                session_key,
                client,
                create_args,
            )
        return model.objects.create(
            user=user,
            session_id=session_key,
            client=client,
            **create_args,
        )

    @staticmethod
    def browser_instance_to_dict(instance: SettingsBrowser) -> dict:
        """
        Convert a SettingsBrowser instance to the params dict.

        The serializer handles the q↔search translation on output; here
        we build the dict that the rest of the view layer consumes.
        """
        result: dict = {}
        for key in instance.DIRECT_KEYS:
            result[key] = getattr(instance, key)

        # The API parameter is "q"; the column is "search".
        result["q"] = instance.search

        # Show — from the related SettingsBrowserShow row.
        show_obj = instance.show
        result["show"] = {k: getattr(show_obj, k) for k in SHOW_KEYS}

        # Filters — from the related SettingsBrowserFilters row.
        filters_obj = instance.filters  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        result["filters"] = {
            k: getattr(filters_obj, k) for k in SettingsBrowserFilters.FILTER_KEYS
        }

        # Last route — from the related SettingsBrowserLastRoute row.
        route_obj = instance.last_route  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        result["last_route"] = {
            "group": route_obj.group,
            "pks": tuple(route_obj.pks) if route_obj.pks else (0,),
            "page": route_obj.page,
        }

        return result

    @staticmethod
    def _reader_instance_to_dict(instance: SettingsReader) -> dict:
        """Convert a SettingsReader instance to the params dict."""
        return {key: getattr(instance, key) for key in instance.DIRECT_KEYS}

    def _load_settings_data(self, only: Sequence[str] | None = None) -> dict:
        """Load the settings dict from the view's own model."""
        instance = self._get_or_create_settings(
            self.MODEL,
            self.CLIENT,
            self.FILTER_ARGS,
            self.CREATE_ARGS,
            only=only,
        )
        if isinstance(instance, SettingsBrowser):
            return self.browser_instance_to_dict(instance)
        return self._reader_instance_to_dict(instance)  # pyright: ignore[reportArgumentType], # ty: ignore[invalid-argument-type]

    def _load_browser_settings_data(self, only: Sequence[str] | None = None) -> dict:
        """Load settings from the browser model (for cross-reading)."""
        instance: SettingsBrowser = self._get_or_create_settings(  # pyright: ignore[reportAssignmentType], # ty: ignore[invalid-assignment]
            self.BROWSER_MODEL,
            self.BROWSER_CLIENT,
            BROWSER_FILTER_ARGS,
            BROWSER_CREATE_ARGS,
            only=only,
        )
        return self.browser_instance_to_dict(instance)

    # Public API — read-only

    def get_from_settings(self, key: str, default=None, *, browser: bool = False):
        """Get one key from the session or its default."""
        if browser:
            stored = self._load_browser_settings_data()
            model = self.BROWSER_MODEL
        else:
            stored = self._load_settings_data()
            model = self.MODEL
        if stored:
            return stored.get(key, default)
        field = model._meta.get_field(key)
        return field.default

    def get_last_route(self) -> Mapping:
        """Get the last route from the browser session."""
        if last_route := self.get_from_settings("last_route", browser=True):
            return last_route
        return DEFAULT_BROWSER_ROUTE


class SettingsWriteView(SettingsReadView):
    """
    Full settings view with params mutation support.

    Adds the higher-level load/save params API, save_last_route,
    and browser-specific constants used by browser and reader param
    views.  Views that need to read *and write* settings should
    inherit from this class (via a concrete browser/reader subclass).
    """

    def save_last_route(self, data: MutableMapping) -> None:
        """Save last route to data."""
        last_route = {
            "group": self.kwargs.get("group", "r"),
            "pks": self.kwargs.get("pks", (0,)),
            "page": self.kwargs.get("page", 1),
        }
        data["last_route"].update(last_route)

    def _get_browser_order_defaults(self) -> dict:
        if group := self.kwargs.get("group"):
            # order_by has a dynamic group based default
            order_by = (
                "filename"
                if group == FOLDER_GROUP
                else "story_arc_number"
                if group == STORY_ARC_GROUP
                else "sort_name"
            )
            order_defaults = {"order_by": order_by}
        else:
            order_defaults = {}
        return order_defaults

    def load_params_from_settings(self, only: Sequence[str] | None = None) -> dict:
        """Get session settings with defaults."""
        try:
            return self._load_settings_data(only=only)
        except Exception:
            logger.exception("Loading settings data from model")
            raise

    @staticmethod
    def _save_browser_show(instance: SettingsBrowser, show_data: dict) -> None:
        """Get-or-create a shared SettingsBrowserShow row and assign it."""
        show_kwargs = {k: bool(show_data.get(k, False)) for k in SHOW_KEYS}
        show, _ = SettingsBrowserShow.objects.get_or_create(**show_kwargs)  # pyright: ignore[reportArgumentType]
        instance.show = show

    @staticmethod
    def _save_browser_filters(
        filters_obj: SettingsBrowserFilters,
        filters_data: dict,
    ) -> None:
        """Apply filter values from the params dict to the filters row."""
        for key, value in filters_data.items():
            if key not in SettingsBrowserFilters.FILTER_KEYS:
                continue
            cleaned = value if key == "bookmark" else (list(value) if value else [])
            setattr(filters_obj, key, cleaned)
        filters_obj.save()

    @staticmethod
    def _save_browser_last_route(
        route_obj: SettingsBrowserLastRoute,
        route_data: dict,
    ) -> None:
        """Apply last-route values from the params dict to the route row."""
        if "group" in route_data:
            route_obj.group = route_data["group"]
        if "pks" in route_data:
            pks = route_data["pks"]
            route_obj.pks = tuple(pks) if pks else (0,)
        if "page" in route_data:
            route_obj.page = route_data["page"]
        route_obj.save()

    @classmethod
    def _save_browser_settings_data(cls, instance: SettingsBrowser, data: dict) -> None:
        """Persist a params dict to a SettingsBrowser and its related rows."""
        for key in instance.DIRECT_KEYS:
            if key in data:
                setattr(instance, key, data[key])
        if "q" in data:
            instance.search = data["q"]
        if show_data := data.get("show"):
            cls._save_browser_show(instance, show_data)
        instance.save()

        if filters_data := data.get("filters"):
            cls._save_browser_filters(instance.filters, filters_data)  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        if route_data := data.get("last_route"):
            cls._save_browser_last_route(instance.last_route, route_data)  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]

    @staticmethod
    def _save_reader_settings_data(instance: SettingsReader, data: dict) -> None:
        """Persist a params dict to a SettingsReader row."""
        for key in instance.DIRECT_KEYS:
            if key in data:
                setattr(instance, key, data[key])
        instance.save()

    def _save_settings_data(self, data: dict) -> None:
        """Persist the settings dict to the view's own model."""
        instance = self._get_or_create_settings(
            self.MODEL,
            self.CLIENT,
            self.FILTER_ARGS,
            self.CREATE_ARGS,
        )
        if isinstance(instance, SettingsBrowser):
            self._save_browser_settings_data(instance, data)
        else:
            self._save_reader_settings_data(instance, data)  # pyright: ignore[reportArgumentType], # ty: ignore[invalid-argument-type]

    # Public API with save.

    def save_params_to_settings(self, params) -> None:  # reader session & browser final
        """Save the session from params with defaults for missing values."""
        try:
            # Deepcopy this so serializing the values later for http response doesn't alter them
            data = deepcopy(dict(params))
            self._save_settings_data(data)
        except Exception as exc:
            logger.warning(f"Saving params to session: {exc}")
