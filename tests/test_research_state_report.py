from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path

import csag.cli as cli


ROOT = cli.ROOT
LITE = ROOT / "examples" / "lite" / "paper_extraction.json"
LITE_MD = ROOT / "examples" / "lite" / "lite.md"
LITE_ARTICLE = ROOT / "examples" / "lite" / "lite.article.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _research_state_extraction() -> dict:
    extraction = deepcopy(_read(LITE))
    doc_id = extraction["id"]
    assertion_1 = extraction["assertions"][0]
    assertion_2 = deepcopy(assertion_1)
    assertion_2["id"] = f"csag:assertion/{doc_id}/A0002"
    assertion_2["assertion_text"] = "Dark controls, not blue light, explain the pigment difference."
    assertion_2["claim_role"] = "hypothesis"
    assertion_2["contexts"][0]["id"] = f"csag:context/{doc_id}/C0003"
    assertion_2["text_spans"][0]["id"] = f"csag:span/{doc_id}/S0003"
    extraction["assertions"].append(assertion_2)
    extraction["artifacts"] = [
        {
            "id": f"csag:artifact/{doc_id}/F0001",
            "artifact_type": "figure",
            "artifact_label": "Figure 1",
            "caption": "Pigment absorbance under blue-light and dark-control conditions.",
        }
    ]
    extraction["evidence_items"][0]["evidence_type"] = "experimental_result"
    extraction["evidence_items"][0]["associated_artifacts"] = [f"csag:artifact/{doc_id}/F0001"]
    extraction["assertion_relations"] = [
        {
            "id": f"csag:relation/{doc_id}/AR0001",
            "from_assertion": assertion_1["id"],
            "to_assertion": assertion_2["id"],
            "relation_type": "competes_with",
            "relation_rationale": "Both assertions explain the same treatment-control observation.",
        }
    ]
    extraction["research_states"] = [
        {
            "id": f"csag:state/{doc_id}/RS0001",
            "target_assertions": [assertion_1["id"]],
            "state": "needs_replication",
            "current_read": "Supported by one experiment; independent replication is still needed.",
            "recommended_next_actions": [f"csag:action/{doc_id}/NA0001"],
        }
    ]
    extraction["next_actions"] = [
        {
            "id": f"csag:action/{doc_id}/NA0001",
            "action_type": "replication",
            "description": "Repeat the blue-light assay with independent cultures.",
            "target_assertions": [assertion_1["id"]],
            "priority": "moderate",
        }
    ]
    extraction["executions"] = [
        {
            "id": f"csag:execution/{doc_id}/EX0001",
            "execution_type": "analysis script",
            "execution_status": "completed",
            "command": "uv run python scripts/analyze_absorbance.py",
            "output_artifacts": [f"csag:artifact/{doc_id}/F0001"],
            "generated_evidence_items": [extraction["evidence_items"][0]["id"]],
            "tested_assertions": [assertion_1["id"]],
        }
    ]
    return extraction


def test_research_state_profile_accepts_state_actions_executions_and_competing_relations(tmp_path: Path) -> None:
    extraction_path = tmp_path / "paper_extraction.json"
    extraction_path.write_text(json.dumps(_research_state_extraction(), indent=2) + "\n", encoding="utf-8")
    report_out = tmp_path / "validation.json"
    args = argparse.Namespace(
        extraction_json=extraction_path,
        source_markdown=LITE_MD,
        article_json=LITE_ARTICLE,
        profile="core,research_state",
        report_out=report_out,
    )
    code = cli.cmd_validate(args)
    report = _read(report_out)
    assert code == 0
    assert report["ok"] is True
    assert report["profile_modules"] == ["core", "research_state"]


