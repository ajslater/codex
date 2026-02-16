#!/usr/bin/env python3
"""
Deep merge multiple package.json files into a single merged file.

This script recursively merges package.json files, with later files taking precedence
over earlier ones. Special handling for dependencies and devDependencies where
semver ranges are intelligently merged to prefer higher version constraints.

Requirements:
    pip install semver
    Python 3.14+
"""

from __future__ import annotations

import argparse
import json
import re
from contextlib import suppress
from pathlib import Path
from typing import Any

import semver

SEMVER_LEN = 3
SPECIAL_PROTOCOLS = frozenset(
    {
        "git+",
        "github:",
        "file:",
        "http://",
        "https://",
        "workspace:",
    }
)


def is_spec_special(spec_str):
    """Determine if the spec start with a protocol."""
    return any(spec_str.startswith(prefix) for prefix in SPECIAL_PROTOCOLS)


def extract_version_from_range(version_str: str) -> str | None:
    """Extract a base semver version from an npm version range string."""
    # Handle special cases
    if version_str in ("*", "latest", "", "next"):
        return None

    # Remove common npm range operators
    cleaned = version_str
    for op in ["^", "~", "=", "v", ">=", "<=", ">", "<"]:
        cleaned = cleaned.replace(op, "")

    # Handle OR ranges - take the first one
    if "||" in cleaned:
        cleaned = cleaned.split("||")[0].strip()

    # Handle hyphen ranges - take the first version
    if " - " in cleaned:
        cleaned = cleaned.split(" - ")[0].strip()

    # Take first space-separated token
    cleaned = cleaned.split()[0].strip() if " " in cleaned else cleaned.strip()

    # Remove wildcards
    cleaned = cleaned.replace("x", "0").replace("X", "0")

    # Ensure we have at least major.minor.patch
    parts = cleaned.split(".")
    while len(parts) < SEMVER_LEN:
        parts.append("0")

    # Handle prerelease tags
    base_spec = ".".join(parts[:SEMVER_LEN])
    if "-" in parts[2]:
        base_spec = ".".join(parts[:2]) + "." + parts[2]

    # Validate it's a proper version
    try:
        semver.VersionInfo.parse(base_spec)
        result_spec = base_spec
    except (ValueError, AttributeError):
        result_spec = None
    return result_spec


def get_version_prefix(version_str: str) -> str:
    """Extract the npm range prefix from a version string."""
    # Order matters: >= and <= must come before > and
    if match := re.match(r"^([\^~]|>=|<=|>|<|=)", version_str):
        return match.group(1)
    return "="


def merge_dependency_specs(base_spec: str, update_spec: str) -> str:  # noqa: PLR0911
    """
    Merge two npm semver version strings, preferring the higher version.

    Uses the semver package for proper semantic version comparison.
    Handles npm-specific version ranges (^, ~, >=, etc.)
    """
    if is_spec_special(base_spec):
        return base_spec
    if is_spec_special(update_spec):
        return update_spec

    # Try to extract actual versions from ranges
    base_extracted = extract_version_from_range(base_spec)
    update_extracted = extract_version_from_range(update_spec)

    # If we can't parse either, prefer the update
    if base_extracted is None and update_extracted is None:
        return update_spec

    # If only one is parseable, use that one
    if base_extracted is None:
        return update_spec
    if update_extracted is None:
        return base_spec

    # Compare the extracted versions
    try:
        base_ver = semver.VersionInfo.parse(base_extracted)
        update_ver = semver.VersionInfo.parse(update_extracted)

        # Compare versions
        if update_ver > base_ver:
            return update_spec
        if base_ver > update_ver:
            return base_spec
        # Versions are equal, prefer more flexible range
        # Priority: ^ > ~ > >= > exact
        base_prefix = get_version_prefix(base_spec)
        update_prefix = get_version_prefix(update_spec)

        prefix_priority = {"": 0, "=": 0, ">=": 1, "~": 2, "^": 3}
        base_priority = prefix_priority.get(base_prefix, 0)
        update_priority = prefix_priority.get(update_prefix, 0)

        result_spec = update_spec if update_priority > base_priority else base_spec

    except (ValueError, AttributeError):
        # If comparison fails, prefer update
        result_spec = update_spec
    return result_spec


def merge_dependencies(base: dict[str, str], updates: dict[str, str]) -> dict[str, str]:
    """
    Merge two dependency dictionaries with semver-aware version selection.

    Args:
        base: Base dependencies
        updates: Update dependencies

    Returns:
        Merged dependencies with higher versions preferred

    """
    result = base.copy()

    for package, version in updates.items():
        if package in result:
            # Merge versions, preferring higher
            result[package] = merge_dependency_specs(result[package], version)
        else:
            # New package
            result[package] = version

    return result


