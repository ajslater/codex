#!/usr/bin/env python3
"""Dump choices to JSON."""

import json
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from caseconverter import camelcase

from codex.choices.admin import (
    ADMIN_FLAG_CHOICES,
    ADMIN_STATUS_TITLES,
    ADMIN_TASK_GROUPS,
)
from codex.choices.browser import BROWSER_CHOICES, BROWSER_DEFAULTS
from codex.choices.notifications import Notifications
from codex.choices.reader import READER_CHOICES, READER_DEFAULTS
from codex.serializers.route import RouteSerializer

_DEFAULTS = MappingProxyType(
    {"browser-choices.json": BROWSER_DEFAULTS, "reader-choices.json": READER_DEFAULTS}
)

_DUMPS = MappingProxyType(
    {
        "admin-flag-choices.json": ADMIN_FLAG_CHOICES,
        "admin-status-titles.json": ADMIN_STATUS_TITLES,
        "browser-choices.json": BROWSER_CHOICES,
        "reader-choices.json": READER_CHOICES,
    }
)

_MAP_DUMPS = MappingProxyType(
    {
        "admin-tasks.json": ADMIN_TASK_GROUPS,
        "browser-defaults.json": BROWSER_DEFAULTS,
        "browser-map.json": BROWSER_CHOICES,
        "reader-map.json": READER_CHOICES,
    }
)


def _to_vuetify_choices(defaults, key: str, obj_map):
    """Transform a dict into a list of vuetify choices."""
    default = defaults.get(key)
    vuetify_list = []
    for value, title in obj_map.items():
        vuetify_dict = {
            "value": value,
            "title": title,
        }
        if default == value:
            vuetify_dict["default"] = True
        vuetify_list.append(vuetify_dict)
    return vuetify_list


def _json_key(key: str):
    """Transform key to json version."""
    return key if key.upper() == key else camelcase(key)


def _make_json_serializable(data):
    """Convert nested Mapping objects to dicts."""
    if isinstance(data, Mapping):
        json_dict = {}
        for key, value in data.items():
            if key == "breadcrumbs":
                json_value = tuple(RouteSerializer(dict(route)).data for route in value)
            else:
                json_value = _make_json_serializable(value)
            json_dict[_json_key(key)] = json_value
        return json_dict
    if isinstance(data, list | tuple | frozenset | set):
        return [_make_json_serializable(item) for item in data]
    return data


def _to_vuetify_dict(fn: str, data):
    """Convert mappings to vuetify dict list."""
    vuetify_data = {}
    defaults = _DEFAULTS.get(fn) or {}
    for key, obj in data.items():
        if isinstance(obj, Mapping):
            vuetify_value = _to_vuetify_choices(defaults, key, obj)
        else:
            vuetify_value = _make_json_serializable(obj)
        vuetify_data[_json_key(key)] = vuetify_value
    return vuetify_data


def _dump(parent_path: Path, fn: str, data, vuetify: bool):
    """Dump data to json file."""
    vuetify_data = (
        _to_vuetify_dict(fn, data) if vuetify else _make_json_serializable(data)
    )
    path = parent_path / fn
    with path.open("w") as json_file:
        json.dump(vuetify_data, json_file, indent=2)
        json_file.write("\n")


def _make_websocket_messages():
    return MappingProxyType(
        {"messages": {msg.name: msg.value for msg in Notifications}}
    )


def main():
    """Dump all files."""
    import sys  # noqa: PLC0415

    parent_path = sys.argv[1] if len(sys.argv) > 1 else "."
    parent_path = Path(parent_path)
    parent_path.mkdir(exist_ok=True)
    for fn, data in _DUMPS.items():
        _dump(parent_path, fn, data, vuetify=True)

    for fn, data in _MAP_DUMPS.items():
        _dump(parent_path, fn, data, vuetify=False)

    ws_messages = _make_websocket_messages()
    _dump(parent_path, "websocket-messages.json", ws_messages, vuetify=False)


if __name__ == "__main__":
    main()
