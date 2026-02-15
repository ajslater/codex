#!/usr/bin/env python3
"""
Deep merge multiple YAML files into a single merged YAML file.

This script recursively merges YAML files, with later files taking precedence
over earlier ones. Lists can be either replaced or appended based on configuration.

Requirements:
    Python 3.14+
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


def deep_merge(
    base: dict[Any, Any], updates: dict[Any, Any], list_strategy: str = "replace"
) -> dict[Any, Any]:
    """
    Recursively merge two dictionaries.

    Args:
        base: The base dictionary to merge into
        updates: The dictionary with updates to apply
        list_strategy: How to handle lists - 'replace' (default) or 'append'

    Returns:
        The merged dictionary

    """
    result = base.copy()

    for key, value in updates.items():
        if key in result:
            # Both values are dictionaries - recurse
            if isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value, list_strategy)
            # Both values are lists - apply strategy
            elif isinstance(result[key], list) and isinstance(value, list):
                if list_strategy == "append":
                    result[key] = result[key] + value
                else:  # replace
                    result[key] = value
            # Otherwise, the new value overwrites the old
            else:
                result[key] = value
        else:
            # New key - just add it
            result[key] = value

    return dict(sorted(result.items()))


def load_yaml_file(filepath: Path) -> dict[Any, Any]:
    """
    Load a YAML file and return its contents.

    Args:
        filepath: Path to the YAML file

    Returns:
        The parsed YAML content as a dictionary

    """
    content = yaml.safe_load(filepath.read_text())
    # Handle empty files
    if content is None:
        return {}
    if not isinstance(content, dict):
        reason = f"{filepath} does not contain a YAML dictionary at root level"
        raise TypeError(reason)
    return content


def merge_yaml_files(
    filepaths: list[Path], list_strategy: str = "replace"
) -> dict[Any, Any]:
    """
    Merge multiple YAML files in order.

    Args:
        filepaths: List of paths to YAML files (in order of precedence)
        list_strategy: How to handle lists - 'replace' or 'append'

    Returns:
        The merged dictionary

    """
    if not filepaths:
        return {}

    # Start with the first file
    result = load_yaml_file(filepaths[0])

    # Merge in each subsequent file
    for filepath in filepaths[1:]:
        updates = load_yaml_file(filepath)
        result = deep_merge(result, updates, list_strategy)

    return result


def main() -> None:
    """
    Run CLI.

    Parses command-line arguments, validates input files, performs the merge,
    and outputs the result to stdout or a file.
    """
    parser = argparse.ArgumentParser(
        description="Deep merge multiple YAML files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Merge three files, output to stdout
  %(prog)s base.yaml overrides.yaml local.yaml

  # Merge and save to output file
  %(prog)s base.yaml overrides.yaml -o merged.yaml

  # Merge with list appending instead of replacement
  %(prog)s base.yaml overrides.yaml --list-strategy append
        """,
    )

    parser.add_argument(
        "files",
        nargs="+",
        type=Path,
        help="YAML files to merge (in order of precedence - later files override earlier ones)",
    )

    parser.add_argument(
        "-o", "--output", type=Path, help="Output file path (default: stdout)"
    )

    parser.add_argument(
        "--list-strategy",
        choices=["replace", "append"],
        default="replace",
        help="How to handle list merging: replace (default) or append",
    )

    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Number of spaces for YAML indentation (default: 2)",
    )

    args = parser.parse_args()

    # Validate input files exist
    for filepath in args.files:
        if not filepath.exists():
            reason = f"File not found: {filepath}"
            parser.error(reason)

    try:
        # Perform the merge
        merged_data = merge_yaml_files(args.files, args.list_strategy)

        # Output the result
        yaml_output = yaml.dump(
            merged_data, default_flow_style=False, sort_keys=False, indent=args.indent
        )

        if args.output:
            args.output.write_text(yaml_output)
            print(f"Merged YAML written to: {args.output}")  # noqa: T201
        else:
            print(yaml_output)  # noqa: T201

    except Exception as e:
        reason = f"Error during merge: {e}"
        parser.error(reason)


if __name__ == "__main__":
    main()
