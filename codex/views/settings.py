"""Base class for settings."""

from abc import ABC
from collections.abc import Mapping, Sequence
from copy import deepcopy
from types import MappingProxyType
from typing import cast

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from loguru import logger

from codex.choices.admin import AdminFlagChoices
from codex.choices.browser import (
    BROWSER_TOP_GROUP_CHOICES,
    admin_default_route_for,
)
from codex.models import AdminFlag
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

# Fallback top-group when the BG flag row is missing, off, or holds
# an invalid value. Mirrors ``SettingsBrowser.top_group``'s model
# default; ``admin_default_route_for("p")`` yields the historical
# ``/r/0/1`` redirect target.
_FALLBACK_DEFAULT_TOP_GROUP = "p"

CREDIT_PERSON_UI_FIELD = "credits"
STORY_ARC_UI_FIELD = "story_arcs"
IDENTIFIER_TYPE_UI_FIELD = "identifier_source"
SETTINGS_BROWSER_SELECT_RELATED = ("show", "filters", "last_route")

BROWSER_FILTER_ARGS = MappingProxyType({"name": ""})
BROWSER_CREATE_ARGS = MappingProxyType({"name": ""})
NULL_VALUES: frozenset = frozenset({"", None})
_SHOW_KEYS = ("p", "i", "s", "v")


