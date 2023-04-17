#!/bin/bash
# Find the diffs for two vendored packages.
# vendor the original package into codex/_vendor_orig before comparing edits
# Would be slicker if this automated the creation and destruction of _vendor-orig in /tmp
set -euo pipefail
PKG=$1
MODULE=$2
VENDOR_TARGET=/tmp/_vendor_orig
rm -rf "$VENDOR_TARGET"
mkdir -p "$VENDOR_TARGET"

cd cache

# vendorize the original in a tmp dir
cat <<EOT >vendorize.toml
target = "$VENDOR_TARGET"
packages = [ "$PKG" ]
EOT
poetry run python-vendorize

# compare
DIFF_FN="../codex/_vendor/$PKG.diff"
echo "# Non automated/import patches to $PKG" >"$DIFF_FN"
diff --minimal --recursive --suppress-common-lines \
    -x "*~" \
    -x "*.pyc" \
    -x "*__pycache__*" \
    "$VENDOR_TARGET/$MODULE" \
    "../codex/_vendor/$MODULE" |
    rg -v "Binary|Only" >>"$DIFF_FN"

# cleanup
rm -rf "$VENDOR_TARGET"
rm -f vendorize.toml
