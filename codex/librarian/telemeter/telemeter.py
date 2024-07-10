"""Telemeter job."""

import json
from base64 import a85decode
from datetime import datetime, timedelta, timezone
from logging import DEBUG, getLogger
from lzma import compress
from uuid import UUID, uuid4

from requests import post

from codex.librarian.telemeter.stats import CodexStats
from codex.models.admin import Timestamp

# Version
_APP_NAME = "codex"
_VERSION = "0"

# Timing
_ONE_DAY = 60 * 60
_SECS_PER_WEEK = 7 * _ONE_DAY
_MAX_UUID = 2**128
_UUID_DIVISOR = _MAX_UUID / _SECS_PER_WEEK

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

LOG = getLogger(__name__)


def _get_timestamp():
    # Get or create timestamp
    key = Timestamp.TimestampChoices.TELEMETER_SENT.value
    defaults = {"key": key}
    ts, _ = Timestamp.objects.get_or_create(defaults=defaults, key=key)
    if not ts.version:
        ts.version = str(uuid4())
        ts.save()
    return ts


def _get_start_of_week(now):
    """Get timestamp for this Monady 00:00:00."""
    # Monday, now o'clock.
    start_of_week = now - timedelta(days=now.weekday())
    # Monday, midnight.
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_of_week.timestamp()


def _is_send_window(uuid_str):
    """Are we in the send window."""
    # Get the send time.
    now = datetime.now(tz=timezone.utc)
    start_of_week = _get_start_of_week(now)
    # time of week based on uuid
    uuid = UUID(uuid_str)
    time_of_week = uuid.int / _UUID_DIVISOR
    send_time = start_of_week + time_of_week

    # is now within a day of the send time.
    delta = now - send_time
    return delta > 0 and delta <= _ONE_DAY


def _post_stats(stats):
    """Post telemetry to endpoint."""
    stats_json = json.dumps(stats)
    json_bytes = stats_json.encode()
    compressed_data = compress(json_bytes)
    if DEBUG:
        LOG.debug(f"{_POST} {len(compressed_data)}, {_HEADERS}, {_TIMEOUT}")
    else:
        response = post(_POST, data=compressed_data, headers=_HEADERS, timeout=_TIMEOUT)
        response.raise_for_status()


def _send_telemetry(uuid_str):
    """Send telemetry to server."""
    stats = CodexStats().get()
    stats["uuid"] = uuid_str
    _post_stats(stats)
    LOG.debug("Sent anonymous telemetry")


def send_telemetry_in_window():
    """Send anonymous telemetry during one window per week."""
    try:
        ts = _get_timestamp()

        if _is_send_window(ts.version):
            # If within an hour of send time, send.
            _send_telemetry(ts.version)
            ts.save()
    except Exception as exc:
        LOG.debug(f"Failed to send anonyomous telemetry: {exc}")
