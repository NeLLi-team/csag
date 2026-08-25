#!/usr/bin/env python3
"""Run a small OCR API compatible with skills/pdf-to-md/scripts/ocr_api_job.py.

This development helper is intentionally separate from the local PDF fallback:
clients still submit a PDF over HTTP and receive OCR-derived artifacts through
the same API contract used by the remote service. Conversion is performed by
rendering PDF pages with pdftoppm and recognizing text with tesseract.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def run(cmd: list[str], *, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout)


def require_tools() -> None:
    missing = [name for name in ("pdftoppm", "tesseract") if shutil.which(name) is None]
    if missing:
        raise SystemExit(f"Missing required OCR tool(s): {', '.join(missing)}")


def extract_uploaded_file(body: bytes, content_type: str) -> tuple[str, bytes]:
    match = re.search(r"boundary=(?P<boundary>[^;]+)", content_type)
    if not match:
        raise ValueError("multipart boundary is missing")
    boundary = match.group("boundary").strip().strip('"').encode()
    marker = b"--" + boundary
    for part in body.split(marker):
        part = part.strip(b"\r\n")
        if not part or part == b"--" or b"\r\n\r\n" not in part:
            continue
        raw_headers, payload = part.split(b"\r\n\r\n", 1)
        headers = raw_headers.decode("utf-8", errors="replace")
        if 'name="file"' not in headers:
            continue
        filename_match = re.search(r'filename="(?P<name>[^"]+)"', headers)
        filename = filename_match.group("name") if filename_match else "input.pdf"
        return filename, payload.rstrip(b"\r\n")
    raise ValueError("multipart file field named 'file' was not found")


def page_sort_key(path: Path) -> tuple[int, str]:
    match = re.search(r"-(\d+)\.png$", path.name)
    if match:
        return int(match.group(1)), path.name
    return 0, path.name


def normalize_ocr_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    cleaned: list[str] = []
    blank = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if not blank:
                cleaned.append("")
            blank = True
            continue
        cleaned.append(stripped)
        blank = False
    return "\n".join(cleaned).strip()


def detect_heading(line: str) -> str | None:
    value = line.strip()
    normalized = re.sub(r"[^A-Za-z ]", "", value).strip().lower()
    headings = {
        "abstract",
        "introduction",
        "results",
        "discussion",
        "methods",
        "materials and methods",
        "results and discussion",
        "data availability",
        "code availability",
        "references",
        "acknowledgements",
        "author contributions",
        "competing interests",
        "additional information",
    }
    if normalized in headings:
        return value
    return None


def text_to_markdown(stem: str, pages: list[dict[str, Any]]) -> str:
    title = ""
    first_page_lines = [line.strip() for line in pages[0]["text"].splitlines()] if pages else []
    for index, line in enumerate(first_page_lines):
        line = line.strip()
        lower = line.lower()
        if (
            len(line) > 20
            and not lower.startswith(("nature", "www.", "article", "http", "doi", "check for updates"))
            and "@" not in line
        ):
            title_lines = [line]
            for continuation in first_page_lines[index + 1 : index + 4]:
                continuation_lower = continuation.lower()
                if (
                    not continuation
                    or continuation_lower.startswith(("received", "accepted", "published", "bikash"))
                    or "@" in continuation
                ):
                    break
                title_lines.append(continuation)
            title = " ".join(title_lines)
            break
    if not title:
        title = stem.replace("-", " ")

    output = [f"# {title}", ""]
    seen_headings: set[str] = set()
    for page in pages:
        output.append(f"<!-- OCR page {page['page']} -->")
        for raw_line in page["text"].splitlines():
            line = raw_line.strip()
            if not line:
                output.append("")
                continue
            heading = detect_heading(line)
            heading_key = re.sub(r"[^A-Za-z ]", "", line).strip().lower()
            if heading and heading_key not in seen_headings:
                output.extend(["", f"## {heading}", ""])
                seen_headings.add(heading_key)
            else:
                output.append(line)
        output.append("")
    return "\n".join(output).strip() + "\n"


def run_ocr(pdf_path: Path, work_dir: Path, dpi: int) -> tuple[str, dict[str, Any]]:
    image_prefix = work_dir / "page"
    render = run(["pdftoppm", "-r", str(dpi), "-png", str(pdf_path), str(image_prefix)])
    if render.returncode != 0:
        raise RuntimeError(render.stderr.strip() or render.stdout.strip() or "pdftoppm failed")

    pages: list[dict[str, Any]] = []
    for page_index, image_path in enumerate(sorted(work_dir.glob("page-*.png"), key=page_sort_key), start=1):
        ocr = run(["tesseract", str(image_path), "stdout", "--psm", "3", "-l", "eng"], timeout=180)
        if ocr.returncode != 0:
            raise RuntimeError(ocr.stderr.strip() or ocr.stdout.strip() or f"tesseract failed on {image_path.name}")
        text = normalize_ocr_text(ocr.stdout)
        pages.append(
            {
                "page": page_index,
                "image": image_path.name,
                "text": text,
                "char_count": len(text),
            }
        )

    markdown = text_to_markdown(pdf_path.stem, pages)
    ocr_json = {
        "engine": "tesseract",
        "renderer": "pdftoppm",
        "dpi": dpi,
        "page_count": len(pages),
        "pages": pages,
    }
    return markdown, ocr_json


class OCRState:
    def __init__(self, api_key: str, dpi: int, root: Path) -> None:
        self.api_key = api_key
        self.dpi = dpi
        self.root = root
        self.jobs: dict[str, dict[str, Any]] = {}


class Handler(BaseHTTPRequestHandler):
    server_version = "CSAGLocalTesseractOCR/0.1"

    @property
    def state(self) -> OCRState:
        return self.server.state  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        if self.server.verbose:  # type: ignore[attr-defined]
            super().log_message(format, *args)

    def write_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def write_text(self, text: str, content_type: str = "text/plain; charset=utf-8") -> None:
        data = text.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authorized(self) -> bool:
        return self.headers.get("X-API-Key", "") == self.state.api_key

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/ocr/health":
            self.write_json({"ok": True, "engine": "tesseract"})
            return
        if not self.authorized():
            self.write_json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
            return
        match = re.fullmatch(r"/ocr/api/jobs/([^/]+)", path)
        if match:
            job = self.state.jobs.get(match.group(1))
            if not job:
                self.write_json({"error": "job not found"}, HTTPStatus.NOT_FOUND)
                return
            self.write_json({"job_id": job["job_id"], "status": job["status"], "error": job.get("error")})
            return
        match = re.fullmatch(r"/ocr/api/jobs/([^/]+)/result", path)
        if match:
            job = self.state.jobs.get(match.group(1))
            if not job:
                self.write_json({"error": "job not found"}, HTTPStatus.NOT_FOUND)
                return
            self.write_json(job["result"])
            return
        match = re.fullmatch(r"/ocr/api/jobs/([^/]+)/artifacts/(markdown|json)", path)
        if match:
            job = self.state.jobs.get(match.group(1))
            if not job:
                self.write_json({"error": "job not found"}, HTTPStatus.NOT_FOUND)
                return
            if match.group(2) == "markdown":
                self.write_text(job["markdown"], "text/markdown; charset=utf-8")
            else:
                self.write_text(json.dumps(job["ocr_json"], indent=2) + "\n", "application/json")
            return
        self.write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path != "/ocr/api/jobs":
            self.write_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        if not self.authorized():
            self.write_json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        try:
            filename, payload = extract_uploaded_file(body, self.headers.get("Content-Type", ""))
            job_id = f"local-{uuid.uuid4().hex[:12]}"
            job_dir = self.state.root / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = job_dir / Path(filename).name
            pdf_path.write_bytes(payload)
            started = time.time()
            markdown, ocr_json = run_ocr(pdf_path, job_dir, self.state.dpi)
            result = {
                "job_id": job_id,
                "status": "succeeded",
                "engine": "tesseract",
                "renderer": "pdftoppm",
                "elapsed_seconds": round(time.time() - started, 3),
                "page_count": ocr_json["page_count"],
            }
            self.state.jobs[job_id] = {
                "job_id": job_id,
                "status": "succeeded",
                "markdown": markdown,
                "ocr_json": ocr_json,
                "result": result,
            }
            self.write_json({"job_id": job_id})
        except Exception as exc:
            job_id = f"local-{uuid.uuid4().hex[:12]}"
            self.state.jobs[job_id] = {"job_id": job_id, "status": "failed", "error": str(exc)}
            self.write_json({"job_id": job_id})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a local tesseract-backed OCR API for CSAG development.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument("--api-key", default="local-ocr-key")
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--work-dir", type=Path, default=None)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    require_tools()
    root = args.work_dir or Path(tempfile.mkdtemp(prefix="csag-local-ocr-api-"))
    root.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.state = OCRState(args.api_key, args.dpi, root)  # type: ignore[attr-defined]
    server.verbose = args.verbose  # type: ignore[attr-defined]
    print(f"serving http://{args.host}:{args.port}/ocr api_key={args.api_key} work_dir={root}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
