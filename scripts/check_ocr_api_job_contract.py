#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SECRET = "contract-secret"


FAKE_CURL = r'''#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


args = sys.argv[1:]
stdin_text = ""
if "-K" in args:
    index = args.index("-K")
    if index + 1 < len(args) and args[index + 1] == "-":
        stdin_text = sys.stdin.read()

log_path = Path(os.environ["FAKE_CURL_LOG"])
with log_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({"args": args, "stdin": stdin_text}) + "\n")

if os.environ["CONTRACT_SECRET"] in " ".join(args):
    print("secret leaked into curl argv", file=sys.stderr)
    raise SystemExit(43)

output_path = None
if "-o" in args:
    index = args.index("-o")
    output_path = Path(args[index + 1])

url = args[-1]
if url.endswith("/api/jobs") and "-X" in args and "POST" in args:
    print(json.dumps({"job_id": "job-1"}))
elif url.endswith("/api/jobs/job-1"):
    print(json.dumps({"status": "succeeded"}))
elif url.endswith("/api/jobs/job-1/result"):
    print(json.dumps({"summary": "done"}))
elif url.endswith("/api/jobs/job-1/artifacts/markdown") and output_path is not None:
    output_path.write_text("# OCR Contract\n\n## Abstract\n\nContract Markdown.\n", encoding="utf-8")
elif url.endswith("/api/jobs/job-1/artifacts/json") and output_path is not None:
    output_path.write_text(json.dumps({"pages": [{"index": 1, "text": "Contract Markdown."}]}) + "\n", encoding="utf-8")
else:
    print(f"unexpected fake curl invocation: {args}", file=sys.stderr)
    raise SystemExit(44)
'''


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="csag-ocr-contract-") as temp_name:
        temp_dir = Path(temp_name)
        bin_dir = temp_dir / "bin"
        bin_dir.mkdir()
        fake_curl = bin_dir / "curl"
        fake_curl.write_text(FAKE_CURL, encoding="utf-8")
        fake_curl.chmod(0o755)

        input_pdf = temp_dir / "paper.pdf"
        input_pdf.write_bytes(b"%PDF-1.4\n% fake contract input\n")
        output_dir = temp_dir / "out"
        log_path = temp_dir / "curl-log.jsonl"

        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{bin_dir}{os.pathsep}{env['PATH']}",
                "OCR_API_KEY": SECRET,
                "FAKE_CURL_LOG": str(log_path),
                "CONTRACT_SECRET": SECRET,
            }
        )
        command = [
            sys.executable,
            str(ROOT / "skills/pdf-to-md/scripts/ocr_api_job.py"),
            str(input_pdf),
            "--output-dir",
            str(output_dir),
            "--base-url",
            "https://ocr.contract.test/ocr",
            "--poll-interval-seconds",
            "1",
        ]
        completed = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, check=False)

        markdown = output_dir / "paper.md"
        ocr_json = output_dir / "paper.ocr.json"
        job_json = output_dir / "paper.job.json"
        errors: list[str] = []
        if completed.returncode != 0:
            errors.append(completed.stderr.strip() or completed.stdout.strip() or "ocr_api_job.py failed")
        for path in (markdown, ocr_json, job_json):
            if not path.exists():
                errors.append(f"missing output: {path.name}")
        if job_json.exists():
            job_meta = json.loads(job_json.read_text(encoding="utf-8"))
            for field in ("job_create", "job_status", "job_result"):
                if field not in job_meta:
                    errors.append(f"missing job metadata field: {field}")
        curl_calls = [
            json.loads(line)
            for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ] if log_path.exists() else []
        if len(curl_calls) != 5:
            errors.append(f"expected 5 curl calls, observed {len(curl_calls)}")
        for index, call in enumerate(curl_calls):
            args = call.get("args", [])
            stdin_text = call.get("stdin", "")
            if SECRET in " ".join(args):
                errors.append(f"secret present in curl argv for call {index}")
            if "-K" not in args or "-" not in args:
                errors.append(f"curl call {index} did not use stdin config")
            if SECRET not in stdin_text:
                errors.append(f"curl call {index} did not receive the API key through stdin config")

        report = {
            "ok": not errors,
            "curl_call_count": len(curl_calls),
            "outputs": sorted(path.name for path in output_dir.glob("*")) if output_dir.exists() else [],
            "errors": errors,
        }
        print(json.dumps(report, indent=2))
        return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
