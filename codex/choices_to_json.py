#!/usr/bin/env python3
"""Dump choices to JSON."""
import json
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from caseconverter import camelcase

from codex.choices import (
    ADMIN_FLAG_CHOICES,
    ADMIN_STATUS_TITLES,
    ADMIN_TASKS,
    BROWSER_CHOICES,
    BROWSER_DEFAULTS,
    READER_CHOICES,
    READER_DEFAULTS,
    WEBSOCKET_MESSAGES,
)

_DEFAULTS = MappingProxyType(
    {"browser-choices.json": BROWSER_DEFAULTS, "reader-choices.json": READER_DEFAULTS}
)

_DUMPS = MappingProxyType(
    {
        "websocket-messages.json": WEBSOCKET_MESSAGES,
        "browser-choices.json": BROWSER_CHOICES,
        "reader-choices.json": READER_CHOICES,
        "admin-flag-choices.json": ADMIN_FLAG_CHOICES,
        "admin-status-titles.json": ADMIN_STATUS_TITLES,
        "admin-tasks.json": ADMIN_TASKS,
    }
)

_LOOKUP_DUMPS = MappingProxyType(
    {
        "browser-map.json": BROWSER_CHOICES,
        "reader-map.json": READER_CHOICES,
        "browser-defaults.json": BROWSER_DEFAULTS,
    }
)


def _to_vuetify_choices(defaults, key, obj_map):
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


def _make_json_serializable(data):
    """Convert nested Mapping objects to dicts."""
    if isinstance(data, Mapping):
        return {key: _make_json_serializable(value) for key, value in data.items()}
    if isinstance(data, list | tuple | frozenset | set):
        return [_make_json_serializable(item) for item in data]
    return data


def _to_vuetify_dict(fn, data):
    """Convert mappings to vuetify dict list."""
    vuetify_data = {}
    defaults = _DEFAULTS.get(fn) or {}
    for key, obj in data.items():
        if isinstance(obj, Mapping):
            vuetify_value = _to_vuetify_choices(defaults, key, obj)
        else:
            vuetify_value = _make_json_serializable(obj)
        vuetify_data[camelcase(key)] = vuetify_value
    return vuetify_data


def _dump(parent_path, fn, data, vuetify=True):
    """Dump data to json file."""
    vuetify_data = (
        _to_vuetify_dict(fn, data) if vuetify else _make_json_serializable(data)
    )
    path = parent_path / Path(fn)
    with path.open("w") as json_file:
        json.dump(vuetify_data, json_file, indent=2)


def main():
    """Dump all files."""
    import sys

    parent_path = sys.argv[1] if len(sys.argv) > 1 else "."
    parent_path = Path(parent_path)
    parent_path.mkdir(exist_ok=True)
    for fn, data in _DUMPS.items():
        _dump(parent_path, fn, data)

    for fn, data in _LOOKUP_DUMPS.items():
        _dump(parent_path, fn, data, False)


if __name__ == "__main__":
    main()
