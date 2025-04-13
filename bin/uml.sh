#!/bin/bash
# Generate a big UML png diagram of codex classes
# Requires tomlq & jq
set -euo pipefail
THIS_DIR="$(dirname "$0")/.."
cd "$THIS_DIR" || exit 1

CLASSES_UML=classes.plantuml
PACKAGES_UML=packages.plantuml
is_uml_out_of_date() {
  find "$2" -type f -name "*.py" | while read -r file; do
    if [ "$1" -ot "$file" ]; then
      echo 'out_of_date'
    fi
  done
}

ensure_latest_jar() {
  # Get latest plantuml jar
  latest_version() {
    curl --silent "https://api.github.com/repos/$1/releases/latest" | jq -r .tag_name
  }
  echo "Checking plantuml for updates..."
  local PLANTUML_VERSION
  PLANTUML_VERSION=$(latest_version plantuml/plantuml)
  local PLANTUML_JAR
  PLANTUML_JAR=plantuml-${PLANTUML_VERSION:1}.jar
  if [ ! -f "$PLANTUML_JAR" ]; then
    local PLANTUML_URL
    PLANTUML_URL=https://github.com/plantuml/plantuml/releases/download/${PLANTUML_VERSION}/$PLANTUML_JAR
    curl --location --remote-name --progress-bar "$PLANTUML_URL"
  fi
}

UML_OUT_OF_DATE=$(is_uml_out_of_date "$CLASSES_UML" "$PACKAGE_DIR")

if [ "$UML_OUT_OF_DATE" != "" ]; then
  export PYTHONPATH="${PYTHONPATH:-}:$THIS_DIR"
  echo "Generating UML..."
  uv run pyreverse --colorized --output plantuml "$PACKAGE_DIR"
  echo "done."
else
  echo "UML is up to date."
fi

if [[ $CLASSES_UML -ot classes.png ]]; then
  echo "UML images are up to date."
  exit 0
fi
ensure_latest_jar

export PLANTUML_LIMIT_SIZE=65536
java -jar "$PLANTUML_JAR" "$CLASSES_UML"
java -jar "$PLANTUML_JAR" "$PACKAGES_UML"
