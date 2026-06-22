#!/usr/bin/env bash
#
# Launch a local nginx that reverse-proxies to a running Codex, for testing
# a `url_path_prefix` / subpath deployment (GitHub #784) without Docker.
#
# The full standalone config lives in ../test-proxy/ and is checked into git
# — generated once, reused every run:
#
#   test-proxy/nginx.conf   top-level events{} + http{} wrapper
#   test-proxy/server.conf  the server block: listen ports, proxy_pass, etc.
#                           EDIT THIS to change ports, backend, or routing.
#   test-proxy/ssl.conf     points at the self-signed cert below
#   test-proxy/cert.pem     self-signed localhost cert (throwaway, test-only)
#   test-proxy/cert.key       "
#
# Only the ephemeral nginx temp/pid dir (test-proxy/tmp/, gitignored) is
# created at run time. Pass --new-cert to regenerate the self-signed cert.
#
# Usage:
#   ./bin/run-test-proxy.sh              # run with the committed scaffold
#   ./bin/run-test-proxy.sh --new-cert   # regenerate the cert, then run
#
#   --new-cert   Regenerate the self-signed localhost cert
#   -h, --help   Show this help
#
# To exercise the subpath, run Codex with url_path_prefix="/codex", then
# browse http://localhost:8080/codex/ (nginx forwards the full path; Codex
# serves under /codex). Change ports or backend by editing
# test-proxy/server.conf.
set -euo pipefail

new_cert=0

usage() {
  sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
  --new-cert)  new_cert=1; shift ;;
  -h | --help) usage 0 ;;
  *)
    echo "Unknown argument: $1" >&2
    usage 1
    ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
scaffold="$(cd "$script_dir/.." && pwd)/test-proxy"

command -v nginx >/dev/null 2>&1 || {
  echo "nginx not found. Install it (e.g. 'brew install nginx')." >&2
  exit 1
}
[[ -f "$scaffold/nginx.conf" && -f "$scaffold/server.conf" ]] || {
  echo "Missing scaffold in $scaffold (expected nginx.conf + server.conf)." >&2
  exit 1
}

# Self-signed cert for the TLS / HTTP3 listeners. Committed and reused; only
# (re)generated when absent or when --new-cert is passed.
if [[ "$new_cert" -eq 1 || ! -f "$scaffold/cert.pem" || ! -f "$scaffold/cert.key" ]]; then
  command -v openssl >/dev/null 2>&1 || {
    echo "openssl not found. Install it (e.g. 'brew install openssl')." >&2
    exit 1
  }
  openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "$scaffold/cert.key" -out "$scaffold/cert.pem" -days 3650 \
    -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" 2>/dev/null
  echo "[proxy] generated self-signed cert in $scaffold"
fi

# Ephemeral working dirs (gitignored).
mkdir -p "$scaffold/tmp"

nginx -p "$scaffold" -c "$scaffold/nginx.conf" -t

# Best-effort: surface the ports/backend the committed config actually uses.
http_port="$(awk '/^[[:space:]]*listen [0-9]+ / && !/ssl/ && !/quic/ {print $2; exit}' "$scaffold/server.conf")"
https_port="$(awk '/^[[:space:]]*listen [0-9]+ ssl/ {print $2; exit}' "$scaffold/server.conf")"
backend="$(awk '/proxy_pass[[:space:]]+http:\/\// {gsub(/.*http:\/\/|;.*/, ""); print; exit}' "$scaffold/server.conf")"

cat <<EOF
[proxy] nginx test reverse proxy  (config: test-proxy/server.conf)
[proxy]   HTTP  : http://localhost:${http_port:-?}/
[proxy]   HTTPS : https://localhost:${https_port:-?}/   (self-signed; curl -k)
[proxy]   -> backend http://${backend:-?}
[proxy]
[proxy] Subpath test: run Codex with url_path_prefix="/codex", then open
[proxy]   http://localhost:${http_port:-8080}/codex/
[proxy] Ctrl+C to stop.
EOF

exec nginx -p "$scaffold" -c "$scaffold/nginx.conf"
