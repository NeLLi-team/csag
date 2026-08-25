#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

REMOTE_BASE_URL = "https://api.newlineages.com/ocr"
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}
API_KEY_ENV_VARS = ("OCR_API_KEY", "NELLI_API_KEY")
BASE_URL_ENV = "OCR_BASE_URL"


def run(cmd: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, input=input_text, capture_output=True, text=True, check=False)


def run_curl(args: list[str], *, api_key: str) -> subprocess.CompletedProcess[str]:
    # Keep the API key out of the process argument list.
    config = f'header = "X-API-Key: {api_key}"\n'
    return run(["curl", "-fsS", "--max-time", "600", "-K", "-", *args], input_text=config)


def resolve_base_url(explicit: str | None) -> str:
    """Return the OCR base URL from the explicit argument, OCR_BASE_URL, or the remote default."""
    base_url = explicit or os.getenv(BASE_URL_ENV, "").strip() or REMOTE_BASE_URL
    parts = urlsplit(base_url)
    if parts.scheme != "https" and not (parts.scheme == "http" and parts.hostname in LOCAL_HOSTS):
        raise SystemExit("OCR base URL must use https, or http on localhost")
    return base_url


def require_api_key(args: argparse.Namespace) -> str:
    key = args.api_key or ""
    for env_var in API_KEY_ENV_VARS:
        key = key or os.getenv(env_var, "").strip()
    if not key:
        names = " or ".join(API_KEY_ENV_VARS)
        raise SystemExit(f"Missing OCR API key. Set {names} or pass --api-key.")
    # The key goes into a quoted curl config value, where curl decodes backslash
    # escapes; a quote, backslash, or whitespace would break or leak it.
    if '"' in key or "\\" in key or any(char.isspace() for char in key):
        raise SystemExit("OCR API key must not contain double quotes, backslashes, or whitespace.")
    return key


def curl_json(url: str, *, api_key: str, method: str = "GET", form_file: Path | None = None) -> dict:
    cmd = ["-X", method]
    if form_file is not None:
        cmd.extend(["-F", f"file=@{form_file}"])
    cmd.append(url)
    result = run_curl(cmd, api_key=api_key)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"curl failed for {url}")
    return json.loads(result.stdout)


def curl_download(url: str, *, api_key: str, output_path: Path) -> None:
    result = run_curl(["-o", str(output_path), url], api_key=api_key)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"curl failed for {url}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit a PDF to the OCR API service, poll the async job, and download Markdown/JSON artifacts."
    )
    parser.add_argument("input_path", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--base-url", default=None,
                        help="OCR API base URL; defaults to OCR_BASE_URL or the remote API.")
    parser.add_argument("--api-key", default=None,
                        help="OCR API key. Falls back to OCR_API_KEY / NELLI_API_KEY env vars.")
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--poll-interval-seconds", type=int, default=2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input_path.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    api_key = require_api_key(args)
    base_url = resolve_base_url(args.base_url).rstrip("/")
    output_dir.mkdir(parents=True, exist_ok=True)

    create_payload = curl_json(
        f"{base_url}/api/jobs",
        api_key=api_key,
        method="POST",
        form_file=input_path,
    )

    job_id = create_payload["job_id"]
    status_url = f"{base_url}/api/jobs/{job_id}"
    result_url = f"{base_url}/api/jobs/{job_id}/result"
    started = time.time()

    while True:
        status_payload = curl_json(status_url, api_key=api_key)
        status = status_payload["status"]
        if status == "succeeded":
            break
        if status == "failed":
            raise RuntimeError(f"OCR API job {job_id} failed: {status_payload.get('error')}")
        if time.time() - started > args.timeout_seconds:
            raise TimeoutError(f"OCR API job {job_id} timed out after {args.timeout_seconds}s")
        time.sleep(max(1, args.poll_interval_seconds))

    result_payload = curl_json(result_url, api_key=api_key)
    stem = input_path.stem
    markdown_path = output_dir / f"{stem}.md"
    ocr_json_path = output_dir / f"{stem}.ocr.json"
    job_meta_path = output_dir / f"{stem}.job.json"

    curl_download(f"{base_url}/api/jobs/{job_id}/artifacts/markdown", api_key=api_key, output_path=markdown_path)
    curl_download(f"{base_url}/api/jobs/{job_id}/artifacts/json", api_key=api_key, output_path=ocr_json_path)
    job_meta_path.write_text(
        json.dumps(
            {
                "job_create": create_payload,
                "job_status": status_payload,
                "job_result": result_payload,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"job={job_meta_path}")
    print(f"markdown={markdown_path}")
    print(f"json={ocr_json_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
