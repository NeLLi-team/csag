#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml
from linkml.generators.jsonschemagen import JsonSchemaGenerator
from linkml_runtime.utils.schemaview import SchemaView


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_YAML = ROOT / "skills/csag-extraction/assets/csag.yaml"
JSON_OUT_DIR = SCHEMA_YAML.parent
OUT_DIR = ROOT / "schema"


def build_json_schema(*, top_class: str, schema_id: str) -> dict:
    generated = JsonSchemaGenerator(
        SCHEMA_YAML,
        top_class=top_class,
        not_closed=False,
        preserve_names=True,
    ).serialize()
    payload = json.loads(generated)
    payload["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    payload["$id"] = schema_id
    return payload


def build_markdown(schema: dict) -> str:
    schema_view = SchemaView(SCHEMA_YAML)
    lines = [
        "# CSAG schema reference",
        "",
        f"Authoritative source: `{SCHEMA_YAML.relative_to(ROOT)}`.",
        "",
        "## Controlled vocabularies",
        "",
    ]
    for enum_name, enum_def in sorted((schema.get("enums") or {}).items()):
        values = ", ".join(f"`{value}`" for value in sorted((enum_def.get("permissible_values") or {}).keys()))
        lines.append(f"### {enum_name}")
        lines.append("")
        lines.append(enum_def.get("description", "").strip())
        lines.append("")
        lines.append(f"Values: {values}")
        lines.append("")

    lines.append("## Classes")
    lines.append("")
    for class_name, class_def in sorted((schema.get("classes") or {}).items()):
        lines.append(f"### {class_name}")
        lines.append("")
        description = " ".join(class_def.get("description", "").split())
        if description:
            lines.append(description)
            lines.append("")
        class_slots = schema_view.class_induced_slots(class_name)
        if class_slots:
            lines.append("| Slot | Range | Cardinality | Description |")
            lines.append("|------|-------|-------------|-------------|")
            for slot in class_slots:
                slot_name = str(slot.name)
                cardinality = "many" if slot.multivalued else "one"
                if slot.required or slot.identifier or (slot.minimum_cardinality or 0) >= 1:
                    cardinality += ", required"
                slot_desc = " ".join((slot.description or "").split())
                lines.append(f"| `{slot_name}` | `{slot.range or 'string'}` | {cardinality} | {slot_desc} |")
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate derived CSAG schema artifacts.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Write every artifact to this directory (default: JSON Schema next to csag.yaml, Markdown to schema/).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    schema = yaml.safe_load(SCHEMA_YAML.read_text(encoding="utf-8"))
    out_dir = args.out_dir.expanduser().resolve() if args.out_dir else None
    json_dir = out_dir or JSON_OUT_DIR
    md_dir = out_dir or OUT_DIR
    json_dir.mkdir(parents=True, exist_ok=True)
    md_dir.mkdir(parents=True, exist_ok=True)
    (json_dir / "csag.schema.json").write_text(
        json.dumps(
            build_json_schema(
                top_class="PaperExtraction",
                schema_id="https://w3id.org/csag/schema/csag.schema.json",
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (json_dir / "csag.handoff.schema.json").write_text(
        json.dumps(
            build_json_schema(
                top_class="HandoffEnvelope",
                schema_id="https://w3id.org/csag/schema/csag.handoff.schema.json",
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (md_dir / "csag.md").write_text(build_markdown(schema), encoding="utf-8")
    (md_dir / "README.md").write_text(
        "# Schema artifacts\n\n"
        "The authoritative CSAG schema is the LinkML (Linked Data Modeling Language)\n"
        "source `skills/csag-extraction/assets/csag.yaml`.\n\n"
        "This directory contains generated files:\n\n"
        "- `csag.md`: Markdown reference of the controlled vocabularies and classes.\n"
        "- `README.md`: this file.\n\n"
        "The generated JSON Schema files sit next to the LinkML source in\n"
        "`skills/csag-extraction/assets/`:\n\n"
        "- `csag.schema.json`: closed JSON Schema for `PaperExtraction`.\n"
        "- `csag.handoff.schema.json`: closed JSON Schema for `HandoffEnvelope`.\n\n"
        "Regenerate every generated file with:\n\n"
        "```bash\nuv run python scripts/generate_schema_artifacts.py\n```\n\n"
        "Check that the committed files match the generator with:\n\n"
        "```bash\nuv run python scripts/check_schema_artifacts.py\n```\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
