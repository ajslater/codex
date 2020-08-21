#!/bin/sh
# This papers over a macos crash that i think only happens on
#   development server rapid restarts
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
poetry run hypercorn --bind 0.0.0.0:8000 --quic-bind 0.0.0.0:8000 --reload codex.asgi:application
