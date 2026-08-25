from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from rdflib import Graph

from .paths import CommandResult, ROOT
from .provenance import check_report_inputs, sha256_file


EXPORT_FIDELITY = {
    "json": {"level": "lossless", "description": "Canonical CSAG artifact."},
    "ro-crate": {"level": "lossless_bundle", "description": "Byte-identical included files with SHA-256 hashes."},
    "jsonld": {"level": "lossy_projection", "description": "Semantic graph projection; canonical JSON remains authoritative."},
    "rdf": {"level": "lossy_projection", "description": "Turtle serialization of the JSON-LD semantic projection."},
    "graphml": {"level": "lossy_view", "description": "Selected graph nodes and edges for analysis."},
    "table": {"level": "lossy_view", "description": "Assertion/evidence table for analysis."},
}

FIELD_TYPES = {
    "documents": "PaperExtraction",
    "authors": "Author",
    "extraction_activities": "ExtractionActivity",
    "artifacts": "Artifact",
    "datasets": "Dataset",
    "entities": "Entity",
    "ontology_annotations": "OntologyAnnotation",
    "mentions": "EntityMention",
    "studies": "Study",
    "study_contexts": "Context",
    "experiments": "Experiment",
    "variables": "Variable",
    "assertions": "Assertion",
    "contexts": "Context",
    "conditions": "Condition",
    "qualifiers": "Qualifier",
    "additional_context_qualifiers": "Qualifier",
    "evidence_items": "EvidenceItem",
    "results": "Result",
    "referenced_works": "Reference",
    "evidence_links": "EvidenceLink",
    "inferences": "InferenceStep",
    "assertion_relations": "AssertionRelation",
    "critiques": "StudyCritique",
    "knowledge_gaps": "KnowledgeGap",
    "qa_items": "QAItem",
    "answers": "Answer",
    "research_states": "ResearchStateRecord",
    "next_actions": "NextAction",
    "executions": "Execution",
    "text_spans": "TextSpan",
    "mention_span": "TextSpan",
    "provenance": "ProvenanceRecord",
    "parameters": "KeyValue",
}

REFERENCE_FIELDS = {
    "created_by",
    "contexts",
    "generated_by",
    "derived_from",
    "document_id",
    "artifact_ref",
    "dataset_url",
    "dataset_license",
    "full_text_url",
    "license",
    "url",
    "xrefs",
    "term_id",
    "evidence_code",
    "entity_ref",
    "organism",
    "cell_type",
    "tissue",
    "disease_state",
    "strain",
    "entity_involved",
    "variable_entity",
    "subject",
    "predicate",
    "object",
    "asserted_in_study",
    "associated_experiment",
    "associated_artifacts",
    "associated_datasets",
    "dataset_ref",
    "evidence_item",
    "assertion",
    "supporting_assertions",
    "supporting_evidence_links",
    "query_assertion",
    "answer_entity",
    "input_assertions",
    "input_evidence_links",
    "output_assertion",
    "outcome",
    "assumptions",
    "from_assertion",
    "to_assertion",
    "related_work",
    "impacted_assertions",
    "impacted_evidence_items",
    "related_assertions",
    "target_assertions",
    "target_knowledge_gaps",
    "agent_uri",
    "recommended_next_actions",
    "output_artifacts",
    "generated_evidence_items",
    "tested_assertions",
}


def load_extraction(path: Path) -> dict:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def _clean(value: object) -> str:
    return str(value or "").replace("\t", " ").replace("\n", " ")


def build_jsonld(extraction: dict) -> dict:
    context: dict[str, object] = {
        "@vocab": "https://w3id.org/csag/",
        "csag": "https://w3id.org/csag/",
        "schema": "https://schema.org/",
        "id": "@id",
        "type": "@type",
    }
    context.update({field: {"@type": "@id"} for field in sorted(REFERENCE_FIELDS)})

    def convert(value: object, field: str | None = None, class_name: str | None = None) -> object:
        if isinstance(value, list):
            return [convert(item, field, FIELD_TYPES.get(field or "")) for item in value]
        if not isinstance(value, dict):
            return value
        node: dict[str, object] = {}
        if isinstance(value.get("id"), str):
            node["@id"] = value["id"]
        node_type = class_name or FIELD_TYPES.get(field or "")
        if node_type:
            node["@type"] = f"csag:{node_type}"
        for key, nested in value.items():
            if key == "id":
                continue
            node[key] = convert(nested, key, FIELD_TYPES.get(key))
        return node

    payload = convert(extraction, class_name="PaperExtraction")
    assert isinstance(payload, dict)
    payload = {"@context": context, **payload}
    return payload


