#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "skills/csag-extraction/assets/csag.yaml"
DOC_PATH = ROOT / "schema/csag.md"

EXPECTED_SLOT_ENUMS = {
    "polarity": "Polarity",
    "strength": "StrengthLevel",
    "criticality": "AssertionCriticality",
    "normalization_status": "NormalizationStatus",
    "curation_status": "CurationStatus",
    "claim_role": "ClaimRole",
    "assertion_type": "AssertionType",
    "critique_type": "ThreatToValidityType",
    "risk_domain": "RiskOfBiasDomain",
    "gap_type": "GapType",
}


def main() -> int:
    schema = yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))
    slots = schema.get("slots", {}) or {}
    enums = schema.get("enums", {}) or {}
    docs = DOC_PATH.read_text(encoding="utf-8") if DOC_PATH.exists() else ""

    errors: list[str] = []
    for slot_name, enum_name in EXPECTED_SLOT_ENUMS.items():
        slot = slots.get(slot_name)
        if not isinstance(slot, dict):
            errors.append(f"slot missing: {slot_name}")
            continue
        actual_range = slot.get("range")
        if actual_range != enum_name:
            errors.append(f"slot {slot_name} range is {actual_range!r}, expected {enum_name!r}")
        enum = enums.get(enum_name)
        if not isinstance(enum, dict):
            errors.append(f"enum missing: {enum_name}")
            continue
        values = enum.get("permissible_values", {}) or {}
        if not values:
            errors.append(f"enum has no permissible values: {enum_name}")
        if f"### {enum_name}" not in docs:
            errors.append(f"enum missing from generated docs: {enum_name}")
        for value in values:
            if f"`{value}`" not in docs:
                errors.append(f"enum value missing from generated docs: {enum_name}.{value}")

    report = {
        "ok": not errors,
        "checked": EXPECTED_SLOT_ENUMS,
        "errors": errors,
    }
    print(json.dumps(report, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
