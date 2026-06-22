#!/usr/bin/env bash
#
# Launch a local nginx that uses this directory's default.conf as its
# default server, so you can test Codex behind a reverse proxy — in
# particular a `url_path_prefix` / subpath deployment (GitHub #784).
#
# default.conf is a linuxserver.io-style *server block* only: it expects to
# be wrapped in a full nginx config, pulls SSL from the container path
# /config/nginx/ssl.conf, and binds 80/443. The standalone scaffold that
# supplies those missing pieces lives in ./test-proxy/ and is CHECKED INTO
# GIT — generated once, reused every run:
#
#   test-proxy/nginx.conf   top-level events{} + http{} wrapper
#   test-proxy/server.conf  default.conf adapted for standalone use
#                           (80/443 -> high ports, ssl include rewritten)
#   test-proxy/ssl.conf     points at the self-signed cert below
#   test-proxy/cert.pem     self-signed localhost cert (throwaway, test-only)
#   test-proxy/cert.key       "
#
# Only the ephemeral nginx temp/pid dir (test-proxy/tmp/, gitignored) is
# created at run time. Pass --regenerate to rebuild the scaffold from the
# current default.conf (do this after editing default.conf, then commit).
#
# Usage:
#   ./run-test-proxy.sh                       # run with the committed scaffold
#   ./run-test-proxy.sh --regenerate          # rebuild scaffold, then exit
#   ./run-test-proxy.sh --regenerate -b 1.2.3.4:9810 -H 9000 -S 9443
#
#   -H, --http-port    Plain HTTP listen port      (default 8080)
#   -S, --https-port   HTTPS + HTTP/3 listen port  (default 8443)
#   -b, --backend      Codex backend to proxy to   (default 127.0.0.1:9810)
#       --regenerate   Rebuild the test-proxy/ scaffold from default.conf
#   -h, --help         Show this help
#
# To exercise the subpath, run Codex with url_path_prefix="/codex", then
# browse http://localhost:8080/codex/ (nginx forwards the full path; Codex
# serves under /codex).
set -euo pipefail

HTTP_PORT=8080
HTTPS_PORT=8443
BACKEND="127.0.0.1:9810"
regenerate=0

usage() {
  sed -n '2,39p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
  -H | --http-port)  HTTP_PORT="$2"; regenerate=1; shift 2 ;;
  -S | --https-port) HTTPS_PORT="$2"; regenerate=1; shift 2 ;;
  -b | --backend)    BACKEND="$2"; regenerate=1; shift 2 ;;
  --regenerate)      regenerate=1; shift ;;
  -h | --help)       usage 0 ;;
  *)
    echo "Unknown argument: $1" >&2
    usage 1
    ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
default_conf="$script_dir/default.conf"
scaffold="$script_dir/test-proxy"

command -v nginx >/dev/null 2>&1 || {
  echo "nginx not found. Install it (e.g. 'brew install nginx')." >&2
  exit 1
}

generate_scaffold() {
  command -v openssl >/dev/null 2>&1 || {
    echo "openssl not found. Install it (e.g. 'brew install openssl')." >&2
    exit 1
  }
  [[ -f "$default_conf" ]] || {
    echo "Missing $default_conf" >&2
    exit 1
  }
  mkdir -p "$scaffold"

  # Self-signed cert for the TLS / HTTP3 listeners. Kept across runs (and
  # committed) — only generated when absent so --regenerate doesn't churn it.
  if [[ ! -f "$scaffold/cert.pem" || ! -f "$scaffold/cert.key" ]]; then
    openssl req -x509 -newkey rsa:2048 -nodes \
      -keyout "$scaffold/cert.key" -out "$scaffold/cert.pem" -days 3650 \
      -subj "/CN=localhost" \
      -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" 2>/dev/null
  fi

  # Stand-in for the container's /config/nginx/ssl.conf. Paths are relative to
  # the nginx prefix (this dir), set with -p at launch.
  cat >"$scaffold/ssl.conf" <<'EOF'
# Local stand-in for the container's /config/nginx/ssl.conf.
ssl_certificate cert.pem;
ssl_certificate_key cert.key;
ssl_protocols TLSv1.2 TLSv1.3;
ssl_session_cache shared:SSL:1m;
EOF

  # default.conf adapted for standalone use: privileged ports -> high ports,
  # the absolute ssl.conf include -> our relative stand-in, and the upstream
  # backend. Only environment-specific bits change; proxy/location logic is
  # preserved verbatim.
  {
    echo "# GENERATED from ../default.conf by run-test-proxy.sh --regenerate."
    echo "# Do not edit by hand; rerun --regenerate after changing default.conf."
    sed -E \
      -e "s/listen 80 /listen ${HTTP_PORT} /" \
      -e "s/listen \[::\]:80 /listen [::]:${HTTP_PORT} /" \
      -e "s/listen 443 /listen ${HTTPS_PORT} /" \
      -e "s/listen \[::\]:443 /listen [::]:${HTTPS_PORT} /" \
      -e "s#include /config/nginx/ssl.conf;#include ssl.conf;#" \
      -e "s#proxy_pass http://localhost:9810;#proxy_pass http://${BACKEND};#" \
      "$default_conf"
  } >"$scaffold/server.conf"

  # Top-level wrapper. No 'user' directive (runs unprivileged); all paths are
  # relative to the nginx prefix so the scaffold is machine-independent.
  cat >"$scaffold/nginx.conf" <<'EOF'
# Standalone wrapper so default.conf's server block runs without the
# linuxserver container. Launch via run-test-proxy.sh (nginx -p test-proxy).
worker_processes 1;
daemon off;
pid tmp/nginx.pid;
error_log /dev/stderr info;
events { worker_connections 1024; }
http {
    default_type application/octet-stream;
    access_log /dev/stdout;
    client_body_temp_path tmp/client;
    proxy_temp_path tmp/proxy;
    fastcgi_temp_path tmp/fastcgi;
    uwsgi_temp_path tmp/uwsgi;
    scgi_temp_path tmp/scgi;
    include server.conf;
}
EOF

  cat >"$scaffold/.gitignore" <<'EOF'
# Ephemeral nginx temp/pid dir, recreated on each run.
tmp/
EOF
}

# Build the scaffold on demand: explicit --regenerate / flag overrides, or a
# first run before it's been committed.
required=("$scaffold/nginx.conf" "$scaffold/server.conf" "$scaffold/ssl.conf"
  "$scaffold/cert.pem" "$scaffold/cert.key")
missing=0
for f in "${required[@]}"; do [[ -f "$f" ]] || missing=1; done

if [[ "$regenerate" -eq 1 || "$missing" -eq 1 ]]; then
  generate_scaffold
  if [[ "$regenerate" -eq 1 ]]; then
    echo "[proxy] regenerated scaffold in $scaffold — commit it to git."
    exit 0
  fi
fi

# Ephemeral working dirs (gitignored).
mkdir -p "$scaffold/tmp"

nginx -p "$scaffold" -c "$scaffold/nginx.conf" -t

cat <<EOF
[proxy] nginx test reverse proxy
[proxy]   HTTP  : http://localhost:${HTTP_PORT}/
[proxy]   HTTPS : https://localhost:${HTTPS_PORT}/   (self-signed; curl -k)
[proxy]   -> backend in test-proxy/server.conf
[proxy]
[proxy] Subpath test: run Codex with url_path_prefix="/codex", then open
[proxy]   http://localhost:${HTTP_PORT}/codex/
[proxy] Ctrl+C to stop.
EOF

exec nginx -p "$scaffold" -c "$scaffold/nginx.conf"
