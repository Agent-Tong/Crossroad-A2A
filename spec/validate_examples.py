#!/usr/bin/env python3
"""Validate spec/examples/*.json against spec/*.schema.json. Standard library only. Read-only.

Usage:   python3 -I -B spec/validate_examples.py          (exit 0 = every example valid and every bad variant rejected)

This is a small validator for the subset of JSON Schema (draft 2020-12) that the schemas in this folder use:
type (string or list), enum, const, pattern, minLength, maxLength, minimum, maximum, minItems, required,
properties, additionalProperties false, items. It is not a full validator; use a full one in your own project.

Length note: JSON Schema maxLength counts CHARACTERS. The bridge's answer cap is 8000 UTF-8 BYTES. The schema alone cannot
prove the byte cap, and this file does not claim it does. The byte cap is an application check (see byte_cap_ok below and the
reference ports); the last checks in main() show a text that passes the schema's character check and fails the byte check.
"""
import copy
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAIRS = [("letter", "letter"), ("answer", "answer"), ("island", "island"), ("member", "member"), ("policy", "policy")]


def type_ok(value, name):
    if name == "string":
        return isinstance(value, str)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "null":
        return value is None
    if name == "object":
        return isinstance(value, dict)
    if name == "array":
        return isinstance(value, list)
    raise ValueError("unsupported type " + name)


def check(value, schema, path="$"):
    errors = []
    if "type" in schema:
        names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(type_ok(value, n) for n in names):
            return ["%s: wrong type" % path]
    if "const" in schema and value != schema["const"]:
        errors.append("%s: not the constant" % path)
    if "enum" in schema and value not in schema["enum"]:
        errors.append("%s: not in enum" % path)
    if isinstance(value, str):
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append("%s: pattern" % path)
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append("%s: too short" % path)
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append("%s: too long" % path)
    if isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append("%s: below minimum" % path)
        if "maximum" in schema and value > schema["maximum"]:
            errors.append("%s: above maximum" % path)
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append("%s: missing %s" % (path, key))
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append("%s: unexpected %s" % (path, key))
        for key, sub in props.items():
            if key in value:
                errors.extend(check(value[key], sub, path + "." + key))
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append("%s: too few items" % path)
        if "items" in schema:
            for index, item in enumerate(value):
                errors.extend(check(item, schema["items"], "%s[%d]" % (path, index)))
    return errors


ANSWER_BODY_MAX_BYTES = 8000


def byte_cap_ok(text, limit=ANSWER_BODY_MAX_BYTES):
    """Application-level check for the byte cap. The schema's maxLength cannot express this."""
    return len(text.encode("utf-8")) <= limit


def load(name):
    with open(os.path.join(HERE, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


def main():
    failed = 0
    for example, schema_name in PAIRS:
        schema = load(schema_name + ".schema.json")
        value = load(os.path.join("examples", example + ".json"))
        errors = check(value, schema)
        print("%-8s valid example   : %s" % (example, "OK" if not errors else "FAIL " + "; ".join(errors)))
        failed += bool(errors)
        bad = copy.deepcopy(value)
        bad["unexpected_field"] = 1                     # every schema forbids extra fields
        rejected = bool(check(bad, schema))
        print("%-8s bad variant     : %s" % (example, "rejected OK" if rejected else "FAIL accepted"))
        failed += not rejected
    # two targeted bad variants
    letter = load("letter.schema.json")
    sample = load(os.path.join("examples", "letter.json"))
    sample["call_id"] = "not-a-call-id"
    rejected = bool(check(sample, letter))
    print("letter   bad call_id     : %s" % ("rejected OK" if rejected else "FAIL accepted"))
    failed += not rejected
    answer = load("answer.schema.json")
    sample = load(os.path.join("examples", "answer.json"))
    sample["purpose"] = "queue_task"
    rejected = bool(check(sample, answer))
    print("answer   wrong purpose   : %s" % ("rejected OK" if rejected else "FAIL accepted"))
    failed += not rejected
    # byte cap: the schema checks characters only; the application checks bytes
    body_schema = answer["properties"]["body"]
    for label, text, want_schema, want_bytes in (
        ("8000 ASCII chars (8000 bytes)", "a" * 8000, True, True),
        ("4000 two-byte chars (8000 bytes)", "\u00e9" * 4000, True, True),
        ("4001 two-byte chars (8002 bytes)", "\u00e9" * 4001, True, False),
    ):
        schema_ok = not check(text, body_schema)
        bytes_ok = byte_cap_ok(text)
        good = (schema_ok == want_schema) and (bytes_ok == want_bytes)
        print("answer   %-34s: schema(chars)=%s bytes=%s %s" % (label, "pass" if schema_ok else "fail", "pass" if bytes_ok else "fail", "OK" if good else "FAIL"))
        failed += not good
    print("RESULT: %s" % ("all checks passed" if not failed else "%d check(s) failed" % failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
