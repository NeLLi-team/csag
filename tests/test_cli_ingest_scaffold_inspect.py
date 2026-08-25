from __future__ import annotations

import json
import subprocess
from pathlib import Path

import csag.cli as cli

ROOT = cli.ROOT
TOY_MD = ROOT / "examples" / "toy" / "toy.md"


def run_csag(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["uv", "run", "csag", *args], cwd=ROOT, text=True, capture_output=True, check=False)


def test_ingest(tmp_path: Path) -> None:
    ingest_dir = tmp_path / "ingest"
    ingest = run_csag("ingest", str(TOY_MD), "--output-dir", str(ingest_dir))
    assert ingest.returncode == 0, ingest.stderr
    assert (ingest_dir / "toy.md").exists()
    assert (ingest_dir / "toy.article.json").exists()
    assert (ingest_dir / "toy.section_audit.json").exists()


def test_ingest_markdown_in_place_without_output_dir(tmp_path: Path) -> None:
    from csag import ingest_manuscript

    md = tmp_path / "toy.md"
    md.write_text(TOY_MD.read_text(encoding="utf-8"), encoding="utf-8")
    result = ingest_manuscript(md)
    assert result.ok, result.stderr
    assert result.data["markdown"] == str(md)
    assert (tmp_path / "toy.article.json").exists()
    assert (tmp_path / "toy.section_audit.json").exists()


def test_scaffold_is_structural_lite_and_stable_ids(tmp_path: Path) -> None:
    workdir = tmp_path / "work"
    assert run_csag("ingest", str(TOY_MD), "--output-dir", str(workdir)).returncode == 0
    out1 = workdir / "paper_extraction.json"
    scaffold = run_csag("scaffold", str(workdir / "toy.md"), "--article-json", str(workdir / "toy.article.json"), "--output", str(out1), "--profile", "lite")
    assert scaffold.returncode == 0, scaffold.stderr
    first = json.loads(out1.read_text(encoding="utf-8"))
    out2 = workdir / "paper_extraction.second.json"
    assert run_csag("scaffold", str(workdir / "toy.md"), "--article-json", str(workdir / "toy.article.json"), "--output", str(out2), "--profile", "lite").returncode == 0
    second = json.loads(out2.read_text(encoding="utf-8"))
    assert first["id"] == second["id"]
    assert first["assertions"][0]["id"] == second["assertions"][0]["id"]
    validate = run_csag("validate", str(out1), "--profile", "lite", "--report-out", str(workdir / "paper_extraction.validation.json"))
    assert validate.returncode == 0, validate.stderr


def test_inspect_states(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    report = json.loads(run_csag("inspect", str(empty), "--json").stdout)
    assert report["state"] == "empty_or_missing"
    workdir = tmp_path / "work"
    assert run_csag("ingest", str(TOY_MD), "--output-dir", str(workdir)).returncode == 0
    ingested = json.loads(run_csag("inspect", str(workdir), "--json").stdout)
    assert ingested["state"] == "ingested"
    assert "scaffold" in ingested["suggested_next_command"]
