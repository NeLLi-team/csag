from __future__ import annotations

import csv
from datetime import date
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from pyld import jsonld
from rdflib import Graph, RDF, URIRef

import csag.export as export_module
from csag.export import EXPORT_FIDELITY, export_extraction
from csag.provenance import input_records


def graph_fixture(tmp_path: Path) -> Path:
    doc = "csag:doc/export_fixture"
    assertion = f"csag:assertion/{doc}/A0001"
    evidence_ids = [f"csag:evidence/{doc}/E{i:04d}" for i in range(1, 4)]
    payload = {
        "id": doc,
        "title": "Export fixture",
        "schema_version": "0.6.0",
        "validator_version": "0.6.0",
        "assertions": [{"id": assertion, "assertion_text": "Claim one.", "claim_role": "result_claim", "criticality": "core", "normalization_status": "raw", "contexts": [{"id": f"csag:context/{doc}/C0001", "label": "ctx", "context_facet": "other"}]}],
        "evidence_items": [
            {"id": evidence_ids[0], "evidence_type": "observation", "evidence_text": "Evidence 1", "associated_artifacts": [f"csag:artifact/{doc}/F0001"], "associated_datasets": [f"csag:dataset/{doc}/D0001"]},
            {"id": evidence_ids[1], "evidence_type": "observation", "evidence_text": "Evidence 2"},
            {"id": evidence_ids[2], "evidence_type": "observation", "evidence_text": "Evidence 3"},
        ],
        "evidence_links": [{"id": f"csag:elink/{doc}/L{i:04d}", "evidence_item": eid, "assertion": assertion, "polarity": "supports", "strength": "moderate"} for i, eid in enumerate(evidence_ids, 1)],
        "critiques": [{"id": f"csag:critique/{doc}/R0001", "critique_type": "limitation", "impacted_assertions": [assertion]}],
        "knowledge_gaps": [{"id": f"csag:gap/{doc}/G0001", "gap_type": "future_work", "related_assertions": [assertion]}],
        "artifacts": [{"id": f"csag:artifact/{doc}/F0001", "artifact_type": "figure", "artifact_label": "Figure 1"}],
        "datasets": [{"id": f"csag:dataset/{doc}/D0001", "label": "Dataset 1"}],
    }
    path = tmp_path / "paper_extraction.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def test_table_export_one_row_per_evidence_link(tmp_path: Path) -> None:
    source = graph_fixture(tmp_path)
    output = tmp_path / "out.tsv"
    result = export_extraction(source, format="table", output=output)
    assert result.ok
    rows = list(csv.DictReader(output.open(encoding="utf-8"), delimiter="\t"))
    assert len(rows) == 3
    assert {row["evidence_link_id"] for row in rows} == {"csag:elink/csag:doc/export_fixture/L0001", "csag:elink/csag:doc/export_fixture/L0002", "csag:elink/csag:doc/export_fixture/L0003"}
    assert all(row["missing_evidence"] == "false" for row in rows)


def test_graphml_export_includes_graph_structure(tmp_path: Path) -> None:
    source = graph_fixture(tmp_path)
    output = tmp_path / "out.graphml"
    assert export_extraction(source, format="graphml", output=output).ok
    tree = ET.parse(output)
    ns = {"g": "http://graphml.graphdrawing.org/xmlns"}
    data_values = [node.text for node in tree.findall(".//g:data", ns)]
    for expected in ["Assertion", "EvidenceItem", "Context", "StudyCritique", "KnowledgeGap", "Artifact", "Dataset", "evidence_link", "scoped_by", "impacts", "related_to", "uses_artifact", "uses_dataset"]:
        assert expected in data_values
    output2 = tmp_path / "out2.graphml"
    assert export_extraction(source, format="graphml", output=output2).ok
    assert output.read_text(encoding="utf-8") == output2.read_text(encoding="utf-8")