def test_research_state_profile_rejects_broken_next_action_reference(tmp_path: Path) -> None:
    extraction = _research_state_extraction()
    extraction["research_states"][0]["recommended_next_actions"] = ["csag:action/missing"]
    extraction_path = tmp_path / "paper_extraction.json"
    extraction_path.write_text(json.dumps(extraction, indent=2) + "\n", encoding="utf-8")
    report_out = tmp_path / "validation.json"
    args = argparse.Namespace(
        extraction_json=extraction_path,
        source_markdown=LITE_MD,
        article_json=LITE_ARTICLE,
        profile="core,research_state",
        report_out=report_out,
    )
    code = cli.cmd_validate(args)
    report = _read(report_out)
    assert code == 1
    assert any("recommended_next_actions" in error for error in report["errors"])


def test_quality_report_includes_claim_readouts_execution_evidence_and_openalex_context(tmp_path: Path) -> None:
    extraction_path = tmp_path / "paper_extraction.json"
    extraction_path.write_text(json.dumps(_research_state_extraction(), indent=2) + "\n", encoding="utf-8")
    openalex_json = tmp_path / "openalex_work.json"
    openalex_json.write_text(
        json.dumps(
            {
                "id": "https://openalex.org/W123",
                "doi": "https://doi.org/10.0000/example",
                "display_name": "Lite Claim Example",
                "publication_year": 2024,
                "cited_by_count": 30,
                "counts_by_year": [
                    {"year": 2026, "cited_by_count": 12},
                    {"year": 2025, "cited_by_count": 10},
                    {"year": 2024, "cited_by_count": 8},
                ],
                "fwci": 1.7,
                "is_retracted": False,
                "type": "article",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    report_out = tmp_path / "quality.json"
    args = argparse.Namespace(
        extraction_json=extraction_path,
        source_markdown=LITE_MD,
        article_json=LITE_ARTICLE,
        openalex_json=openalex_json,
        analysis_year=2026,
        report_out=report_out,
        strict=False,
        document_scope="lite",
    )
    code = cli.cmd_report(args)
    report = _read(report_out)
    assert code == 0
    assert report["claim_readouts"][0]["state"] == "needs_replication"
    assert report["claim_readouts"][0]["next_actions"][0]["action_type"] == "replication"
    assert report["artifact_discipline"]["score"] == 1.0
    assert report["conversion_quality"]["overall_conversion_score"] > 0
    assert report["literature_quality"]["metrics"]["citations_per_year"] == 10.0
    assert report["literature_quality"]["signals"][1]["status"] == "moderate"


def test_claim_readout_treats_refuting_and_mixed_evidence_as_mixed(tmp_path: Path) -> None:
    extraction = deepcopy(_read(LITE))
    assertion_id = extraction["assertions"][0]["id"]
    doc_id = extraction["id"]
    extraction["research_states"] = []
    extraction["next_actions"] = []
    extraction["evidence_links"][0]["polarity"] = "refutes"
    extraction["evidence_items"].append(
        {
            "id": f"csag:evidence/{doc_id}/E0002",
            "evidence_type": "observation",
            "evidence_text": "A second observation was directionally inconsistent.",
            "contexts": extraction["assertions"][0]["contexts"],
        }
    )
    extraction["evidence_links"].append(
        {
            "id": f"csag:elink/{doc_id}/L0002",
            "evidence_item": f"csag:evidence/{doc_id}/E0002",
            "assertion": assertion_id,
            "polarity": "mixed",
            "strength": "weak",
        }
    )

    extraction_path = tmp_path / "paper_extraction.json"
    extraction_path.write_text(json.dumps(extraction, indent=2) + "\n", encoding="utf-8")
    report_out = tmp_path / "quality.json"
    args = argparse.Namespace(
        extraction_json=extraction_path,
        source_markdown=LITE_MD,
        article_json=LITE_ARTICLE,
        openalex_json=None,
        analysis_year=None,
        report_out=report_out,
        strict=False,
        document_scope="lite",
    )
    code = cli.cmd_report(args)
    report = _read(report_out)

    assert code == 0
    assert report["claim_readouts"][0]["state"] == "mixed"
    assert len(report["claim_readouts"][0]["evidence_against"]) == 1
    assert len(report["claim_readouts"][0]["mixed_or_inconclusive"]) == 1