def write_jsonld(extraction: dict, output: Path) -> None:
    payload = build_jsonld(extraction)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _node_label(item: dict, *fields: str, fallback: str) -> str:
    for field in fields:
        value = item.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _collect_context_objects(extraction: dict) -> dict[str, dict]:
    """Map context id -> context dict from every ``contexts`` list in the extraction."""
    out: dict[str, dict] = {}

    def consume(contexts: object) -> None:
        if isinstance(contexts, list):
            for context in contexts:
                if isinstance(context, dict) and isinstance(context.get("id"), str):
                    out.setdefault(context["id"], context)

    def walk(value: object) -> None:
        if isinstance(value, dict):
            consume(value.get("contexts"))
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    consume(extraction.get("contexts"))
    walk(extraction)
    return out


def _context_refs(item: dict, context_map: dict[str, dict]) -> list[tuple[str, dict]]:
    """Return (id, context_dict) for each context reference, resolving string refs."""
    refs: list[tuple[str, dict]] = []
    for context in item.get("contexts") or []:
        if isinstance(context, dict) and context.get("id"):
            refs.append((context["id"], context))
        elif isinstance(context, str) and context:
            refs.append((context, context_map.get(context, {"id": context})))
    return refs


def _refs(value: object) -> list[str]:
    if isinstance(value, str) and value:
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


