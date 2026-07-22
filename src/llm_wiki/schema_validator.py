"""
schema_validator.py — Python validator for JSON Schema wiki artifacts.

Loads JSON Schema files from schema/versions/v0.2.1/ and validates
documents against them. Used by CLI commands, tests, and cross-language CI.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_DIR = REPO_ROOT / "schema" / "versions" / "v0.2.1"

_REQUIRED_FRONTMATTER = frozenset({"title", "type", "created", "updated", "sources", "tags"})
_VALID_TYPES = frozenset({"entity", "concept", "source", "comparison", "synthesis", "overview"})
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _load_schema(name: str) -> dict:
    path = SCHEMA_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Schema not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_with_jsonschema(instance: dict, schema_name: str) -> list[str]:
    """Validate an instance against a JSON Schema using jsonschema if available."""
    try:
        import jsonschema
        schema = _load_schema(schema_name)
        validator = jsonschema.Draft7Validator(schema)
        errors = list(validator.iter_errors(instance))
        return [_format_error(e) for e in errors]
    except ImportError:
        return []


def _format_error(error) -> str:
    path = " → ".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
    return f"{path}: {error.message}"


def validate_page(data: dict) -> list[str]:
    """Validate a page frontmatter dict. Returns list of error messages (empty = valid)."""
    errors = []

    for field in _REQUIRED_FRONTMATTER:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")

    val_type = data.get("type")
    if val_type is not None and val_type not in _VALID_TYPES:
        errors.append(f"Invalid type '{val_type}': must be one of {sorted(_VALID_TYPES)}")

    for date_field in ("created", "updated"):
        val = data.get(date_field)
        if val is not None and not _DATE_RE.match(str(val)):
            errors.append(f"Field '{date_field}' must be YYYY-MM-DD, got '{val}'")

    for list_field in ("sources", "tags"):
        val = data.get(list_field)
        if val is not None and not isinstance(val, list):
            errors.append(f"Field '{list_field}' must be a list, got {type(val).__name__}")

    confidence = data.get("confidence")
    if confidence is not None and confidence not in ("high", "medium", "low"):
        errors.append(f"Invalid confidence '{confidence}': must be 'high', 'medium', or 'low'")

    contested = data.get("contested")
    if contested is not None and not isinstance(contested, bool):
        errors.append(f"Field 'contested' must be boolean, got {type(contested).__name__}")

    contradictions = data.get("contradictions")
    if contradictions is not None and not isinstance(contradictions, list):
        errors.append(f"Field 'contradictions' must be a list, got {type(contradictions).__name__}")

    jsonschema_errors = _validate_with_jsonschema(data, "page.schema.json")
    errors.extend(jsonschema_errors)

    return errors


def validate_audit(data: dict) -> list[str]:
    """Validate an audit entry dict. Returns list of error messages (empty = valid)."""
    errors = []
    required = {"id", "target", "severity", "author", "source", "created", "status"}
    for field in required:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")

    has_anchors = all(k in data for k in ("target_lines", "anchor_before", "anchor_text", "anchor_after"))
    is_unanchored = all(k in data for k in ("target_kind", "target_reason"))

    if not has_anchors and not is_unanchored:
        errors.append("Audit must have either anchor fields (target_lines, anchor_before, anchor_text, anchor_after) or unanchored kind (target_kind, target_reason)")

    sev = data.get("severity")
    if sev is not None and sev not in ("info", "suggest", "warn", "error"):
        errors.append(f"Invalid severity '{sev}'")

    status = data.get("status")
    if status is not None and status not in ("open", "resolved"):
        errors.append(f"Invalid status '{status}'")

    aid = data.get("id")
    if aid is not None:
        import re
        if not re.match(r"^\d{8}-\d{6}-[0-9a-f]{4}$", str(aid)):
            errors.append(f"Invalid id format '{aid}': must match YYYYMMDD-HHMMSS-XXXX")

    jsonschema_errors = _validate_with_jsonschema(data, "audit.schema.json")
    errors.extend(jsonschema_errors)

    return errors


def validate_log_event(data: dict) -> list[str]:
    """Validate a log event dict. Returns list of error messages (empty = valid)."""
    errors = []
    required = {"v", "ts", "lvl", "cmp", "msg"}
    for field in required:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")

    if data.get("v") != 1:
        errors.append(f"Log format version must be 1, got {data.get('v')}")

    lvl = data.get("lvl")
    valid_levels = {"DEBUG", "INFO", "WARN", "ERROR", "PANIC"}
    if lvl is not None and lvl not in valid_levels:
        errors.append(f"Invalid level '{lvl}': must be one of {sorted(valid_levels)}")

    jsonschema_errors = _validate_with_jsonschema(data, "log-event.schema.json")
    errors.extend(jsonschema_errors)

    return errors


def validate_template(data: dict) -> list[str]:
    """Validate a template metadata dict. Returns list of error messages (empty = valid)."""
    errors = []
    required = {"name", "description"}
    for field in required:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")

    jsonschema_errors = _validate_with_jsonschema(data, "template-schema.schema.json")
    errors.extend(jsonschema_errors)

    return errors


def validate_operation_manifest(data: dict) -> list[str]:
    """Validate an operation manifest dict."""
    errors = []
    required = {"operation_id", "command", "status", "started_at"}
    for field in required:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")

    jsonschema_errors = _validate_with_jsonschema(data, "operation-manifest.schema.json")
    errors.extend(jsonschema_errors)

    return errors


def validate_claim(data: dict) -> list[str]:
    """Validate a claim record dict."""
    errors = []
    required = {"claim_id", "statement", "confidence", "status"}
    for field in required:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")

    status = data.get("status")
    if status is not None and status not in ("active", "contested", "superseded", "resolved", "retracted", "stale"):
        errors.append(f"Invalid status '{status}'")

    confidence = data.get("confidence")
    if confidence is not None and confidence not in ("high", "medium", "low"):
        errors.append(f"Invalid confidence '{confidence}'")

    jsonschema_errors = _validate_with_jsonschema(data, "claim-sidecar.schema.json")
    if jsonschema_errors:
        errors.extend(jsonschema_errors)

    return errors


def validate_epistemic_event(data: dict) -> list[str]:
    """Validate an epistemic event record dict."""
    errors = []
    required = {"claim_id", "event_type", "source", "timestamp"}
    for field in required:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")

    et = data.get("event_type")
    valid_events = {"created", "reinforced", "challenged", "weakened", "superseded", "resolved", "retracted"}
    if et is not None and et not in valid_events:
        errors.append(f"Invalid event_type '{et}'")

    return errors


def validate_contradiction(data: dict) -> list[str]:
    """Validate a contradiction record dict."""
    errors = []
    required = {"contradiction_id", "claim_ids", "status", "severity"}
    for field in required:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")

    cids = data.get("claim_ids")
    if cids is not None and not isinstance(cids, list):
        errors.append("'claim_ids' must be a list")
    if cids is not None and isinstance(cids, list) and len(cids) < 1:
        errors.append("'claim_ids' must have at least 1 entry")

    sev = data.get("severity")
    if sev is not None and sev not in ("low", "medium", "high", "blocking"):
        errors.append(f"Invalid severity '{sev}'")

    status = data.get("status")
    if status is not None and status not in ("open", "investigating", "resolved", "false_positive", "wont_fix"):
        errors.append(f"Invalid status '{status}'")

    return errors


def validate_fixture_file(file_path: str) -> dict:
    """Validate a JSON fixture file against its expected schema based on filename patterns."""
    path = Path(file_path)
    name = path.stem
    errors = []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"file": str(path), "valid": False, "errors": [f"Invalid JSON: {e}"]}

    if "page" in name or name in ("full-page", "minimal-page"):
        errors = validate_page(data)
    elif "audit" in name:
        errors = validate_audit(data)
    elif "log" in name:
        errors = validate_log_event(data)
    elif "template" in name:
        errors = validate_template(data)
    elif "manifest" in name:
        errors = validate_operation_manifest(data)
    elif "epistemic" in name:
        errors = validate_epistemic_event(data)
    elif "claim" in name:
        errors = validate_claim(data)
    elif "contradiction" in name:
        errors = validate_contradiction(data)
    else:
        return {"file": str(path), "valid": True, "errors": [], "skipped": True}

    return {"file": str(path), "valid": len(errors) == 0, "errors": errors}


def validate_fixture_dir(directory: str) -> list[dict]:
    """Validate all JSON fixture files in a directory."""
    results = []
    for f in sorted(Path(directory).glob("*.json")):
        results.append(validate_fixture_file(str(f)))
    return results


def parse_page_frontmatter(text: str) -> dict | None:
    """Parse YAML frontmatter from a wiki page markdown file."""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return None
    body = m.group(1)
    result = {}
    for line in body.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            result[key] = [x.strip().strip("\"'") for x in inner.split(",") if x.strip()] if inner else []
        elif val.startswith(('"', "'")):
            result[key] = val[1:-1]
        elif val.lower() in ("true", "false"):
            result[key] = val.lower() == "true"
        elif val.lower() in ("none", "null"):
            result[key] = None
        else:
            result[key] = val
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Schema validator for LLM Wiki artifacts")
    parser.add_argument("--schema", help="Path to JSON schema file")
    parser.add_argument("files", nargs="*", help="Files to validate")
    args = parser.parse_args()

    if not args.files:
        print("Usage: schema_validator.py <file> [file...]", file=sys.stderr)
        return 1

    all_errors = []
    for f in args.files:
        result = validate_fixture_file(f)
        if result.get("skipped"):
            print(f"⚠  Skipped (unknown type): {f}")
        elif result["valid"]:
            print(f"✓  Valid: {f}")
        else:
            print(f"✗  Invalid: {f}")
            for e in result["errors"]:
                print(f"    - {e}")
            all_errors.append(f)

    return 1 if all_errors else 0


if __name__ == "__main__":
    sys.exit(main())