def _deep_merge_override(base_val, value):
    """Handle overrides: deduplicate by "files" key."""
    # Prioritize base values when there are duplicates
    dedup_dict: dict[str, Any] = {}

    # Add base items first (these take priority)
    for item in base_val:
        if isinstance(item, dict) and "files" in item:
            dedup_key = ":".join(sorted(item["files"]))
            dedup_dict[dedup_key] = item

    # Add update items only if not already present
    for item in value:
        if isinstance(item, dict) and "files" in item:
            dedup_key = ":".join(sorted(item["files"]))
            if dedup_key not in dedup_dict:
                dedup_dict[dedup_key] = item

    dedup_dict = dict(sorted(dedup_dict.items()))

    return list(dedup_dict.values())


def _deep_merge_value(key, value, result, list_strategy):
    if key not in result:
        # New key - just add it
        result[key] = value
        return

    base_val = result[key]

    # Special handling for dependency objects
    if key.lower().endswith("dependencies"):
        result[key] = merge_dependencies(base_val, value)

    # Both values are dictionaries - recurse
    elif isinstance(base_val, dict) and isinstance(value, dict):
        result[key] = deep_merge(base_val, value, list_strategy)

    # Both values are lists - apply strategy
    elif isinstance(base_val, list) and isinstance(value, list):
        if list_strategy == "merge":
            if key == "overrides":
                result[key] = _deep_merge_override(base_val, value)
            else:
                # Regular list merging with deduplication and sorting
                merged_list = base_val + value
                # Try to deduplicate if possible (for hashable types)
                with suppress(TypeError):
                    merged_list = list(set(merged_list))
                result[key] = sorted(merged_list)
        else:
            result[key] = value

    # Otherwise, the new value overwrites the old
    else:
        result[key] = value


def deep_merge(
    base: dict[Any, Any], updates: dict[Any, Any], list_strategy: str = "replace"
) -> dict[Any, Any]:
    """
    Recursively merge two dictionaries.

    Special handling for dependency keys where semver versions are compared.
    """
    result = base.copy()
    for key, value in updates.items():
        _deep_merge_value(key, value, result, list_strategy)
    return result


def load_package_json(filepath: Path) -> dict[Any, Any]:
    """Load a package.json file and return its contents."""
    content = json.loads(filepath.read_text())
    if not isinstance(content, dict):
        reason = f"{filepath} does not contain a JSON object at root level"
        raise TypeError(reason)
    return content


def merge_package_json_files(
    filepaths: list[Path], list_strategy: str = "replace"
) -> dict[Any, Any]:
    """Merge multiple package.json files in order."""
    if not filepaths:
        return {}

    # Start with the first file
    result = load_package_json(filepaths[0])

    # Merge in each subsequent file
    for filepath in filepaths[1:]:
        updates = load_package_json(filepath)
        result = deep_merge(result, updates, list_strategy)

    return result


def main() -> None:
    """
    Run cli.

    Parses command-line arguments, validates input files, performs the merge
    with semver-aware dependency handling, and outputs the result to stdout or a file.
    """
    parser = argparse.ArgumentParser(
        description="Deep merge multiple package.json files with semver-aware dependency merging",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Merge three files, output to stdout
  %(prog)s package.json package-override.json package-local.json

  # Merge and save to output file
  %(prog)s package.json package-dev.json -o package-merged.json

  # Merge with array appending instead of replacement
  %(prog)s package.json package-extra.json --list-strategy append

Dependency Merging:
  For dependencies, devDependencies, and related keys, the tool compares
  semver version strings and keeps the higher version constraint.

  Example:
    base:    "express": "^4.17.1"
    update:  "express": "^4.18.0"
    result:  "express": "^4.18.0"

    base:    "react": "~16.8.0"
    update:  "react": "^17.0.0"
    result:  "react": "^17.0.0"
        """,
    )

    parser.add_argument(
        "files",
        nargs="+",
        type=Path,
        help="package.json files to merge (in order of precedence - later files override earlier ones)",
    )

    parser.add_argument(
        "-o", "--output", type=Path, help="Output file path (default: stdout)"
    )

    parser.add_argument(
        "--list-strategy",
        choices=["merge", "replace"],
        default="merge",
        help="How to handle array merging: replace (default) or append",
    )

    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Number of spaces for JSON indentation (default: 2)",
    )

    args = parser.parse_args()

    # Validate input files exist
    for filepath in args.files:
        if not filepath.exists():
            reason = f"File not found: {filepath}"
            parser.error(reason)

    # Perform the merge
    merged_data = merge_package_json_files(args.files, args.list_strategy)

    # Output the result
    json_output = json.dumps(merged_data, indent=args.indent, ensure_ascii=False)
    json_output += "\n"  # Add trailing newline like npm does

    if args.output:
        args.output.write_text(json_output)
        print(f"Merged package.json written to: {args.output}")  # noqa: T201
    else:
        print(json_output)  # noqa: T201


if __name__ == "__main__":
    main()
