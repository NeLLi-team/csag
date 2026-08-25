from __future__ import annotations

from dataclasses import dataclass
import os
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    env_root = os.getenv("CSAG_REPO_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    checkout_root = Path(__file__).resolve().parents[1]
    if (checkout_root / "scripts").exists() and (checkout_root / "skills").exists():
        return checkout_root
    packaged_root = Path(__file__).resolve().parent / "data"
    if packaged_root.exists():
        return packaged_root
    return checkout_root


ROOT = repo_root()


@dataclass
class CommandResult:
    ok: bool
    exit_code: int
    report_path: Path | None = None
    data: dict | None = None
    stdout: str = ""
    stderr: str = ""


def default_output_dir(input_path: Path) -> Path:
    return ROOT / "work" / input_path.stem.replace("-", "_")


def run_python(script: Path, args: list[str], *, env: dict[str, str] | None = None) -> int:
    if not script.exists():
        print(
            f"Missing repository resource: {script}. "
            "Run from the CSAG checkout or set CSAG_REPO_ROOT to the checkout path.",
            file=sys.stderr,
        )
        return 1
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.call([sys.executable, str(script), *args], cwd=ROOT, env=merged_env)


def run_python_capture(script: Path, args: list[str], *, env: dict[str, str] | None = None) -> CommandResult:
    if not script.exists():
        return CommandResult(False, 1, stderr=f"Missing repository resource: {script}\n")
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    completed = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=ROOT,
        env=merged_env,
        text=True,
        capture_output=True,
        check=False,
    )
    return CommandResult(completed.returncode == 0, completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