def test_graphml_export_quote_escapes_dynamic_identifiers(tmp_path: Path) -> None:
    source = graph_fixture(tmp_path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    hostile_id = 'csag:assertion/csag:doc/export_fixture/A"0001&<'
    payload["assertions"][0]["id"] = hostile_id
    for link in payload["evidence_links"]:
        link["assertion"] = hostile_id
    source.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    output = tmp_path / "hostile.graphml"
    result = export_extraction(source, format="graphml", output=output)
    assert result.ok, result.stderr
    tree = ET.parse(output)
    ns = {"g": "http://graphml.graphdrawing.org/xmlns"}
    assert hostile_id in [node.get("id") for node in tree.findall(".//g:node", ns)]
    assert hostile_id in [edge.get("target") for edge in tree.findall(".//g:edge", ns)]


def test_exports_preserve_string_context_references(tmp_path: Path) -> None:
    doc = "csag:doc/strctx"
    cid = f"csag:context/{doc}/C0001"
    aid = f"csag:assertion/{doc}/A0001"
    eid = f"csag:evidence/{doc}/E0001"
    payload = {
        "id": doc,
        "title": "String context refs",
        "schema_version": "0.6.0",
        "validator_version": "0.6.0",
        "contexts": [{"id": cid, "label": "broad", "context_facet": "other"}],
        "assertions": [{"id": aid, "assertion_text": "Claim.", "claim_role": "result_claim", "criticality": "core", "normalization_status": "raw", "contexts": [cid]}],
        "evidence_items": [{"id": eid, "evidence_type": "observation", "evidence_text": "ev", "contexts": [cid]}],
        "evidence_links": [{"id": f"csag:elink/{doc}/L0001", "evidence_item": eid, "assertion": aid, "polarity": "supports"}],
    }
    source = tmp_path / "paper_extraction.json"
    source.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    tsv = tmp_path / "out.tsv"
    assert export_extraction(source, format="table", output=tsv).ok
    rows = list(csv.DictReader(tsv.open(encoding="utf-8"), delimiter="\t"))
    assert rows and cid in rows[0]["context_ids"]

    graphml = tmp_path / "out.graphml"
    assert export_extraction(source, format="graphml", output=graphml).ok
    tree = ET.parse(graphml)
    ns = {"g": "http://graphml.graphdrawing.org/xmlns"}
    assert cid in [node.get("id") for node in tree.findall(".//g:node", ns)]
    assert "scoped_by" in [data.text for data in tree.findall(".//g:edge/g:data", ns)]

    jsonld_path = tmp_path / "out.jsonld"
    assert export_extraction(source, format="jsonld", output=jsonld_path).ok
    graph = Graph().parse(jsonld_path, format="json-ld")
    base = "https://w3id.org/csag/"
    assert (
        URIRef(base + aid.removeprefix("csag:")),
        URIRef(base + "contexts"),
        URIRef(base + cid.removeprefix("csag:")),
    ) in graph


def test_json_export_is_lossless_and_every_export_reports_fidelity(tmp_path: Path) -> None:
    source = graph_fixture(tmp_path)
    expected = json.loads(source.read_text(encoding="utf-8"))
    for export_format, contract in EXPORT_FIDELITY.items():
        output = tmp_path / ("crate" if export_format == "ro-crate" else f"out.{export_format}")
        result = export_extraction(source, format=export_format, output=output)
        assert result.ok, result.stderr
        assert result.data == {"format": export_format, "fidelity": contract}
    assert json.loads((tmp_path / "out.json").read_text(encoding="utf-8")) == expected


def test_jsonld_and_turtle_are_isomorphic_semantic_projections(tmp_path: Path) -> None:
    source = graph_fixture(tmp_path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["assertions"][0]["assertion_text"] = 'A claim with "quotes" and Unicode β.'
    source.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    jsonld_path = tmp_path / "out.jsonld"
    turtle_path = tmp_path / "out.ttl"
    assert export_extraction(source, format="jsonld", output=jsonld_path).ok
    assert export_extraction(source, format="rdf", output=turtle_path).ok

    expanded = jsonld.expand(json.loads(jsonld_path.read_text(encoding="utf-8")))
    assert expanded
    jsonld_graph = Graph().parse(jsonld_path, format="json-ld")
    turtle_graph = Graph().parse(turtle_path, format="turtle")
    assert jsonld_graph.isomorphic(turtle_graph)

    def iri(identifier: str) -> URIRef:
        return URIRef("https://w3id.org/csag/" + identifier.removeprefix("csag:"))

    object_ids = [
        payload["id"],
        *[item["id"] for item in payload["assertions"]],
        *[item["id"] for item in payload["evidence_items"]],
        *[item["id"] for item in payload["evidence_links"]],
    ]
    subjects = set(jsonld_graph.subjects())
    assert {iri(identifier) for identifier in object_ids} <= subjects
    link = payload["evidence_links"][0]
    assert (
        iri(link["id"]),
        URIRef("https://w3id.org/csag/evidence_item"),
        iri(link["evidence_item"]),
    ) in jsonld_graph


def test_jsonld_and_turtle_type_inline_study_contexts(tmp_path: Path) -> None:
    source = graph_fixture(tmp_path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    study_id = "csag:study/csag:doc/export_fixture/S0001"
    context_id = "csag:context/csag:doc/export_fixture/C0002"
    payload["studies"] = [
        {
            "id": study_id,
            "study_contexts": [
                {
                    "id": context_id,
                    "label": "study context",
                    "context_facet": "other",
                }
            ],
        }
    ]
    source.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    jsonld_path = tmp_path / "out.jsonld"
    turtle_path = tmp_path / "out.ttl"
    assert export_extraction(source, format="jsonld", output=jsonld_path).ok
    assert export_extraction(source, format="rdf", output=turtle_path).ok
    base = "https://w3id.org/csag/"
    study_iri = URIRef(base + study_id.removeprefix("csag:"))
    context_iri = URIRef(base + context_id.removeprefix("csag:"))
    predicate = URIRef(base + "study_contexts")
    context_type = URIRef(base + "Context")
    for graph in (
        Graph().parse(jsonld_path, format="json-ld"),
        Graph().parse(turtle_path, format="turtle"),
    ):
        assert (study_iri, predicate, context_iri) in graph
        assert (context_iri, RDF.type, context_type) in graph


def test_ro_crate_copies_reports_and_verifies_every_file_hash(tmp_path: Path) -> None:
    source = graph_fixture(tmp_path)
    inputs = input_records(base_dir=tmp_path, extraction=source)
    for name, payload in (
        ("paper_extraction.validation.json", {"ok": True, "profile": "paper_local", "inputs": inputs}),
        ("paper_extraction.quality.json", {"issues": [], "inputs": inputs}),
        ("paper_extraction.lint.json", {"ok": True, "inputs": inputs}),
    ):
        (tmp_path / name).write_text(json.dumps(payload) + "\n", encoding="utf-8")
    output = tmp_path / "crate"
    result = export_extraction(source, format="ro-crate", output=output)
    assert result.ok, result.stderr
    metadata = json.loads((output / "ro-crate-metadata.json").read_text(encoding="utf-8"))
    root = next(node for node in metadata["@graph"] if node["@id"] == "./")
    descriptor = next(
        node
        for node in metadata["@graph"]
        if node["@id"] == "ro-crate-metadata.json"
    )
    assert descriptor == {
        "@id": "ro-crate-metadata.json",
        "@type": "CreativeWork",
        "about": {"@id": "./"},
        "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
    }
    assert date.fromisoformat(root["datePublished"])
    assert root["csag:validationProfile"] == "paper_local"
    assert root["csag:bundleFidelity"] == "lossless-included-files"
    file_nodes = {node["@id"]: node for node in metadata["@graph"] if node.get("@type") == "File"}
    for required in (
        "paper_extraction.json",
        "paper_extraction.validation.json",
        "paper_extraction.quality.json",
        "paper_extraction.lint.json",
    ):
        copied = output / required
        original = tmp_path / required
        assert copied.read_bytes() == original.read_bytes()
        assert file_nodes[required]["sha256"] == hashlib.sha256(original.read_bytes()).hexdigest()
        assert file_nodes[required]["contentSize"] == original.stat().st_size


def test_ro_crate_prefers_local_supplements_and_deduplicates_destinations(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "work" / "paper"
    source_dir.mkdir(parents=True)
    source = graph_fixture(source_dir)
    source_document = json.loads(source.read_text(encoding="utf-8"))["id"]

    local = source_dir / "entity-normalization"
    repository = tmp_path / "repository" / "supplementary" / "entity-normalization"
    local.mkdir(parents=True)
    repository.mkdir(parents=True)
    local_report = {"source_document": source_document, "origin": "local"}
    repository_report = {"source_document": source_document, "origin": "repository"}
    (local / "normalization_report.json").write_text(
        json.dumps(local_report) + "\n", encoding="utf-8"
    )
    (repository / "normalization_report.json").write_text(
        json.dumps(repository_report) + "\n", encoding="utf-8"
    )
    for directory in (local, repository):
        (directory / "shared.tsv").write_text("id\tlabel\n1\tshared\n", encoding="utf-8")

    monkeypatch.setattr(export_module, "ROOT", tmp_path / "repository")
    output = tmp_path / "crate"
    result = export_extraction(source, format="ro-crate", output=output)
    assert result.ok, result.stderr
    assert json.loads(
        (output / "entity-normalization" / "normalization_report.json").read_text(
            encoding="utf-8"
        )
    ) == local_report

    metadata = json.loads((output / "ro-crate-metadata.json").read_text(encoding="utf-8"))
    file_ids = [
        node["@id"]
        for node in metadata["@graph"]
        if node.get("@type") == "File"
    ]
    has_part_ids = next(node for node in metadata["@graph"] if node["@id"] == "./")[
        "hasPart"
    ]
    assert len(file_ids) == len(set(file_ids))
    assert file_ids.count("entity-normalization/normalization_report.json") == 1
    assert file_ids.count("entity-normalization/shared.tsv") == 1
    assert has_part_ids.count({"@id": "entity-normalization/normalization_report.json"}) == 1
    assert has_part_ids.count({"@id": "entity-normalization/shared.tsv"}) == 1


def test_ro_crate_refuses_to_package_a_stale_report(tmp_path: Path) -> None:
    source = graph_fixture(tmp_path)
    report = {
        "ok": True,
        "inputs": input_records(base_dir=tmp_path, extraction=source),
    }
    (tmp_path / "paper_extraction.validation.json").write_text(
        json.dumps(report) + "\n", encoding="utf-8"
    )
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    result = export_extraction(source, format="ro-crate", output=tmp_path / "crate")
    assert not result.ok
    assert "stale report" in result.stderr