def write_graphml(extraction: dict, output: Path) -> None:
    nodes: dict[str, dict[str, str]] = {}
    edges: list[dict[str, str]] = []
    context_map = _collect_context_objects(extraction)

    def add_node(node_id: str | None, klass: str, label: str, **attrs: str) -> None:
        if not node_id:
            return
        current = nodes.setdefault(node_id, {"class": klass, "label": label})
        current.update({key: value for key, value in attrs.items() if value})

    def add_edge(edge_id: str, source: str | None, target: str | None, relation: str, **attrs: str) -> None:
        if not source or not target:
            return
        edges.append({"id": edge_id, "source": source, "target": target, "relation": relation, **{k: v for k, v in attrs.items() if v}})

    for assertion in extraction.get("assertions", []) or []:
        if not isinstance(assertion, dict):
            continue
        aid = assertion.get("id")
        add_node(aid, "Assertion", _node_label(assertion, "assertion_text", fallback="Assertion"), claim_role=str(assertion.get("claim_role") or ""), criticality=str(assertion.get("criticality") or ""))
        for cid, context in _context_refs(assertion, context_map):
            add_node(cid, "Context", _node_label(context, "label", "context_facet", fallback="Context"))
            add_edge(f"{aid}->ctx:{cid}", aid, cid, "scoped_by")

    for evidence in extraction.get("evidence_items", []) or []:
        if not isinstance(evidence, dict):
            continue
        eid = evidence.get("id")
        add_node(eid, "EvidenceItem", _node_label(evidence, "evidence_text", "evidence_type", fallback="EvidenceItem"))
        for cid, context in _context_refs(evidence, context_map):
            add_node(cid, "Context", _node_label(context, "label", "context_facet", fallback="Context"))
            add_edge(f"{eid}->ctx:{cid}", eid, cid, "scoped_by")
        for artifact_id in _refs(evidence.get("associated_artifacts")) + _refs(evidence.get("artifact_ref")):
            add_edge(f"{eid}->artifact:{artifact_id}", eid, artifact_id, "uses_artifact")
        for dataset_id in _refs(evidence.get("associated_datasets")) + _refs(evidence.get("dataset_ref")):
            add_edge(f"{eid}->dataset:{dataset_id}", eid, dataset_id, "uses_dataset")

    for link in extraction.get("evidence_links", []) or []:
        if not isinstance(link, dict):
            continue
        source = link.get("evidence_item")
        target = link.get("assertion")
        add_edge(str(link.get("id") or f"{source}->{target}"), source, target, "evidence_link", polarity=str(link.get("polarity") or ""), strength=str(link.get("strength") or ""))

    for item, klass, fields in [
        ("critiques", "StudyCritique", ("critique_type", "risk_domain", "id")),
        ("knowledge_gaps", "KnowledgeGap", ("gap_statement", "gap_type", "id")),
        ("artifacts", "Artifact", ("artifact_label", "caption", "id")),
        ("datasets", "Dataset", ("label", "accession", "repository", "dataset_url", "id")),
    ]:
        for obj in extraction.get(item, []) or []:
            if not isinstance(obj, dict):
                continue
            oid = obj.get("id")
            add_node(oid, klass, _node_label(obj, *fields, fallback=klass))
            if item == "critiques":
                for aid in _refs(obj.get("impacted_assertions")):
                    add_edge(f"{oid}->assertion:{aid}", oid, aid, "impacts")
            if item == "knowledge_gaps":
                for aid in _refs(obj.get("related_assertions")):
                    add_edge(f"{oid}->assertion:{aid}", oid, aid, "related_to")

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        '<key id="class" for="node" attr.name="class" attr.type="string"/>',
        '<key id="label" for="node" attr.name="label" attr.type="string"/>',
        '<key id="claim_role" for="node" attr.name="claim_role" attr.type="string"/>',
        '<key id="criticality" for="node" attr.name="criticality" attr.type="string"/>',
        '<key id="relation" for="edge" attr.name="relation" attr.type="string"/>',
        '<key id="polarity" for="edge" attr.name="polarity" attr.type="string"/>',
        '<key id="strength" for="edge" attr.name="strength" attr.type="string"/>',
        '<graph edgedefault="directed">',
    ]
    for node_id in sorted(nodes):
        attrs = nodes[node_id]
        data = "".join(
            f"<data key={quoteattr(key)}>{escape(str(value))}</data>"
            for key, value in sorted(attrs.items())
        )
        lines.append(f"<node id={quoteattr(node_id)}>{data}</node>")
    for edge in sorted(edges, key=lambda row: (row["id"], row["source"], row["target"])):
        data = "".join(
            f"<data key={quoteattr(key)}>{escape(str(value))}</data>"
            for key, value in sorted(edge.items())
            if key not in {"id", "source", "target"}
        )
        lines.append(
            f"<edge id={quoteattr(edge['id'])} source={quoteattr(edge['source'])} "
            f"target={quoteattr(edge['target'])}>{data}</edge>"
        )
    lines.extend(["</graph>", "</graphml>"])
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_table(extraction: dict, output: Path) -> None:
    evidence_by_id = {item.get("id"): item for item in extraction.get("evidence_items", []) or [] if isinstance(item, dict) and item.get("id")}
    links_by_assertion: dict[str, list[dict]] = {}
    for link in extraction.get("evidence_links", []) or []:
        if isinstance(link, dict) and link.get("assertion"):
            links_by_assertion.setdefault(link["assertion"], []).append(link)
    header = [
        "assertion_id", "assertion_text", "claim_role", "criticality", "context_ids", "evidence_link_id", "evidence_item_id", "polarity", "strength", "evidence_text", "artifact_ids", "dataset_ids", "missing_evidence",
    ]
    context_map = _collect_context_objects(extraction)
    rows = ["\t".join(header)]
    for assertion in extraction.get("assertions", []) or []:
        if not isinstance(assertion, dict):
            continue
        assertion_id = assertion.get("id", "")
        context_ids = ";".join(cid for cid, _ in _context_refs(assertion, context_map))
        links = sorted(links_by_assertion.get(assertion_id, []), key=lambda item: item.get("id", ""))
        if not links:
            rows.append("\t".join(_clean(value) for value in [assertion_id, assertion.get("assertion_text", ""), assertion.get("claim_role", ""), assertion.get("criticality", ""), context_ids, "", "", "", "", "", "", "", "true"]))
            continue
        for link in links:
            evidence = evidence_by_id.get(link.get("evidence_item"), {})
            artifact_ids = ";".join(_refs(evidence.get("associated_artifacts")) + _refs(evidence.get("artifact_ref")))
            dataset_ids = ";".join(_refs(evidence.get("associated_datasets")) + _refs(evidence.get("dataset_ref")))
            rows.append("\t".join(_clean(value) for value in [assertion_id, assertion.get("assertion_text", ""), assertion.get("claim_role", ""), assertion.get("criticality", ""), context_ids, link.get("id", ""), link.get("evidence_item", ""), link.get("polarity", ""), link.get("strength", ""), evidence.get("evidence_text", ""), artifact_ids, dataset_ids, "false"]))
    output.write_text("\n".join(rows) + "\n", encoding="utf-8")


