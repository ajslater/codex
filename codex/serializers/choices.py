"""
Static choices that aren't derived from models.

Extract the same json the frontend uses for the values so they're always
in sync.
Which is a little bit of overengineering.
"""
import json
import mmap
import re

from pathlib import Path

from codex.settings.logging import get_logger
from codex.settings.settings import BUILD, DEBUG, STATIC_ROOT


LOG = get_logger(__name__)

_PROD_JS_ROOT = STATIC_ROOT / "js"
if DEBUG:
    from codex.settings.settings import BASE_DIR, STATIC_BUILD

    _SRC_JS_ROOT = BASE_DIR / "frontend/src"
    # not sure this ever gets used. in dev src is always present.
    _DEV_JS_ROOT = STATIC_BUILD / "js"
    _JS_ROOTS = (_SRC_JS_ROOT, _DEV_JS_ROOT, _PROD_JS_ROOT)
else:
    _JS_ROOTS = (_PROD_JS_ROOT,)
    # Dummy values for type checker. Never used if not DEBUG
    _SRC_JS_ROOT = Path()
    _DEV_JS_ROOT = Path()

_CHOICES_MODULE_NAME = "choices"
_CHOICES_FN_RE = {
    _PROD_JS_ROOT: re.compile("^" + _CHOICES_MODULE_NAME + r"\.[0-9a-f]{12}\.json$"),
}
if DEBUG:
    _CHOICES_FN_RE[_SRC_JS_ROOT] = re.compile(f"^{_CHOICES_MODULE_NAME}.json$")
    _CHOICES_FN_RE[_DEV_JS_ROOT] = re.compile(f"^{_CHOICES_MODULE_NAME}.json$")

# Exports
CHOICES = {}
DEFAULTS = {}
WEBSOCKET_MESSAGES = {}
VUETIFY_NULL_CODE = -1


def _find_filename_regex(js_root):
    """Find a filename in a dir that matches the regex."""
    if not js_root.is_dir():
        LOG.warning(f"Not a directory: {js_root}")
        return
    matcher = _CHOICES_FN_RE[js_root]
    for path in js_root.iterdir():
        if matcher.match(path.name):
            return path
    raise FileNotFoundError(f"Could not find {js_root} {_CHOICES_MODULE_NAME}")


def _parse_choices():
    """Parse the choices.json."""
    data_dict = {}
    for js_root in _JS_ROOTS:
        try:
            path = _find_filename_regex(js_root)
            if path:
                with path.open("r") as choices_file, mmap.mmap(
                    choices_file.fileno(), 0, access=mmap.ACCESS_READ
                ) as choices_mmap_file:
                    json_str = choices_mmap_file.read()
                    data_dict = json.loads(json_str)
                    LOG.verbose(f"Loaded json choices from {js_root}")
                    break
        except Exception as exc:
            LOG.exception(exc)
    if not data_dict:
        LOG.error(f"Could not extract values from {_CHOICES_MODULE_NAME}")

    return data_dict


def _build_show_defaults(settings_group_list):
    """Parse the show defaults from vuetify form into a dict."""
    show = {}
    for choice in settings_group_list:
        key = choice["value"]
        show[key] = choice.get("default", False)
    return show


def _parse_choices_to_dict(vuetify_key, vuetify_list):
    """Parse the vuetify choices into dicts and extract defaults."""
    choices = {}
    for item in vuetify_list:
        key = item["value"]
        choices[key] = item["text"]
        if item.get("default"):
            DEFAULTS[vuetify_key] = key
    return choices


def _build_choices_and_defaults(data_dict):
    """Transform the vuetify choice formatted data to key:value dicts."""
    global DEFAULTS, VUETIFY_NULL_CODE, CHOICES
    for vuetify_key, vuetify_list in data_dict.items():
        if vuetify_key == "settingsGroup":
            DEFAULTS["show"] = _build_show_defaults(vuetify_list)
            continue
        if vuetify_key == "vuetifyNullCode":
            VUETIFY_NULL_CODE = vuetify_list
            continue
        if vuetify_key in ("autoquery", "route"):
            DEFAULTS[vuetify_key] = vuetify_list
            continue
        CHOICES[vuetify_key] = _parse_choices_to_dict(vuetify_key, vuetify_list)


def _load_json():
    """Load values from the vuetify formatted json into python dicts."""
    global WEBSOCKET_MESSAGES
    if DEFAULTS and VUETIFY_NULL_CODE and CHOICES and WEBSOCKET_MESSAGES:
        LOG.verbose("choices already loaded")
        return
    data_dict = _parse_choices()
    for key, value in data_dict.items():
        if key == "websockets":
            WEBSOCKET_MESSAGES = value
        else:
            if key == "browser":
                del value["groupNames"]
            _build_choices_and_defaults(value)
        LOG.debug(f"Parsed {key} choices")


if not BUILD:
    # Run if not running collectstatic
    _load_json()
