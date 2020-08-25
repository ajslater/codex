"""Static choices that aren't derived from models."""
from pathlib import Path

import simplejson as json


VUEX_MODULES = Path(__file__).parent
CHOICES_FNS = (
    f"{VUEX_MODULES}/browserChoices.json",
    f"{VUEX_MODULES}/readerChoices.json",
)
CHOICES = {}
DEFAULTS = {}


def load_vue_choices():
    """Load values from the vuetify formatted json into python dicts."""
    for fn in CHOICES_FNS:
        with open(fn, "r") as choices_file:
            vue_choices = json.load(choices_file)

        # settingsGroupChoices is special
        if "settingsGroup" in vue_choices:
            DEFAULTS["show"] = dict(
                [
                    (choice["value"], choice.get("default", False))
                    for choice in vue_choices["settingsGroup"]
                ]
            )
            del vue_choices["settingsGroup"]

        # do the rest
        for vue_key, vue_list in vue_choices.items():
            CHOICES[vue_key] = {}
            for item in vue_list:
                CHOICES[vue_key][item["value"]] = item["text"]
                if item.get("default"):
                    DEFAULTS[vue_key] = item["value"]


load_vue_choices()
