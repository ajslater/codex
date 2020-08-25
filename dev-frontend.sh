#!/bin/sh
# Run the live reloading front end development server
cd "$(dirname "$0")/frontend" || exit 1
npm run dev
