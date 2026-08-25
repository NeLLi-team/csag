from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_doc_json_snippets.py"


def run_checker(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), str(path)], cwd=ROOT, text=True, capture_output=True, check=False)


def test_doc_json_snippets_pass_current_docs() -> None:
    completed = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_doc_json_snippets_flags_stale_alias_and_enum(tmp_path: Path) -> None:
    md = tmp_path / "bad.md"
    md.write_text('''# Bad\n\n```json\n{"id":"c1", "facet":"experimental_context"}\n```\n''', encoding="utf-8")
    completed = run_checker(md)
    report = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert any(issue["field"] == "facet" for issue in report["issues"])


def test_doc_json_snippets_flags_unknown_field(tmp_path: Path) -> None:
    md = tmp_path / "bad.md"
    md.write_text('''# Bad\n\n```json\n{"evidence_item":"E1", "assertion":"A1", "polarity":"maybe"}\n```\n''', encoding="utf-8")
    completed = run_checker(md)
    report = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert any(issue["field"] == "polarity" for issue in report["issues"])


def test_doc_json_snippets_flags_schema_type_mismatch(tmp_path: Path) -> None:
    md = tmp_path / "bad.md"
    md.write_text(
        '''# Bad

```json
{"assertion_text":"Claim", "claim_role":"conclusion", "normalization_status":"raw", "contexts":["csag:context/C0001"]}
```
''',
        encoding="utf-8",
    )
    completed = run_checker(md)
    report = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert any(
        issue["field"] == "contexts.0" and "not of type 'object'" in issue["reason"]
        for issue in report["issues"]
    )
