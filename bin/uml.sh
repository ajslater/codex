#!/bin/bash
# Create UML diagram
set -euo pipefail
PACKAGE=$(uv run toml get --toml-path=pyproject.toml project.name)
uvx --from pylint pyreverse -o png "$PACKAGE"
