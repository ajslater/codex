#!/bin/sh
./setup.sh
poetry run daphne -b 0.0.0.0 -p 8000 codex.asgi:application
