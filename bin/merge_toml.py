#!/usr/bin/env python3
"""
Deep merge multiple TOML files into a single merged file using tomlkit.

This script recursively merges TOML files, with later files taking precedence
over earlier ones. Uses tomlkit to preserve formatting, comments, and style.
String values containing commas are treated as comma-delimited lists that get
merged and sorted. Python dependency lists are merged with version-aware
comparison to prefer higher version constraints.

Requirements:
    pip install tomlkit packaging
    Python 3.14+
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tomlkit
from packaging.requirements import Requirement
from packaging.version import InvalidVersion, Version
from tomlkit import TOMLDocument, inline_table, table
from tomlkit.items import Array, InlineTable, String, Table

if TYPE_CHECKING:
    from packaging.specifiers import SpecifierSet

PYTHON_DEP_KEY_PATH_LEN = 2


def is_comma_delimited_string(value: Any) -> bool:
    """Check if a value is a string containing commas (comma-delimited list)."""
    return isinstance(value, str | String) and "," in str(value)


def parse_comma_delimited(value: str) -> list[str]:
    """Parse a comma-delimited string into a list of trimmed strings."""
    return [item.strip() for item in str(value).split(",") if item.strip()]


def serialize_comma_delimited(items: list[str]) -> str:
    """Serialize a list of strings into a comma-delimited string."""
    return ",".join(sorted(set(items)))


def merge_comma_delimited_strings(base_value: str, update_value: str) -> str:
    """Merge two comma-delimited strings by parsing, combining, sorting, and serializing."""
    base_items = parse_comma_delimited(base_value)
    update_items = parse_comma_delimited(update_value)
    merged_items = base_items + update_items
    return serialize_comma_delimited(merged_items)


def is_python_dependency_key(key_path: tuple[str, ...]) -> bool:
    """
    Check if a key path represents a Python dependency list.

    Handles:
    - project.dependencies
    - dependency-groups.* (any subkey)
    - build-system.requires

    Args:
        key_path: Tuple of keys representing the path (e.g., ('project', 'dependencies'))

    Returns:
        True if this is a Python dependency list

    """
    if len(key_path) == PYTHON_DEP_KEY_PATH_LEN:
        if key_path == ("project", "dependencies"):
            return True
        if key_path == ("build-system", "requires"):
            return True
        if key_path[0] == "dependency-groups":
            return True
    return False


def parse_python_requirement(dep_string: str) -> tuple[str, SpecifierSet | None]:
    """
    Parse a Python dependency string into package name and version specifiers.

    Args:
        dep_string: A PEP 508 dependency string (e.g., "requests>=2.28.0")

    Returns:
        Tuple of (package_name, specifier_set) or (package_name, None) if no version

    """
    try:
        req = Requirement(dep_string.strip())
        return req.name.lower(), req.specifier or None
    except Exception:
        # If parsing fails, try to extract just the package name
        # Handle simple cases like "package-name" without version
        match = re.match(r"^([a-zA-Z0-9._-]+)", dep_string.strip())
        if match:
            return match.group(1).lower(), None
        # If all else fails, return the string as-is
        return dep_string.strip().lower(), None


def get_max_version_from_specifier(spec: SpecifierSet) -> Version | None:
    """
    Extract the maximum/preferred version from a specifier set.

    For comparison purposes, we extract a representative version:
    - For >=x.y.z, use x.y.z
    - For ==x.y.z, use x.y.z
    - For ~=x.y.z, use x.y.z
    - For <x.y.z, use a version slightly less
    - For complex specs, try to find the highest lower bound

    Args:
        spec: A SpecifierSet from packaging

    Returns:
        A representative Version or None

    """
    if not spec:
        return None

    versions: list[Version] = []
    for s in spec:
        # Extract version from the specifier
        try:
            ver = Version(s.version)
            # Prefer lower bounds (>=, ==, ~=) over upper bounds
            if s.operator in (">=", "==", "~=", ">"):
                versions.append(ver)
            elif s.operator in ("<=", "<"):
                # Upper bounds are less preferred
                versions.append(ver)
        except InvalidVersion:
            continue

    return max(versions) if versions else None


def _merge_python_dependency(dep, deps):
    pkg_name, update_spec = parse_python_requirement(dep)

    if pkg_name in deps:
        _, base_spec = deps[pkg_name]

        # If neither has a version, keep the update (later precedence)
        if base_spec is None and update_spec is None:
            deps[pkg_name] = (dep, update_spec)
            return

        # If only one has a version, prefer the one with version
        if base_spec is None:
            deps[pkg_name] = (dep, update_spec)
            return
        if update_spec is None:
            # Keep base (it has a version)
            return

        # Both have versions - compare them
        base_ver = get_max_version_from_specifier(base_spec)
        update_ver = get_max_version_from_specifier(update_spec)

        # If we can compare, use the higher version
        if base_ver and update_ver:
            if update_ver > base_ver:
                deps[pkg_name] = (dep, update_spec)
            # else keep base
        elif update_ver:
            # Only update has a comparable version
            deps[pkg_name] = (dep, update_spec)
        # else keep base

    else:
        # New package
        deps[pkg_name] = (dep, update_spec)


def merge_python_dependencies(base: list[str], updates: list[str]) -> list[str]:
    """
    Merge two Python dependency lists, preferring higher version constraints.

    Args:
        base: Base dependency list
        updates: Update dependency list

    Returns:
        Merged dependency list with highest versions preferred

    """
    # Parse all dependencies into a dict keyed by package name
    deps: dict[str, tuple[str, SpecifierSet | None]] = {}

    # Process base dependencies
    for dep in base:
        pkg_name, spec = parse_python_requirement(dep)
        if pkg_name not in deps:
            deps[pkg_name] = (dep, spec)

    # Process update dependencies, comparing versions
    for dep in updates:
        _merge_python_dependency(dep, deps)
    # Return the merged list, preserving order by package name
    return [dep_str for dep_str, _ in sorted(deps.values(), key=lambda x: x[0].lower())]


def _copy_toml_structure(
    base: TOMLDocument | Table | InlineTable | dict[str, Any],
) -> TOMLDocument | Table | InlineTable | dict[str, Any]:
    """
    Create a copy of a tomlkit structure to avoid modifying the original.

    Args:
        base: The tomlkit structure to copy

    Returns:
        A copy of the structure

    """
    result: TOMLDocument | Table | InlineTable | dict[str, Any]
    if isinstance(base, TOMLDocument):
        result = tomlkit.document()
        for key, value in base.items():
            result[key] = value
    elif isinstance(base, InlineTable):
        result = inline_table()
        for key, value in base.items():
            result[key] = value
    elif isinstance(base, Table):
        result = table()
        for key, value in base.items():
            result[key] = value
    else:
        result = dict(base)
    return result


def _is_table_like(value: Any) -> bool:
    """Check if a value is a table-like tomlkit structure."""
    return isinstance(value, dict | Table | InlineTable | TOMLDocument)


def _merge_arrays(
    base_value: list[Any] | Array,
    update_value: list[Any] | Array,
    list_strategy: str,
    key_path: tuple[str, ...] = (),
) -> Array | list[Any]:
    """
    Merge two array values based on the list strategy.

    Args:
        base_value: The base array
        update_value: The update array
        list_strategy: How to handle lists - 'merge' or 'replace'
        key_path: The path to this key for detecting Python dependencies

    Returns:
        The merged array

    """
    # Check if this is a Python dependency list
    if is_python_dependency_key(key_path):
        # Convert to string list and merge with version comparison
        base_strs = [str(item) for item in base_value]
        update_strs = [str(item) for item in update_value]
        merged_strs = merge_python_dependencies(base_strs, update_strs)

        # Convert back to Array
        new_array = tomlkit.array()
        for item in merged_strs:
            new_array.append(item)
        return new_array

    # Normal list merging
    if list_strategy == "merge":
        # Create new array with combined items
        new_array = tomlkit.array()
        for item in base_value:
            new_array.append(item)
        for item in update_value:
            if item not in new_array:
                new_array.append(item)
        return sorted(new_array)
    # replace
    return update_value


def _merge_comma_strings(base_value: Any, update_value: Any) -> str:
    """
    Merge values that are or contain comma-delimited strings.

    Args:
        base_value: The base value
        update_value: The update value

    Returns:
        A merged comma-delimited string

    """
    base_items = (
        parse_comma_delimited(str(base_value))
        if is_comma_delimited_string(base_value)
        else [str(base_value)]
    )
    update_items = (
        parse_comma_delimited(str(update_value))
        if is_comma_delimited_string(update_value)
        else [str(update_value)]
    )
    return serialize_comma_delimited(base_items + update_items)


def _merge_value_pair(
    base_value: Any, update_value: Any, list_strategy: str, key_path: tuple[str, ...]
) -> Any:
    """
    Merge a single key's base and update values.

    Args:
        base_value: The existing value
        update_value: The new value to merge in
        list_strategy: How to handle lists - 'replace' or 'append'
        key_path: The path to this key for detecting special merge behavior

    Returns:
        The merged value

    """
    # Both are table-like structures - recurse
    if _is_table_like(base_value) and _is_table_like(update_value):
        return deep_merge_tomlkit(base_value, update_value, list_strategy, key_path)

    # Both values are comma-delimited strings - merge them
    if is_comma_delimited_string(base_value) and is_comma_delimited_string(
        update_value
    ):
        return merge_comma_delimited_strings(str(base_value), str(update_value))

    # One is comma-delimited, other is not - convert and merge
    if is_comma_delimited_string(base_value) or is_comma_delimited_string(update_value):
        return _merge_comma_strings(base_value, update_value)

    # Both values are arrays - apply strategy (may use Python dependency merging)
    if isinstance(base_value, list | Array) and isinstance(update_value, list | Array):
        return _merge_arrays(base_value, update_value, list_strategy, key_path)

    # Otherwise, the new value overwrites the old
    return update_value


def deep_merge_tomlkit(
    base: Any,
    updates: Any,
    list_strategy: str = "replace",
    key_path: tuple[str, ...] = (),
) -> TOMLDocument | Table | InlineTable | dict[str, Any]:
    """
    Recursively merge two tomlkit structures.

    tomlkit preserves all formatting, comments, and style automatically.
    We just need to handle the merge logic.

    Args:
        base: The base tomlkit structure to merge into
        updates: The tomlkit structure with updates to apply
        list_strategy: How to handle lists - 'replace' (default) or 'append'
        key_path: Current path in the document (for detecting Python dependencies)

    Returns:
        The merged structure

    """
    # If base is not a table-like structure, just return updates
    if not _is_table_like(base):
        return updates

    # Create a copy to avoid modifying the original
    result = _copy_toml_structure(base)

    # Merge updates into result
    for key, update_value in updates.items():
        current_path = (*key_path, key)

        if key in result:
            base_value = result[key]
            result[key] = _merge_value_pair(
                base_value, update_value, list_strategy, current_path
            )
        else:
            # New key - just add it
            result[key] = update_value

    return result


def load_toml_file(filepath: Path) -> TOMLDocument:
    """
    Load a TOML file and return its contents as a tomlkit document.

    Args:
        filepath: Path to the TOML file

    Returns:
        The parsed TOML content as a tomlkit document

    """
    content = filepath.read_text()
    return tomlkit.parse(content)


def merge_toml_files(
    filepaths: list[Path], list_strategy: str = "replace"
) -> TOMLDocument | Table | InlineTable | dict[str, Any]:
    """
    Merge multiple TOML files in order, preserving formatting and comments.

    Args:
        filepaths: List of paths to TOML files (in order of precedence)
        list_strategy: How to handle lists - 'replace' or 'append'

    Returns:
        The merged tomlkit document

    """
    if not filepaths:
        return tomlkit.document()

    # Start with the first file
    result = load_toml_file(filepaths[0])

    # Merge in each subsequent file
    for filepath in filepaths[1:]:
        updates = load_toml_file(filepath)
        result = deep_merge_tomlkit(result, updates, list_strategy)

    return result


def main() -> None:
    """
    Run CLI.

    Parses command-line arguments, validates input files, performs the merge
    with comma-delimited string handling and automatic comment/format preservation,
    and outputs the result to stdout or a file.
    """
    parser = argparse.ArgumentParser(
        description="Deep merge multiple TOML files with comment preservation using tomlkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Merge three files, output to stdout
  %(prog)s base.toml overrides.toml local.toml

  # Merge and save to output file
  %(prog)s base.toml overrides.toml -o merged.toml

  # Merge with list appending instead of replacement
  %(prog)s base.toml overrides.toml --list-strategy append

Python Dependency Merging:
  Lists at these TOML paths are treated as Python dependencies with
  version-aware merging (prefers higher version constraints):
    - project.dependencies
    - dependency-groups.* (any dependency group)
    - build-system.requires

  Example:
    base.toml:     dependencies = ["requests>=2.28.0", "click>=8.0.0"]
    override.toml: dependencies = ["requests>=2.31.0", "rich>=13.0.0"]
    result:        dependencies = ["click>=8.0.0", "requests>=2.31.0", "rich>=13.0.0"]

Comma-Delimited String Handling:
  String values containing commas are treated as comma-delimited lists.
  They are merged, deduplicated, sorted, and serialized back to strings.

  Example:
    base.toml:    tags = "python, yaml"  # Important configuration
    override.toml: tags = "toml, python"
    result:       tags = "python, toml, yaml"  # Important configuration

Comment and Format Preservation:
  tomlkit automatically preserves:
  - All comments (inline and block)
  - Formatting and whitespace
  - Key ordering
  - Inline table vs regular table style
  - String quote style (single vs double)
  - Number formatting (hex, binary, etc.)
        """,
    )

    parser.add_argument(
        "files",
        nargs="+",
        type=Path,
        help="TOML files to merge (in order of precedence - later files override earlier ones)",
    )

    parser.add_argument(
        "-o", "--output", type=Path, help="Output file path (default: stdout)"
    )

    parser.add_argument(
        "--list-strategy",
        choices=["merge", "replace"],
        default="merge",
        help="How to handle list merging: replace (default) or append",
    )

    args = parser.parse_args()

    # Validate input files exist
    for filepath in args.files:
        if not filepath.exists():
            reason = f"File not found: {filepath}"
            parser.error(reason)

    try:
        # Perform the merge
        merged_doc = merge_toml_files(args.files, args.list_strategy)

        # Output the result
        toml_output = tomlkit.dumps(merged_doc)

        if args.output:
            args.output.write_text(toml_output)
            print(f"Merged TOML written to: {args.output}")  # noqa: T201
        else:
            print(toml_output)  # noqa: T201

    except Exception as e:
        # Broad except is acceptable here for CLI error handling
        reason = f"Error during merge: {e}"
        parser.error(reason)


if __name__ == "__main__":
    main()
