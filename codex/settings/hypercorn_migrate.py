"""Migrate hypercorn.toml to codex.toml."""

import sys
from pathlib import Path

from loguru import logger

if sys.version_info >= (3, 11):
    import tomllib  # pyright: ignore[reportUnreachable]
else:
    try:
        import tomllib  # ty: ignore[unresolved-import]
    except ModuleNotFoundError:
        import tomli as tomllib

HYPERCORN_FN = "hypercorn.toml"
DEFAULT_CONFIG_HEAD_COUNT = 5
DEFAULT_CONFIG_TAIL_START = 18

# Default bind used to detect the common case.
_DEFAULT_HOST = "0.0.0.0"  # noqa: S104
_DEFAULT_PORT = 9810


def _parse_bind(bind_list: list[str]) -> tuple[str, int]:
    """
    Extract (host, port) from a hypercorn bind list.

    Entries look like "0.0.0.0:9810" or "unix:/path".
    Takes the first TCP entry found.
    """
    for raw_entry in bind_list:
        entry = raw_entry.strip()
        if entry.startswith(("unix:", "/")):
            continue
        if ":" in entry:
            host, _, port_str = entry.rpartition(":")
            host = host.strip("[]")  # IPv6 bracket notation
            return host, int(port_str)
    return _DEFAULT_HOST, _DEFAULT_PORT


def _toml_value(val: object) -> str:
    """Format a Python value as a TOML literal."""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        return f"{val}"
    if isinstance(val, str):
        return f'"{val}"'
    if isinstance(val, list):
        inner = ", ".join(_toml_value(v) for v in val)
        return f"[{inner}]"
    return f'"{val}"'


def _build_codex_toml(old: dict, default_toml: Path) -> str:
    """Convert a parsed hypercorn config dict into codex.toml text."""
    host = _DEFAULT_HOST
    port = _DEFAULT_PORT
    if "bind" in old:
        raw = old["bind"]
        host, port = _parse_bind(raw if isinstance(raw, list) else [str(raw)])

    root_path = str(old.get("root_path", ""))

    with default_toml.open() as f:
        default_lines = f.readlines()
        config_head = [
            line.strip() for line in default_lines[:DEFAULT_CONFIG_HEAD_COUNT]
        ]
        config_tail = [
            line.strip() for line in default_lines[DEFAULT_CONFIG_TAIL_START:]
        ]

    # Head of default config file
    lines: list[str] = config_head
    server_line = (
        "# "
        if (not host or host == _DEFAULT_HOST) and (not port or port == _DEFAULT_PORT)
        else ""
    )
    server_line += "[server]"
    host_line = "# " if not host or host == _DEFAULT_HOST else ""
    host_line += f"host = {host}"
    port_line = "# " if not port or port == _DEFAULT_PORT else ""
    port_line += f"port = {port}"
    lines += [server_line, "# Granian ASGI server settings", host_line, port_line]

    # Just in case someone got clever
    if (workers := old.get("workers")) and workers > 1:
        workers_line = f"workers = {int(workers)}"
    else:
        workers_line = "# workers = 1"

    lines += [
        "# Number of worker processes. 1 is recommended for containerized environments.",
        workers_line,
        '# HTTP version: "auto", "1", or "2"',
        '# http = "auto"',
        "# Enable websockets (required for Codex live updates)",
        "# websockets = true",
    ]
    url_path_prefix_line = ""
    if not root_path:
        url_path_prefix_line = "# "
    url_path_prefix_line += f'url_path_prefix = "{root_path}"'
    lines += [url_path_prefix_line]

    # Tail of the default config files
    lines += config_tail

    # Just in case someone got way too clever.
    if "certfile" in old or "keyfile" in old:
        lines += [
            "",
            "# TLS was configured in hypercorn.toml.",
            "# Granian uses environment variables instead:",
        ]
        if "certfile" in old:
            lines.append(f'#   GRANIAN_SSL_CERTIFICATE="{old["certfile"]}"')
        if "keyfile" in old:
            lines.append(f'#   GRANIAN_SSL_KEYFILE="{old["keyfile"]}"')

    lines.append("")
    return "\n".join(lines)


def migrate_hypercorn_config(
    config_dir: Path, codex_toml: Path, default_toml: Path
) -> None:
    """Convert hypercorn.toml to codex.toml."""
    if codex_toml.exists():
        return

    hypercorn_toml = config_dir / HYPERCORN_FN
    if not hypercorn_toml.exists():
        return

    with hypercorn_toml.open("rb") as fh:
        old = tomllib.load(fh)
    if not old:
        return

    codex_toml.write_text(_build_codex_toml(old, default_toml), encoding="utf-8")
    backup = hypercorn_toml.with_suffix(".toml.bak")
    hypercorn_toml.rename(backup)
    logger.info(f"Migrated {hypercorn_toml} to {codex_toml} (backup: {backup})")
