"""Telemeter job."""

import json
from base64 import a85decode, b64encode
from http import HTTPStatus
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
    # urlopen raises HTTPError on 4xx & 5xx, so reaching here is a success.
    # http.client's response has no raise_for_status(); that was requests'.
    with urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310
        if response.status >= HTTPStatus.BAD_REQUEST:
            reason = f"Stats server returned {response.status}"
            raise ValueError(reason)


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
            # Not debug: a transport bug here went unnoticed for months
            # because every failure was invisible at the default log level.
            log.warning(f"Failed to send anonymous stats: {exc}")
        # update updated_at, even on failure to prevent rapid rescheudling.
        ts.save()
    except Exception as exc:
        log.debug(f"Failed to get or set telemeter timestamp: {exc}")
