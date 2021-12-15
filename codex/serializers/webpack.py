"""
Static choices that aren't derived from models.

Extract the same json the frontend uses for the values so they're always
in sync.
Which is a little bit of overengineering.
"""
import json
import mmap
import re

from logging import getLogger
from pathlib import Path

from codex.settings.settings import BASE_DIR, DEBUG, STATIC_ROOT


LOG = getLogger(__name__)

PROD_JS_ROOT = STATIC_ROOT / "js"
if DEBUG:
    from codex.settings.settings import STATIC_BUILD

    SRC_JS_ROOT = BASE_DIR / "frontend/src/choices"
    # not sure this ever gets used. in dev src is always present.
    DEV_JS_ROOT = STATIC_BUILD / "js"
    JS_ROOTS = (SRC_JS_ROOT, DEV_JS_ROOT, PROD_JS_ROOT)
else:
    JS_ROOTS = (PROD_JS_ROOT,)
    # Dummy values for type checker. Never used if not DEBUG
    SRC_JS_ROOT = Path()
    DEV_JS_ROOT = Path()

WEBPACK_MODULE_RE_TEMPLATES = {
    PROD_JS_ROOT: r"^{name}\." + 12 * "." + r"\.js$",
}
if DEBUG:
    WEBPACK_MODULE_RE_TEMPLATES[SRC_JS_ROOT] = "^{name}.json$"
    WEBPACK_MODULE_RE_TEMPLATES[DEV_JS_ROOT] = "^{name}.js$"


BROWSER_CHOICES_MODULE_NAME = "browserChoices"
WEBSOCKETS_MODULE_NAME = "websocketMessages"
WEBPACK_MODULE_NAMES = (
    BROWSER_CHOICES_MODULE_NAME,
    "readerChoices",
    WEBSOCKETS_MODULE_NAME,
)

# These magic pad number are to get around some escaped chars in the
# dev build version of webpack modules.
EXTRACT_JSON_ARGS = {
    PROD_JS_ROOT: {
        "head": b"JSON.parse('",
        "head_pad": 0,
        "tail": b"')}});",
        "tail_pad": 0,
        "remove": b"",
    },
}
if DEBUG:
    EXTRACT_JSON_ARGS[DEV_JS_ROOT] = {
        "head": b"JSON.parse(",
        "head_pad": 2,
        "tail": b'");\\n\\n//# sourceURL',
        "tail_pad": 1,
        "remove": b"\\\\\\",
    }
    EXTRACT_JSON_ARGS[SRC_JS_ROOT] = {
        "head": b"",
        "head_pad": 0,
        "tail": b"",
        "tail_pad": 0,
        "remove": b"",
    }


for args in EXTRACT_JSON_ARGS.values():
    args["head_len"] = len(args["head"]) + args["head_pad"]
    args["tail_len"] = len(args["tail"])

# Exports
CHOICES = {}
DEFAULTS = {}
WEBSOCKET_MESSAGES = {}
VUETIFY_NULL_CODE = -1


def _find_filename_regex(js_root, module_name):
    """Find a filename in a dir that matches the regex."""
    if not js_root.is_dir():
        LOG.warning(f"Not a directory: {js_root}")
        return
    re_template = WEBPACK_MODULE_RE_TEMPLATES[js_root]
    regex_str = re_template.format(name=module_name)
    regex = re.compile(regex_str)
    path = None
    for path in js_root.iterdir():
        if regex.match(path.name):
            return path
    raise FileNotFoundError(f"Could not find {js_root} {module_name}")


def _extract_json(js_root, webpack_module_js):
    """Use different args to extract the json depending on origin."""
    args = EXTRACT_JSON_ARGS[js_root]
    header_index = webpack_module_js.find(args["head"])
    json_start_index = header_index + args["head_len"]
    json_end_index = webpack_module_js.rfind(args["tail"]) - args["tail_pad"]
    json_str = webpack_module_js[json_start_index:json_end_index]
    json_str = json_str.replace(args["remove"], b"")
    return json_str


def _parse_wepack_module(module_name):
    """Extract the JSON core from a webpack module and parse it."""
    data_dict = None
    for js_root in JS_ROOTS:
        try:
            path = _find_filename_regex(js_root, module_name)
            if path:
                with path.open("r") as webpack_module_file, mmap.mmap(
                    webpack_module_file.fileno(), 0, access=mmap.ACCESS_READ
                ) as webpack_module_js:
                    json_str = _extract_json(js_root, webpack_module_js)
                    data_dict = json.loads(json_str)
                    break
        except Exception as exc:
            LOG.exception(exc)
    if not data_dict:
        LOG.error(f"Could not extract values from {module_name}")

    return data_dict


def _build_show_defaults(settings_group_list):
    """Parse the show defaults."""
    show = {}
    for choice in settings_group_list:
        key = choice["value"]
        show[key] = choice.get("default", False)
    return show


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
        choices = {}
        for item in vuetify_list:
            key = item["value"]
            choices[key] = item["text"]
            if item.get("default"):
                DEFAULTS[vuetify_key] = item["value"]
        CHOICES[vuetify_key] = choices


def _load_from_webpack_modules():
    """Load values from the vuetify formatted json into python dicts."""
    global WEBPACK_MODULE_NAMES, WEBSOCKETS_MODULE_NAME, WEBSOCKET_MESSAGES
    for module_name in WEBPACK_MODULE_NAMES:
        data_dict = _parse_wepack_module(module_name)
        if not data_dict:
            return
        if module_name == WEBSOCKETS_MODULE_NAME:
            WEBSOCKET_MESSAGES = data_dict
        else:
            if module_name == BROWSER_CHOICES_MODULE_NAME:
                del data_dict["groupNames"]
            _build_choices_and_defaults(data_dict)
        LOG.debug(f"Parsed {module_name}")


_load_from_webpack_modules()
