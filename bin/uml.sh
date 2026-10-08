#!/usr/bin/env bash
# Create UML diagrams of the project's package in test-results/uml
set -euo pipefail
NAME=$(uv run toml get --toml-path=pyproject.toml project.name)
# pyreverse wants the import name, which has _ where the project name has -.
PACKAGE=${NAME//-/_}
OUTPUT_DIR=test-results/uml
mkdir -p "$OUTPUT_DIR"
uvx --from pylint pyreverse --output png --output-directory "$OUTPUT_DIR" "$PACKAGE"
