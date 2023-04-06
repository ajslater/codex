#!/bin/bash
# Build all icons from source.
# Requires MacOS inkscape & picopt
set -euxo pipefail

TOP_PATH="$(dirname "$(realpath "$0")")"
IMG_PATH=codex/img
RELATIVE_STATIC_PATH=../static_src/img
export PATH=$PATH:/Applications/Inkscape.app/Contents/MacOS

cd "$IMG_PATH"
LOGO_PATH=logo.svg
STATIC_LOGO_PATH=$RELATIVE_STATIC_PATH/logo.svg
# if logo.svg has changed
npx svgo --multipass --pretty --input "$LOGO_PATH" --output "$STATIC_LOGO_PATH"

LOGO_32_PATH=$RELATIVE_STATIC_PATH/logo-32.png
inkscape --export-width=32 --export-height=32 --export-filename="$LOGO_32_PATH" "$LOGO_PATH"

# create logo-maskable.svg from logo.svg
LOGO_MASKABLE_PATH=logo-maskable.svg
MASKABLE_ICON_PATH=$RELATIVE_STATIC_PATH/logo-maskable.svg
# This is fragile without a proper xml tool.
sed 's/inkscape:label="logo"/inkscape:label="logo"\n    transform="matrix(0.80,0,0,0.80,51.5,51.5)"/' "$LOGO_PATH" >"$LOGO_MASKABLE_PATH"
npx svgo --multipass --pretty --input "$LOGO_MASKABLE_PATH" --output "$MASKABLE_ICON_PATH"

LOGO_MASKABLE_180_PATH=$RELATIVE_STATIC_PATH/logo-maskable-180.png
inkscape --export-width=180 --export-height=180 --export-filename="$LOGO_MASKABLE_180_PATH" "$LOGO_MASKABLE_PATH"

# if missing-cover.svg or logo.svg has changed
inkscape --export-filename=missing-cover.png missing-cover.svg

MISSING_PAGE_PATH=missing-page.svg
STATIC_MISSING_PAGE_PATH=$RELATIVE_STATIC_PATH/$MISSING_PAGE_PATH
npx svgo --multipass --pretty --input "$MISSING_PAGE_PATH" --output "$STATIC_MISSING_PAGE_PATH"

cd "$TOP_PATH"
STATIC_PATH=codex/static_src/img
picopt -rc WEBP "$IMG_PATH" "$STATIC_PATH"
