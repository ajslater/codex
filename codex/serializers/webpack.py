"""
Static choices that aren't derived from models.

Extract the same json the frontend uses for the values so they're always
in sync.
Which is a little bit of overengineering.
"""
import logging
import mmap

from glob import glob

import simplejson as json

from codex.settings import BASE_DIR
from codex.settings import DEBUG
from codex.settings import STATIC_ROOT


LOG = logging.getLogger(__name__)

PROD_JS_ROOT = STATIC_ROOT / "js"
if DEBUG:
    from codex.settings import STATIC_BUILD

    SRC_JS_ROOT = BASE_DIR / "frontend/src/choices"
    # not sure this ever gets used. in dev src is always present.
    DEV_JS_ROOT = STATIC_BUILD / "js"
    JS_ROOTS = (SRC_JS_ROOT, DEV_JS_ROOT, PROD_JS_ROOT)
else:
    JS_ROOTS = (PROD_JS_ROOT,)


WEBSOCKET_MESSAGES_GLOB = "websocketMessages*.js[on]?"
WEBPACK_MODULE_GLOBS = (
    "browserChoices*.js[on]?",
    "readerChoices*.js[on]?",
    WEBSOCKET_MESSAGES_GLOB,
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


def extract_json(js_root, webpack_module_js):
    """Use different args to extract the json depending on origin."""
    args = EXTRACT_JSON_ARGS[js_root]
    header_index = webpack_module_js.find(args["head"])
    json_start_index = header_index + args["head_len"]
    json_end_index = webpack_module_js.rfind(args["tail"]) - args["tail_pad"]
    json_str = webpack_module_js[json_start_index:json_end_index]
    json_str = json_str.replace(args["remove"], b"")
    return json_str


def parse_wepack_module(webpack_module_glob):
    """Extract the JSON core from a webpack module and parse it."""
    data_dict = fn = None
    for js_root in JS_ROOTS:
        full_glob = str(js_root / webpack_module_glob)
        globs = glob(full_glob)
        try:
            if len(globs) == 0:
                raise FileNotFoundError()
            fn = globs[0]
            with open(fn, "r") as webpack_module_file, mmap.mmap(
                webpack_module_file.fileno(), 0, access=mmap.ACCESS_READ
            ) as webpack_module_js:
                json_str = extract_json(js_root, webpack_module_js)
                data_dict = json.loads(json_str)
                break
        except FileNotFoundError as exc:
            LOG.debug(f"Could not find {full_glob}: {exc}")
        except Exception as exc:
            LOG.exception(exc)
    if not data_dict:
        LOG.error(f"Could not extract values from {webpack_module_glob}")

    return data_dict, fn


def build_show_defaults(settings_group_list):
    """Parse the show defaults."""
    show = {}
    for choice in settings_group_list:
        key = choice["value"]
        show[key] = choice.get("default", False)
    return show


def build_choices_and_defaults(data_dict):
    """Transform the vuetify choice formatted data to key:value dicts."""
    for vuetify_key, vuetify_list in data_dict.items():
        if vuetify_key == "settingsGroup":
            DEFAULTS["show"] = build_show_defaults(vuetify_list)
            continue
        choices = {}
        for item in vuetify_list:
            key = item["value"]
            choices[key] = item["text"]
            if item.get("default"):
                DEFAULTS[vuetify_key] = item["value"]
        CHOICES[vuetify_key] = choices


def load_from_webpack_modules():
    """Load values from the vuetify formatted json into python dicts."""
    global CHOICES, DEFAULTS, WEBSOCKET_MESSAGES
    for webpack_module_glob in WEBPACK_MODULE_GLOBS:
        data_dict, fn = parse_wepack_module(webpack_module_glob)
        if not data_dict:
            return

        if webpack_module_glob == WEBSOCKET_MESSAGES_GLOB:
            WEBSOCKET_MESSAGES = data_dict
        else:
            build_choices_and_defaults(data_dict)
        LOG.debug(f"Parsed {fn}")


load_from_webpack_modules()
