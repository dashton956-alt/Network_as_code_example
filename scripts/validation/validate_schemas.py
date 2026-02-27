#!/usr/bin/env python3
"""
scripts/validation/validate_schemas.py

Validates changed intent/site YAML files against their schemas.
Called by the CI pipeline on every PR.
"""

import argparse
import sys
import os
import yaml
from pathlib import Path

try:
    import pykwalify.core
    from pykwalify.errors import SchemaError
except ImportError:
    print("pykwalify not installed. Run: pip install pykwalify")
    sys.exit(1)


SCHEMA_MAP = {
    "intents": "schema/intent.schema.yaml",
    "sites": "schema/site.schema.yaml",
    "customer.yaml": "schema/customer.schema.yaml",
}


def get_schema_for_file(filepath: str) -> str | None:
    """Determine which schema applies to a given file path."""
    path = Path(filepath)

    # Intents: customers/<name>/intents/**/*.yaml
    if "intents" in path.parts:
        return SCHEMA_MAP["intents"]

    # Sites: customers/<name>/sites/*.yaml
    if "sites" in path.parts:
        return SCHEMA_MAP["sites"]

    # Customer metadata
    if path.name == "customer.yaml":
        return SCHEMA_MAP.get("customer.yaml")

    return None  # No schema needed (e.g. policy.yaml, rendered/)


def validate_file(filepath: str, schema_path: str) -> list[str]:
    """
    Validate a YAML file against a schema.
    Returns list of error messages (empty = pass).
    """
    errors = []

    # Check file exists
    if not os.path.exists(filepath):
        errors.append(f"File not found: {filepath}")
        return errors

    # Check schema exists
    if not os.path.exists(schema_path):
        errors.append(f"Schema not found: {schema_path}")
        return errors

    # Load and check basic YAML syntax first
    try:
        with open(filepath) as f:
            data = yaml.safe_load(f)
        if data is None:
            errors.append(f"File is empty or contains only comments: {filepath}")
            return errors
    except yaml.YAMLError as e:
        errors.append(f"YAML syntax error in {filepath}: {e}")
        return errors

    # Run pykwalify schema validation
    try:
        c = pykwalify.core.Core(
            source_file=filepath,
            schema_files=[schema_path]
        )
        c.validate(raise_exception=True)
    except SchemaError as e:
        for err in e.errors:
            errors.append(f"Schema violation in {filepath}: {err}")

    return errors


def check_naming_convention(filepath: str) -> list[str]:
    """Check that intent files follow naming conventions."""
    errors = []
    path = Path(filepath)

    if "intents" not in path.parts:
        return errors

    # Intent files must match: <description>-<NNN>.yaml
    # e.g. fin-pci-connectivity-001.yaml
    import re
    if not re.match(r'^[a-z0-9-]+-\d{3}\.yaml$', path.name):
        errors.append(
            f"Intent filename '{path.name}' does not follow convention: "
            f"<description>-<NNN>.yaml (e.g. fin-pci-connectivity-001.yaml)"
        )

    # Intent ID in file must match filename
    try:
        with open(filepath) as f:
            data = yaml.safe_load(f)
        intent_id = data.get("intent", {}).get("id")
        expected_id = path.stem  # filename without .yaml
        if intent_id and intent_id != expected_id:
            errors.append(
                f"Intent ID '{intent_id}' in file does not match filename '{expected_id}'"
            )
    except Exception:
        pass  # YAML errors caught elsewhere

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate intent YAML schemas")
    parser.add_argument(
        "--changed-files",
        required=True,
        help="Space-separated list of changed files"
    )
    args = parser.parse_args()

    changed_files = args.changed_files.strip().split()

    if not changed_files:
        print("No YAML files changed — skipping schema validation")
        sys.exit(0)

    all_errors = []
    validated_count = 0
    skipped_count = 0

    for filepath in changed_files:
        # Skip deleted files
        if not os.path.exists(filepath):
            print(f"  ⏭️  Skipped (deleted): {filepath}")
            skipped_count += 1
            continue

        # Skip auto-generated rendered/ files
        if "rendered/" in filepath:
            print(f"  ⏭️  Skipped (rendered): {filepath}")
            skipped_count += 1
            continue

        schema_path = get_schema_for_file(filepath)

        if schema_path is None:
            print(f"  ⏭️  No schema for: {filepath}")
            skipped_count += 1
            continue

        print(f"  🔍 Validating: {filepath}")

        # Schema validation
        errors = validate_file(filepath, schema_path)

        # Naming convention check
        errors += check_naming_convention(filepath)

        if errors:
            for err in errors:
                print(f"     ❌ {err}")
            all_errors.extend(errors)
        else:
            print(f"     ✅ Valid")

        validated_count += 1

    print(f"\n{'─'*60}")
    print(f"Validated: {validated_count}  Skipped: {skipped_count}  Errors: {len(all_errors)}")

    if all_errors:
        print("\n❌ Schema validation FAILED")
        sys.exit(1)
    else:
        print("\n✅ Schema validation PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
