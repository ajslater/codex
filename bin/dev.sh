#!/usr/bin/env bash
# Start the Codex development stack: Granian (backend) + Vite (frontend) in one terminal.
# Streams prefixed logs from both servers; Ctrl+C tears everything down.
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
cd "$repo_root"

backend_pgid=""
frontend_pgid=""

kill_group() {
  local name=$1 pgid=$2
  if [[ -z $pgid ]] || ! kill -0 -- "-$pgid" 2>/dev/null; then
    echo "[dev] $name already stopped"
    return 0
  fi
  echo "[dev] stopping $name (pgrp $pgid)"
  kill -TERM -- "-$pgid" 2>/dev/null || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if ! kill -0 -- "-$pgid" 2>/dev/null; then
      echo "[dev] $name stopped"
      return 0
    fi
    sleep 0.2
  done
  echo "[dev] $name ignored SIGTERM, sending SIGKILL"
  kill -KILL -- "-$pgid" 2>/dev/null || true
  sleep 0.2
  if kill -0 -- "-$pgid" 2>/dev/null; then
    echo "[dev] WARNING: $name still running after SIGKILL — run 'pgrep -fl granian|vite'"
  else
    echo "[dev] $name stopped"
  fi
}

cleanup() {
  trap - EXIT INT TERM
  echo
  echo "[dev] shutting down"
  kill_group "backend" "$backend_pgid"
  kill_group "frontend" "$frontend_pgid"
  wait 2>/dev/null || true
  echo "[dev] all stopped"
}
trap cleanup EXIT INT TERM

prefix() {
  local tag=$1
  while IFS= read -r line; do
    printf '[%s] %s\n' "$tag" "$line"
  done
}

run_backend() {
  export DEBUG="${DEBUG:-1}"
  export PYTHONDEBUG=1
  export PYTHONDEVMODE="$DEBUG"
  export PYTHONDONTWRITEBYTECODE=1
  export PYTHONPATH="${PYTHONPATH:-}:$repo_root"
  export PYTHONWARNINGS=always
  export DJANGO_SETTINGS_MODULE=codex.settings
  uv run python3 ./codex/run.py 2>&1 | prefix backend
}

run_frontend() {
  cd "$repo_root/frontend"
  bun run dev 2>&1 | prefix frontend
}

# Enable job control so each backgrounded job gets its own process group,
# which lets us SIGTERM the whole subtree (uv→python, bun→node, prefix).
# Without this, bash also auto-ignores SIGINT in background jobs, so Ctrl+C
# wouldn't reach Granian or Vite at all.
set -m

echo "[dev] starting Granian on http://localhost:9810"
run_backend &
backend_pgid=$!

echo "[dev] starting Vite on http://localhost:5173"
run_frontend &
frontend_pgid=$!

set +m

wait -n
