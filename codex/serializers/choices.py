"""Static choices that aren't derived from models.

Extract the same json the frontend uses for the values so they're always
in sync.
Which is a little bit of overengineering.
"""

import json
import mmap
import re
from pathlib import Path

from codex.logger.logging import get_logger
from codex.serializers.route import RouteSerializer
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


def create_choices_fn_regexes(module_name):
    """Build regex paths for a json module."""
    regexes = {
        _PROD_JS_ROOT: re.compile("^" + module_name + r"\.[0-9a-f]{12}\.json$"),
    }
    if DEBUG:
        regexes[_SRC_JS_ROOT] = re.compile(f"^{module_name}.json$")
        regexes[_DEV_JS_ROOT] = re.compile(f"^{module_name}.json$")
    return regexes


_CHOICES_MODULE_NAME = "choices"
_ADMIN_CHOICES_MODULE_NAME = "choices-admin"

_CHOICES_FN_RE = {
    _CHOICES_MODULE_NAME: create_choices_fn_regexes(_CHOICES_MODULE_NAME),
    _ADMIN_CHOICES_MODULE_NAME: create_choices_fn_regexes(_ADMIN_CHOICES_MODULE_NAME),
}
_SINGLE_VALUE_KEYS = frozenset(
    {
        "customCovers",
        "dynamicCovers",
        "finishOnLastPage",
        "orderReverse",
        "q",
        "readRtlInReverse",
        "searchResultsLimit",
        "twentyFourHourTime",
        "twoPages",
    }
)

# Exports
CHOICES = {}
DEFAULTS = {}
WEBSOCKET_MESSAGES = {}
VUETIFY_NULL_CODE = -1
DUMMY_NULL_NAME = "_none_"


def _find_filename_regex(js_root, module_name):
    """Find a filename in a dir that matches the regex."""
    if not js_root.is_dir():
        LOG.warning(f"Not a directory: {js_root}")
        return None
    matcher = _CHOICES_FN_RE[module_name][js_root]
    for path in js_root.iterdir():
        if matcher.match(path.name):
            return path
    reason = f"Could not find {js_root} {module_name}"
    raise FileNotFoundError(reason)


def _parse_choices(module_name):
    """Parse the choices.json."""
    data_dict = {}
    for js_root in _JS_ROOTS:
        try:
            path = _find_filename_regex(js_root, module_name)
            if not path:
                LOG.warning(f"Could not find json choices at {path}")
                continue
            with (
                path.open("r") as choices_file,
                mmap.mmap(
                    choices_file.fileno(), 0, access=mmap.ACCESS_READ
                ) as choices_mmap_file,
            ):
                json_str = choices_mmap_file.read()
                data_dict = json.loads(json_str)
                LOG.debug(f"Loaded json choices from {js_root} {module_name}")
                break
        except Exception:
            LOG.exception(f"Reading {js_root}")
    if not data_dict:
        LOG.error(f"Could not extract values from {module_name}")

    return data_dict


def _build_show_defaults(settings_group_list):
    """Parse the show defaults from vuetify form into a dict."""
    show = {}
    for choice in settings_group_list:
        key = choice["value"]
        show[key] = choice.get("default", False)
    # Returning a mapping proxy makes deepcopy into dict harder
    return show


def _parse_choices_to_dict(vuetify_key, vuetify_list):
    """Parse the vuetify choices into dicts and extract defaults."""
    choices = {}
    for item in vuetify_list:
        key = item["value"]
        choices[key] = item["title"]
        if item.get("default"):
            DEFAULTS[vuetify_key] = key
    return choices


def _build_choices_and_defaults(data_dict):
    """Transform the vuetify choice formatted data to key:value dicts."""
    global VUETIFY_NULL_CODE  # noqa PLW0603
    for vuetify_key, value in data_dict.items():
        match vuetify_key:
            case x if x in ("identifierTypes", "groupNames"):
                continue
            case x if x in _SINGLE_VALUE_KEYS:
                DEFAULTS[vuetify_key] = value
                continue
            case "settingsGroup":
                DEFAULTS["show"] = _build_show_defaults(value)
                continue
            case "vuetifyNullCode":
                VUETIFY_NULL_CODE = value
                continue
            case "breadcrumbs":
                deserialized = []
                for crumb in value:
                    serializer = RouteSerializer(data=crumb)
                    serializer.is_valid()
                    deserialized.append(serializer.validated_data)
                DEFAULTS[vuetify_key] = tuple(deserialized)
                continue

        CHOICES[vuetify_key] = _parse_choices_to_dict(vuetify_key, value)


def _load_choices_json():
    """Load values from the vuetify formatted json into python dicts."""
    global WEBSOCKET_MESSAGES  # noqa PLW0603
    if DEFAULTS and VUETIFY_NULL_CODE and CHOICES and WEBSOCKET_MESSAGES:
        LOG.warning("choices already loaded")
        return
    data_dict = _parse_choices(_CHOICES_MODULE_NAME)
    for key, value in data_dict.items():
        if key == "websockets":
            WEBSOCKET_MESSAGES = value
        else:
            _build_choices_and_defaults(value)
        LOG.debug(f"Parsed {key} choices")


def _load_admin_choices_json():
    """Load admin json into python dicts."""
    CHOICES["admin"] = _parse_choices(_ADMIN_CHOICES_MODULE_NAME)
    admin_tasks = set()
    for group in CHOICES["admin"]["tasks"]:
        for item in group["tasks"]:
            admin_tasks.add(item["value"])
    CHOICES["admin"]["tasks"] = frozenset(admin_tasks)


def main():
    """Load both json files."""
    _load_choices_json()
    _load_admin_choices_json()


if not BUILD:
    # Run if not running collectstatic
    main()
