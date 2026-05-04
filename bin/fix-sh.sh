#!/usr/bin/env bash
# Fix shell script formatting
set -euxo pipefail

shellharden --replace ./**/*.sh
