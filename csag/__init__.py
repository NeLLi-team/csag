"""CSAG Python API and command-line helpers."""

from .paths import CommandResult
from .ingest import ingest_manuscript
from .scaffold import scaffold_extraction
from .inspect import inspect_workdir
from .validate import validate_extraction
from .report import build_quality_report
from .lint import lint_extraction
from .export import export_extraction
from .score import score_extraction

__version__ = "1.0.0"

__all__ = [
    "CommandResult",
    "ingest_manuscript",
    "scaffold_extraction",
    "inspect_workdir",
    "validate_extraction",
    "build_quality_report",
    "lint_extraction",
    "export_extraction",
    "score_extraction",
]
