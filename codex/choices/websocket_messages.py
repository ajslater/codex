"""Static choices that aren't derived from models."""
from pathlib import Path

import simplejson as json


THIS_DIR = Path(__file__).parent
MESSAGES_FN = f"{THIS_DIR}/websocketMessages.json"
with open(MESSAGES_FN, "r") as messages_file:
    MESSAGES = json.load(messages_file)
