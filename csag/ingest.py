from __future__ import annotations

import hashlib
import os
import shutil
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .paths import CommandResult, ROOT, default_output_dir, run_python

REMOTE_OCR_BASE_URL = "https://api.newlineages.com/ocr"
LOCAL_OCR_HOSTS = {"127.0.0.1", "::1", "localhost"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ocr_base_url(explicit: str | None = None) -> str:
    base_url = (explicit or os.getenv("OCR_BASE_URL", "").strip() or REMOTE_OCR_BASE_URL).rstrip("/")
    parts = urlsplit(base_url)
    if parts.scheme != "https" and not (parts.scheme == "http" and parts.hostname in LOCAL_OCR_HOSTS):
        raise SystemExit("OCR base URL must use https, or http on localhost")
    return base_url


def check_http(url: str, timeout: float = 3.0, *, api_key: str | None = None) -> tuple[bool, str]:
    try:
        request = Request(url, headers={"X-API-Key": api_key} if api_key else {})
        with urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 500, f"HTTP {response.status}"
    except URLError as exc:
        return False, str(exc.reason)
    except Exception as exc:  # pragma: no cover - defensive network detail
        return False, str(exc)


def has_ocr_api_key(explicit: str | None = None) -> bool:
    return bool(explicit or os.getenv("OCR_API_KEY") or os.getenv("NELLI_API_KEY"))


def ingest_manuscript(
    input_path: Path,
    *,
    output_dir: Path | None = None,
    pdf_mode: str = "ocr",
    base_url: str | None = None,
    api_key: str | None = None,
) -> CommandResult:
    input_path = input_path.expanduser().resolve()
    explicit_output_dir = output_dir is not None
    output_dir = (output_dir or default_output_dir(input_path)).expanduser().resolve()
    stdout_parts: list[str] = []

    if input_path.suffix.lower() == ".pdf":
        output_dir_preexisting = output_dir.exists()

        def run_ocr_api() -> int:
            if not has_ocr_api_key(api_key):
                print("Missing OCR API key. Set OCR_API_KEY or NELLI_API_KEY or pass --api-key.", file=sys.stderr)
                return 1
            script = ROOT / "skills/pdf-to-md/scripts/ocr_api_job.py"
            ocr_args = [str(input_path), "--output-dir", str(output_dir)]
            if base_url:
                ocr_args.extend(["--base-url", base_url])
            ocr_env = {"OCR_API_KEY": api_key} if api_key else None
            return run_python(script, ocr_args, env=ocr_env)

        def run_local_pdf() -> int:
            script = ROOT / "skills/pdf-to-md/scripts/liteparse_to_md.py"
            return run_python(script, [str(input_path), "--output-dir", str(output_dir)])

        modes = [pdf_mode]
        if pdf_mode == "auto":
            modes = ["ocr", "local"] if has_ocr_api_key(api_key) else ["local"]

        code = 1
        for index, mode in enumerate(modes):
            code = run_ocr_api() if mode == "ocr" else run_local_pdf()
            if code == 0:
                break
            if pdf_mode == "auto" and index < len(modes) - 1:
                print("PDF conversion failed with OCR API; trying local LiteParse fallback.", file=sys.stderr)

        if code != 0:
            if not output_dir_preexisting and output_dir.exists() and not any(output_dir.iterdir()):
                output_dir.rmdir()
            return CommandResult(False, code)
        markdown = output_dir / f"{input_path.stem}.md"
    else:
        if explicit_output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            markdown = output_dir / input_path.name
            if input_path != markdown.resolve():
                shutil.copy2(input_path, markdown)
        else:
            markdown = input_path

    code = run_python(ROOT / "skills/pdf-to-md/scripts/populate_article_json.py", [str(markdown)])
    if code != 0:
        return CommandResult(False, code)
    article_json = markdown.with_suffix(".article.json")
    section_audit = markdown.with_suffix(".section_audit.json")
    code = run_python(
        ROOT / "skills/pdf-to-md/scripts/validate_article_json.py",
        [str(article_json), "--scientific-paper", "--section-audit", str(section_audit)],
    )
    data = {"markdown": str(markdown), "article_json": str(article_json), "section_audit": str(section_audit)}
    stdout_parts.append(f"markdown={markdown}\narticle_json={article_json}\nsection_audit={section_audit}\n")
    return CommandResult(code == 0, code, data=data, stdout="".join(stdout_parts))