def write_turtle(extraction: dict, output: Path) -> None:
    graph = Graph()
    graph.parse(data=json.dumps(build_jsonld(extraction)), format="json-ld")
    serialized = graph.serialize(format="turtle")
    output.write_text(str(serialized), encoding="utf-8")


def write_ro_crate(extraction_path: Path, output: Path) -> None:
    if output.exists() and not output.is_dir():
        raise ValueError(f"RO-Crate output path is not a directory: {output}")
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"RO-Crate output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    extraction = load_extraction(extraction_path)
    source_dir = extraction_path.parent
    source_document = extraction.get("id", "")
    for report_name in (
        "paper_extraction.validation.json",
        "paper_extraction.quality.json",
        "paper_extraction.lint.json",
    ):
        report_path = source_dir / report_name
        if not report_path.exists():
            continue
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"cannot bundle invalid report {report_name}: {exc}") from exc
        fresh, stale = check_report_inputs(report_path, report)
        if not fresh:
            raise ValueError(f"cannot bundle stale report {report_name}: {stale}")
    candidates: list[tuple[Path, str, int]] = [
        (extraction_path, extraction_path.name, 0),
        (source_dir / "paper_extraction.validation.json", "paper_extraction.validation.json", 0),
        (source_dir / "paper_extraction.quality.json", "paper_extraction.quality.json", 0),
        (source_dir / "paper_extraction.lint.json", "paper_extraction.lint.json", 0),
        *[(path, path.name, 0) for path in sorted(source_dir.glob("*.md"))],
        *[(path, path.name, 0) for path in sorted(source_dir.glob("*.article.json"))],
        *[(path, path.name, 0) for path in sorted(source_dir.glob("*.section_audit.json"))],
    ]

    def supplement_matches(path: Path) -> bool:
        if path.parent == source_dir:
            return True
        for metadata_name in ("normalization_report.json", "example_entity_bundle.json"):
            metadata_path = path / metadata_name
            if not metadata_path.exists():
                continue
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if metadata.get("source_document") == source_document:
                return True
        return False

    # Lower precedence values win destination collisions. Source-adjacent
    # supplements are intentionally preferred over the repository fallback;
    # within the source directory, the canonical location wins over legacy
    # locations. Byte-identical duplicates are collapsed below.
    supplement_dirs = [
        (source_dir / "entity-normalization", 10),
        (source_dir / "entity_supplements", 11),
        (source_dir / "supplementary" / "entity-normalization", 12),
        (ROOT / "supplementary" / "entity-normalization", 100),
    ]
    for supplement_dir, precedence in supplement_dirs:
        if not supplement_dir.exists() or not supplement_dir.is_dir() or not supplement_matches(supplement_dir):
            continue
        for path in sorted(item for item in supplement_dir.rglob("*") if item.is_file()):
            crate_name = str(Path("entity-normalization") / path.relative_to(supplement_dir))
            candidates.append((path, crate_name, precedence))

    # Resolve by destination rather than source path: RO-Crate requires one
    # metadata node and one payload per @id. A nearer source may supersede a
    # lower-priority fallback, but two distinct candidates at the same policy
    # level are ambiguous and therefore fail explicitly.
    selected: dict[str, tuple[Path, int, str]] = {}
    for path, crate_name, precedence in candidates:
        resolved = path.resolve()
        if not resolved.exists() or not resolved.is_file():
            continue
        digest = sha256_file(resolved)
        existing = selected.get(crate_name)
        if existing is None:
            selected[crate_name] = (resolved, precedence, digest)
            continue
        existing_path, existing_precedence, existing_digest = existing
        if existing_digest == digest:
            continue
        if precedence < existing_precedence:
            selected[crate_name] = (resolved, precedence, digest)
            continue
        if precedence > existing_precedence:
            continue
        raise ValueError(
            "RO-Crate destination collision for "
            f"{crate_name}: {existing_path} and {resolved} contain different bytes"
        )

    files = [
        (path, crate_name)
        for crate_name, (path, _precedence, _digest) in selected.items()
    ]
    has_part = []
    file_nodes = []
    for path, crate_name in files:
        crate_path = output / crate_name
        crate_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, crate_path)
        has_part.append({"@id": crate_name})
        node = {"@id": crate_name, "@type": "File"}
        node["contentSize"] = crate_path.stat().st_size
        node["sha256"] = sha256_file(crate_path)
        if crate_name.endswith(".json"):
            node["encodingFormat"] = "application/json"
        elif crate_name.endswith(".md"):
            node["encodingFormat"] = "text/markdown"
        elif crate_name.endswith(".tsv"):
            node["encodingFormat"] = "text/tab-separated-values"
        elif crate_name.endswith((".yaml", ".yml")):
            node["encodingFormat"] = "application/x-yaml"
        file_nodes.append(node)
    activity_nodes = []
    for activity in extraction.get("extraction_activities", []) or []:
        activity_id = activity.get("id")
        if activity_id:
            activity_nodes.append({"@id": activity_id, "@type": "CreateAction", "name": activity.get("activity_type", "extraction activity"), "instrument": activity.get("tool_name", ""), "startTime": activity.get("run_datetime", "")})
    execution_nodes = []
    for execution in extraction.get("executions", []) or []:
        execution_id = execution.get("id")
        if not execution_id:
            continue
        node = {
            "@id": execution_id,
            "@type": "CreateAction",
            "name": execution.get("execution_type", "research execution"),
            "actionStatus": execution.get("execution_status", ""),
            "startTime": execution.get("started_on", ""),
            "endTime": execution.get("completed_on", ""),
            "result": [{"@id": item} for item in execution.get("output_artifacts", []) or []],
        }
        execution_nodes.append(node)

    validation_profile = ""
    validation_report = source_dir / "paper_extraction.validation.json"
    if validation_report.exists():
        try:
            validation_profile = str(json.loads(validation_report.read_text(encoding="utf-8")).get("profile") or "")
        except json.JSONDecodeError:
            validation_profile = ""

    mentioned = [*activity_nodes, *execution_nodes]
    metadata = {
        "@context": [
            "https://w3id.org/ro/crate/1.1/context",
            {"csag": "https://w3id.org/csag/", "sha256": "csag:sha256"},
        ],
        "@graph": [
            {
                "@id": "./",
                "@type": "Dataset",
                "name": extraction.get("title", extraction_path.stem),
                "datePublished": datetime.now(timezone.utc).date().isoformat(),
                "identifier": source_document,
                "hasPart": has_part,
                "csag:schemaVersion": extraction.get("schema_version", ""),
                "csag:validatorVersion": extraction.get("validator_version", ""),
                "csag:validationProfile": validation_profile,
                "csag:bundleFidelity": "lossless-included-files",
                "mentions": [{"@id": item["@id"]} for item in mentioned],
            },
            {
                "@id": "ro-crate-metadata.json",
                "@type": "CreativeWork",
                "about": {"@id": "./"},
                "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
            },
            *file_nodes,
            *activity_nodes,
            *execution_nodes,
        ],
    }
    (output / "ro-crate-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def export_extraction(extraction_json: Path, *, format: str, output: Path) -> CommandResult:
    try:
        extraction_path = extraction_json.expanduser().resolve()
        extraction = load_extraction(extraction_path)
        output = output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        if format == "json":
            output.write_text(json.dumps(extraction, indent=2) + "\n", encoding="utf-8")
        elif format == "jsonld":
            write_jsonld(extraction, output)
        elif format == "graphml":
            write_graphml(extraction, output)
        elif format == "table":
            write_table(extraction, output)
        elif format == "rdf":
            write_turtle(extraction, output)
        elif format == "ro-crate":
            write_ro_crate(extraction_path, output)
        else:
            return CommandResult(False, 2, stderr=f"unknown export format: {format}\n")
        fidelity = EXPORT_FIDELITY[format]
        return CommandResult(
            True,
            0,
            report_path=output,
            data={"format": format, "fidelity": fidelity},
            stdout=f"wrote {output} ({format}; {fidelity['level']})\n",
        )
    except Exception as exc:
        return CommandResult(False, 1, stderr=f"ERROR: {exc}\n")
