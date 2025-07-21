"""Telemeter job."""

import json
from base64 import a85decode
from lzma import compress
from uuid import uuid4

from requests import Session

from codex.choices.admin import AdminFlagChoices
from codex.librarian.telemeter.stats import CodexStats
from codex.models.admin import AdminFlag, Timestamp

# Version
_APP_NAME = "codex"
_VERSION = "1"

# Sending
# this isn't meant to fool you. it's meant to discourage lazy scraper bots.
_BASE = "".join(
    (
        a85decode(b"BQS?8F#ks-@:XCm@;\\+").decode(),
        a85decode(b"Ea`frF)to6Bk]hRFCB94/c").decode(),
        a85decode(b"@rGmhGV*rI@:Wqi/n&^<").decode(),
    )
)
_HEADERS = {"Content-Type": "application/xz"}
_POST = _BASE + f"/stats/{_APP_NAME}/{_VERSION}"
_TIMEOUT = 5


def get_telemeter_timestamp():
    """Get or create timestamp."""
    key = Timestamp.Choices.TELEMETER_SENT.value
    defaults = {"key": key}
    ts, _ = Timestamp.objects.get_or_create(defaults=defaults, key=key)
    if not ts.version:
        ts.version = str(uuid4())
        ts.save()
    return ts


def _post_stats(data):
    """Post telemetry to endpoint."""
    data_json = json.dumps(data)
    json_bytes = data_json.encode()
    compressed_data = compress(json_bytes)
    with Session() as session:
        response = session.post(
            _POST, data=compressed_data, headers=_HEADERS, timeout=_TIMEOUT
        )
        response.raise_for_status()


def _send_telemetry(uuid):
    """Send telemetry to server."""
    if (
        not AdminFlag.objects.only("on")
        .get(key=AdminFlagChoices.SEND_TELEMETRY.value)
        .on
    ):
        reason = "Send Telemetry flag is off."
        raise ValueError(reason)
    stats = CodexStats().get()
    data = {"stats": stats, "uuid": uuid}
    _post_stats(data)


def send_telemetry(log):
    """Send anonymous telemetry during one window per week."""
    try:
        ts = get_telemeter_timestamp()
        try:
            _send_telemetry(ts.version)
        except Exception as exc:
            log.debug(f"Failed to send anonyomous stats: {exc}")
        # update updated_at, even on failure to prevent rapid rescheudling.
        ts.save()
    except Exception as exc:
        log.debug(f"Failed to get or set telemeter timestamp: {exc}")
