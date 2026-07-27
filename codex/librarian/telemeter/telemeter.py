"""Telemeter job."""

import json
from base64 import a85decode, b64encode
from lzma import compress
from os import environ
from typing import Final
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from codex.choices.admin import AdminFlagChoices
from codex.librarian.telemeter.stats import CodexStats
from codex.models.admin import AdminFlag, Timestamp

# Version
_APP_NAME: Final = "codex"
_VERSION: Final = "2"

# Sending
# this isn't meant to fool you. it's meant to discourage lazy scraper bots.
_BASE: Final = environ.get("CODEX_TELEMETER_URL") or "".join(
    (
        a85decode(b"BQS?8F#ks-@:XCm@;\\+").decode(),
        a85decode(b"Ea`frF)to6Bk]hRFCB94/c").decode(),
        a85decode(b"@rGmhGV*rI@:Wqi/n&^<").decode(),
    )
)


def _split_credentials(url: str) -> tuple[str, str]:
    """
    Separate basic-auth credentials from the url.

    ``requests`` used to pull userinfo out of the url and turn it into an
    Authorization header. ``urllib`` does not: it hands the whole netloc to
    ``http.client``, which reads everything after the colon as a port and
    raises ``InvalidURL``. So do the split ourselves.
    """
    parts = urlsplit(url)
    if not parts.username:
        return url, ""
    netloc = parts.hostname or ""
    if parts.port:
        netloc += f":{parts.port}"
    bare_url = urlunsplit(
        (parts.scheme, netloc, parts.path, parts.query, parts.fragment)
    )
    userinfo = f"{parts.username}:{parts.password or ''}".encode()
    return bare_url, "Basic " + b64encode(userinfo).decode()


_BARE_BASE, _AUTHORIZATION = _split_credentials(_BASE)
_POST: Final = _BARE_BASE + f"/stats/{_APP_NAME}/{_VERSION}"
_TIMEOUT: Final = 5


def _new_headers() -> dict[str, str]:
    """
    Build request headers.

    urllib's ``Request`` mutates ``headers`` (it lowercases keys), so this
    can't be a ``MappingProxyType`` — it has to be a real ``MutableMapping``.
    Construct fresh per-call to keep the per-call state isolated.
    """
    headers = {"Content-Type": "application/xz"}
    if _AUTHORIZATION:
        headers["Authorization"] = _AUTHORIZATION
    return headers


def get_telemeter_timestamp():
    """Get or create timestamp."""
    key = Timestamp.Choices.TELEMETER_SENT.value
    defaults = {"key": key}
    ts, _ = Timestamp.objects.get_or_create(defaults=defaults, key=key)
    if not ts.value:
        ts.value = str(uuid4())
        ts.save()
    return ts


def _post_stats(data) -> None:
    """Post telemetry to endpoint."""
    data_json = json.dumps(data)
    json_bytes = data_json.encode()
    compressed_data = compress(json_bytes)
    request = Request(  # noqa: S310
        _POST, data=compressed_data, headers=_new_headers(), method="POST"
    )
    # urlopen raises HTTPError on any status outside 2xx, and follows 3xx, so
    # returning from here is a success. Checking response.status ourselves
    # would be dead code; http.client's response has no raise_for_status(),
    # that was requests'. The server answers 202: queued, not yet stored.
    with urlopen(request, timeout=_TIMEOUT):  # noqa: S310
        pass


def _send_telemetry(uuid) -> None:
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


def send_telemetry(log) -> None:
    """Send anonymous telemetry during one window per week."""
    try:
        ts = get_telemeter_timestamp()
        try:
            _send_telemetry(ts.value)
        except Exception as exc:
            # This was briefly a warning, because a transport bug went
            # unnoticed for months while the stats server answered 200 to
            # everything. The server reports honest statuses now, so its
            # operator sees failures in the access log and this install has
            # no reason to say anything: debug is invisible at the default
            # log level, and a stats server is never the user's problem.
            # repr, not str: str(TimeoutError()) is empty, and an HTTPError's
            # repr names the status code. Neither can carry a response body.
            log.debug(f"Failed to send anonymous stats: {exc!r}")
        # Record the attempt whether or not it succeeded: retrying a
        # failed send would turn a stats outage into a stampede. The cron
        # thread already claimed this week's slot before queueing the
        # task (``mark_telemeter_attempt``) — it cannot wait for this
        # write, which happens on a thread it never joins — so this is a
        # backstop for any other caller, and it leaves the recorded time
        # honest about when the send actually finished.
        ts.save()
    except Exception as exc:
        log.debug(f"Failed to get or set telemeter timestamp: {exc}")
