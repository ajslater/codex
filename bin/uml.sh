#!/bin/bash
# Generate a big UML png diagram of codex classes
# Improvements:
#   - Only run pyreverse if code changes
#   - Only running plantuml if *.plantuml changes
#   - Download latest plantuml version
#   - Read package dir from pyproject.toml
set -euo pipefail
PACKAGE_DIR=codex
PLANTUML_VERSION=1.2024.7
THIS_DIR="$(dirname "$0")/.."
cd "$THIS_DIR" || exit 1
export PYTHONPATH="${PYTHONPATH:-}:$THIS_DIR"
poetry run pyreverse --colorized --output plantuml "$PACKAGE_DIR"
export PLANTUML_LIMIT_SIZE=131072
PLANTUML_JAR=plantuml-${PLANTUML_VERSION}.jar
if [ ! -f "$PLANTUML_JAR" ]; then
    PLANTUML_URL=https://github.com/plantuml/plantuml/releases/download/v${PLANTUML_VERSION}/$PLANTUML_JAR
    wget "$PLANTUML_URL"
fi
java -jar "$PLANTUML_JAR" classes.plantuml
java -jar "$PLANTUML_JAR" packages.plantuml
