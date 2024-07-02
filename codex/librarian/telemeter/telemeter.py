"""Telemeter job."""

import json
from base64 import a85decode
from logging import getLogger
from lzma import compress

from codex.librarian.telemeter.stats import CodexStats

# this isn't meant to fool you. it's meant to discourage lazy bots.
_BASE = "".join(
    (
        a85decode(b"BQS?8F#ks-@:XCm@;\\+").decode(),
        a85decode(b"Ea`frF)to6Bk]hRFCB94/c").decode(),
        a85decode(b"@rGmhGV*rI@:Wqi/n&^<").decode(),
    )
)

_APP_NAME = "codex"
_VERSION = "0"

_HEADERS = {"Content-Type": "application/xz"}
_POST = _BASE + f"/stats/{_APP_NAME}/{_VERSION}"
_TIMEOUT = 5

LOG = getLogger(__name__)


def _post_stats(stats):
    """Post telemetry to endpoint."""
    stats_json = json.dumps(stats)
    json_bytes = stats_json.encode()
    compressed_data = compress(json_bytes)
    LOG.warning(f"{_POST} {len(compressed_data)}, {_HEADERS}, {_TIMEOUT}")
    # response = post(_POST, data=compressed_data, headers=_HEADERS, timeout=_TIMEOUT)
    # response.raise_for_status()


def send_telemetry():
    """Send telemetry to server."""
    try:
        stats = CodexStats().get()
        _post_stats(stats)
        LOG.debug("Sent anonymous telemetry")
    except Exception as exc:
        LOG.debug(f"Failed to send anonyomous telemetry: {exc}")
