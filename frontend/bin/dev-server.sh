#!/bin/sh
# Run the live reloading front end development server
THIS_DIR="$(dirname "$0")"
cd "$THIS_DIR" || exit 1
bun run dev