class SettingsBaseView(AuthFilterGenericAPIView, ABC):
    """
    Core settings model access with full read/write support.

    Provides the low-level read/write interface to the settings database
    models.  Subclasses must set MODEL, CLIENT, FILTER_ARGS, and
    CREATE_ARGS.
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

    # ── Session / user helpers ──────────────────────────────────────

    def _get_request_user(self):
        """Return the authenticated user or None."""
        user = self.request.user
        if user and getattr(user, "pk", None):
            return user
        return None

    # ── Model field introspection ───────────────────────────────────

    @staticmethod
    def _get_field_default(model, field_name):
        """Get the default value for a model field, calling it if callable."""
        default = model._meta.get_field(field_name).default
        return default() if callable(default) else default

    # ── Settings row CRUD ───────────────────────────────────────────

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

        if user and instance.user_id is None:
            # Promote anonymous row to a user row (first login).
            instance.user = user
            instance.save(update_fields=("user_id", "updated_at"))
        return instance

    @staticmethod
    def _get_admin_default_top_group() -> str:
        """
        Read the admin-configured default top group.

        Returns the validated ``BROWSER_DEFAULT_GROUP`` flag value,
        falling back to ``"p"`` if the row is missing, the flag is
        off, or the value is out of range (defense against a
        hand-edited DB / pre-migration state). ``"p"`` mirrors the
        ``SettingsBrowser.top_group`` model default and resolves to
        the historical ``/r/0/1`` redirect target.
        """
        try:
            flag = AdminFlag.objects.only("on", "value").get(
                key=AdminFlagChoices.BROWSER_DEFAULT_GROUP.value
            )
        except AdminFlag.DoesNotExist:
            return _FALLBACK_DEFAULT_TOP_GROUP
        if flag.on and flag.value in BROWSER_TOP_GROUP_CHOICES:
            return flag.value
        return _FALLBACK_DEFAULT_TOP_GROUP

    @classmethod
    def _get_admin_default_route(cls) -> Mapping:
        """Translate the admin default top group into a redirect target."""
        return admin_default_route_for(cls._get_admin_default_top_group())

    @classmethod
    def _create_browser_settings(cls, user, session_key, client, create_args):
        """
        Create a SettingsBrowser with its related show/filters/last_route.

        Sets ``top_group`` from the admin-configured default unless
        the caller already supplied one. The override applies only on
        row creation; ``_get_or_create_settings`` returns existing
        rows before reaching this branch, so a returning user's
        pinned ``top_group`` is never overwritten.
        """
        show, _ = SettingsBrowserShow.objects.get_or_create(
            p=True,
            i=False,
            s=True,
            v=False,
        )
        create_kwargs = dict(create_args)
        create_kwargs.setdefault("top_group", cls._get_admin_default_top_group())
        instance = SettingsBrowser.objects.create(
            user=user,
            session_id=session_key,
            client=client,
            show=show,
            **create_kwargs,
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

    # ── Instance → dict conversion ──────────────────────────────────

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

        # Show — from the related SettingsBrowserShow row.
        show_obj = instance.show
        result["show"] = {k: getattr(show_obj, k) for k in _SHOW_KEYS}

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

    # ── Load (read) ─────────────────────────────────────────────────

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
        # Branch invariant: ``instance`` is a ``SettingsReader`` (the
        # only other concrete type in the union). ``_get_or_create_settings``'s
        # broad return type forces the cast.
        return self._reader_instance_to_dict(cast("SettingsReader", instance))

    def _load_browser_settings_data(self, only: Sequence[str] | None = None) -> dict:
        """Load settings from the browser model (for cross-reading)."""
        instance = cast(
            "SettingsBrowser",
            self._get_or_create_settings(
                self.BROWSER_MODEL,
                self.BROWSER_CLIENT,
                BROWSER_FILTER_ARGS,
                BROWSER_CREATE_ARGS,
                only=only,
            ),
        )
        return self.browser_instance_to_dict(instance)

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
        """
        Get the last route from the browser session.

        Returns the user's persisted last_route when available; falls
        through to the admin-configured default for new users /
        cleared-cookie users / anonymous-pre-navigation requests.
        """
        if last_route := self.get_from_settings("last_route", browser=True):
            return last_route
        return self._get_admin_default_route()

    @classmethod
    def get_browser_default_params(cls) -> dict:
        """Derive browser default params from model field metadata."""
        result: dict = {}
        for key in SettingsBrowser.DIRECT_KEYS:
            result[key] = cls._get_field_default(SettingsBrowser, key)

        result["show"] = {
            k: cls._get_field_default(SettingsBrowserShow, k) for k in _SHOW_KEYS
        }

        result["filters"] = {
            k: cls._get_field_default(SettingsBrowserFilters, k)
            for k in SettingsBrowserFilters.FILTER_KEYS
        }

        last_route_keys = ("group", "pks", "page")
        result["last_route"] = {
            k: cls._get_field_default(SettingsBrowserLastRoute, k)
            for k in last_route_keys
        }

        return result

    def load_params_from_settings(self, only: Sequence[str] | None = None) -> dict:
        """Get session settings with defaults."""
        try:
            return self._load_settings_data(only=only)
        except Exception:
            logger.exception("Loading settings data from model")
            raise

    # ── Save (write) ────────────────────────────────────────────────

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

    @staticmethod
    def _save_browser_show(instance: SettingsBrowser, show_data: dict) -> bool:
        """
        Get-or-create a shared SettingsBrowserShow row and assign it.

        Returns True if the instance's ``show`` FK changed.
        """
        show_kwargs = {k: bool(show_data.get(k, False)) for k in _SHOW_KEYS}
        current = instance.show
        if current and all(getattr(current, k) == show_kwargs[k] for k in _SHOW_KEYS):
            return False
        show, _ = SettingsBrowserShow.objects.get_or_create(**show_kwargs)  # pyright: ignore[reportArgumentType]
        if instance.show_id == show.pk:  # pyright: ignore[reportAttributeAccessIssue] # ty: ignore[unresolved-attribute]
            return False
        instance.show = show
        return True

    @staticmethod
    def _save_browser_filters(
        filters_obj: SettingsBrowserFilters,
        filters_data: dict,
    ) -> None:
        """Apply filter values from the params dict to the filters row."""
        dirty = False
        for key, value in filters_data.items():
            if key not in SettingsBrowserFilters.FILTER_KEYS:
                continue
            cleaned = value if key == "bookmark" else (list(value) if value else [])
            if getattr(filters_obj, key) != cleaned:
                setattr(filters_obj, key, cleaned)
                dirty = True
        if dirty:
            filters_obj.save()

    @staticmethod
    def _save_browser_last_route(
        route_obj: SettingsBrowserLastRoute,
        route_data: dict,
    ) -> None:
        """Apply last-route values from the params dict to the route row."""
        dirty = False
        if "group" in route_data and route_obj.group != route_data["group"]:
            route_obj.group = route_data["group"]
            dirty = True
        if "pks" in route_data:
            pks_value = route_data["pks"]
            new_pks = tuple(pks_value) if pks_value else (0,)
            if tuple(route_obj.pks or ()) != new_pks:
                route_obj.pks = new_pks
                dirty = True
        if "page" in route_data and route_obj.page != route_data["page"]:
            route_obj.page = route_data["page"]
            dirty = True
        if dirty:
            route_obj.save()

    @staticmethod
    def _save_browser_settings_direct_key(key: str, data, instance):
        if key in data and getattr(instance, key) != data[key]:
            setattr(instance, key, data[key])
            return True
        return False

    @classmethod
    def _save_browser_settings_data(cls, instance: SettingsBrowser, data: dict) -> None:
        """Persist a params dict to a SettingsBrowser and its related rows."""
        instance_dirty = False
        for key in instance.DIRECT_KEYS:
            instance_dirty |= cls._save_browser_settings_direct_key(key, data, instance)
        if "q" in data and instance.search != data["q"]:
            instance.search = data["q"]
            instance_dirty = True
        show_data = data.get("show")
        if show_data and cls._save_browser_show(instance, show_data):
            instance_dirty = True
        if instance_dirty:
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
            # Same branch invariant as ``_load_settings_data``.
            self._save_reader_settings_data(cast("SettingsReader", instance), data)

    def save_params_to_settings(self, params) -> None:  # reader session & browser final
        """Save the session from params with defaults for missing values."""
        try:
            # Deepcopy this so serializing the values later for http response doesn't alter them
            data = deepcopy(dict(params))
            self._save_settings_data(data)
        except Exception as exc:
            logger.warning(f"Saving params to session: {exc}")
