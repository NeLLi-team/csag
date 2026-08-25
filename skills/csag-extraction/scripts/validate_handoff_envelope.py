#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from jsonschema import Draft202012Validator, FormatChecker

from csag_provenance import check_report_inputs, input_record, sha256_file


ASSETS = Path(__file__).resolve().parents[1] / "assets"
JSON_SCHEMA_PATH = ASSETS / "csag.handoff.schema.json"
PAPER_SCHEMA_PATH = ASSETS / "csag.schema.json"
VALIDATOR_VERSION = "csag-handoff/1"
TERMINAL_EXECUTION_STATUSES = {"completed", "failed", "cancelled"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a versioned CSAG HandoffEnvelope."
    )
    parser.add_argument("envelope_json", type=Path)
    parser.add_argument("--profile", choices=("handoff",), default="handoff")
    parser.add_argument("--report-out", type=Path, required=True)
    return parser.parse_args()


def add_error(errors: list[str], path: str, message: str) -> None:
    errors.append(f"{path}: {message}")


def object_ids(value: Any, path: str = "handoff") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        if isinstance(value.get("id"), str):
            found.append((value["id"], f"{path}.id"))
        for key, child in value.items():
            found.extend(object_ids(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(object_ids(child, f"{path}[{index}]"))
    return found


def require_refs(
    refs: Any,
    known: set[str],
    path: str,
    errors: list[str],
) -> None:
    if refs is None:
        return
    if not isinstance(refs, list):
        add_error(errors, path, "must be a list of identifiers")
        return
    for index, ref in enumerate(refs):
        if ref not in known:
            add_error(errors, f"{path}[{index}]", f"reference does not resolve: {ref}")


def dependency_cycles(actions: list[dict[str, Any]]) -> list[list[str]]:
    graph = {
        action["id"]: list(action.get("dependencies") or [])
        for action in actions
        if isinstance(action, dict) and isinstance(action.get("id"), str)
    }
    cycles: list[list[str]] = []
    visiting: list[str] = []
    active: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in active:
            start = visiting.index(node)
            cycles.append(visiting[start:] + [node])
            return
        if node in visited:
            return
        active.add(node)
        visiting.append(node)
        for dependency in graph.get(node, []):
            if dependency in graph:
                visit(dependency)
        visiting.pop()
        active.remove(node)
        visited.add(node)

    for action_id in graph:
        visit(action_id)
    return cycles


def local_artifact_path(artifact_path: str, *, envelope_dir: Path) -> Path | None:
    parsed = urlsplit(artifact_path)
    if parsed.scheme == "file":
        raise ValueError("file: locators are not allowed; use a bundle-relative path")
    if parsed.scheme:
        return None
    if parsed.netloc:
        return None
    path = Path(unquote(parsed.path)).expanduser()
    if path.is_absolute():
        raise ValueError("absolute local paths are not allowed; use a bundle-relative path")
    bundle_root = envelope_dir.resolve()
    resolved = (bundle_root / path).resolve()
    try:
        resolved.relative_to(bundle_root)
    except ValueError as exc:
        raise ValueError("local path escapes the handoff bundle") from exc
    return resolved


def nested_ids(value: Any) -> set[str]:
    return {identifier for identifier, _ in object_ids(value, "source")}


def validate_semantics(
    envelope: dict[str, Any], *, envelope_path: Path
) -> tuple[list[str], list[Path]]:
    errors: list[str] = []
    verified_local_paths: set[Path] = set()
    revision = envelope.get("revision")
    parents = envelope.get("parents") or []
    current_heads = envelope.get("current_heads") or []
    if revision in parents:
        add_error(errors, "handoff.parents", "the current revision cannot be its own parent")
    if len(parents) != len(set(parents)):
        add_error(errors, "handoff.parents", "parent revision identifiers must be unique")
    if len(current_heads) != len(set(current_heads)):
        add_error(errors, "handoff.current_heads", "current head identifiers must be unique")

    ids_with_paths = object_ids(envelope)
    id_counts = Counter(identifier for identifier, _ in ids_with_paths)
    for identifier, count in sorted(id_counts.items()):
        if count > 1:
            paths = [path for value, path in ids_with_paths if value == identifier]
            add_error(errors, "handoff", f"duplicate object ID {identifier}: {', '.join(paths)}")

    source_artifacts = envelope.get("source_artifacts") or []
    actions = envelope.get("actions") or []
    executions = envelope.get("executions") or []
    assessments = envelope.get("assessments") or []
    conflicts = envelope.get("conflicts") or []

    source_ids = {
        artifact.get("id") for artifact in source_artifacts if isinstance(artifact, dict)
    }
    action_ids = {action.get("id") for action in actions if isinstance(action, dict)}
    execution_ids = {
        execution.get("id") for execution in executions if isinstance(execution, dict)
    }
    artifact_ids = set(source_ids)
    artifact_records: list[tuple[str, dict[str, Any]]] = [
        (f"handoff.source_artifacts[{index}]", artifact)
        for index, artifact in enumerate(source_artifacts)
        if isinstance(artifact, dict)
    ]
    for execution_index, execution in enumerate(executions):
        if not isinstance(execution, dict):
            continue
        for field in ("inputs", "outputs"):
            for artifact_index, artifact in enumerate(execution.get(field) or []):
                if not isinstance(artifact, dict):
                    continue
                artifact_ids.add(artifact.get("id"))
                artifact_records.append(
                    (
                        f"handoff.executions[{execution_index}].{field}[{artifact_index}]",
                        artifact,
                    )
                )

    if not any(
        isinstance(artifact, dict) and artifact.get("artifact_role") == "paper_extraction"
        for artifact in source_artifacts
    ):
        add_error(
            errors,
            "handoff.source_artifacts",
            "at least one content-hashed paper_extraction snapshot is required",
        )

    path_digests: dict[str, tuple[str, int | None]] = {}
    local_paper_extractions: list[dict[str, Any]] = []
    local_paper_digests: set[str] = set()
    local_reports: list[tuple[str, str, Path, dict[str, Any]]] = []
    paper_schema = json.loads(PAPER_SCHEMA_PATH.read_text(encoding="utf-8"))
    paper_validator = Draft202012Validator(
        paper_schema,
        format_checker=FormatChecker(),
    )
    for path, artifact in artifact_records:
        artifact_path = artifact.get("artifact_path")
        digest = artifact.get("sha256")
        size = artifact.get("byte_size")
        if not isinstance(artifact_path, str) or not isinstance(digest, str):
            continue
        identity = (digest, size if isinstance(size, int) else None)
        previous = path_digests.get(artifact_path)
        if previous is not None and previous != identity:
            add_error(
                errors,
                path,
                f"artifact_path {artifact_path!r} is associated with inconsistent hashes or sizes",
            )
        path_digests[artifact_path] = identity
        try:
            local_path = local_artifact_path(
                artifact_path,
                envelope_dir=envelope_path.parent,
            )
        except ValueError as exc:
            add_error(errors, f"{path}.artifact_path", str(exc))
            continue
        if local_path is None:
            continue
        if not local_path.is_file():
            add_error(errors, f"{path}.artifact_path", f"local artifact does not exist: {artifact_path}")
            continue
        actual_digest = sha256_file(local_path)
        digest_matches = actual_digest == digest
        if actual_digest != digest:
            add_error(
                errors,
                f"{path}.sha256",
                f"digest does not match local artifact bytes: {artifact_path}",
            )
        size_matches = not isinstance(size, int) or local_path.stat().st_size == size
        if not size_matches:
            add_error(
                errors,
                f"{path}.byte_size",
                f"byte_size does not match local artifact bytes: {artifact_path}",
            )
        if digest_matches and size_matches:
            verified_local_paths.add(local_path)
        if (
            path.startswith("handoff.source_artifacts[")
            and artifact.get("artifact_role") == "paper_extraction"
            and actual_digest == digest
        ):
            local_paper_digests.add(digest)
            try:
                candidate = json.loads(local_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                add_error(
                    errors,
                    f"{path}.artifact_path",
                    f"local paper_extraction snapshot is not readable JSON: {exc}",
                )
            else:
                if isinstance(candidate, dict):
                    schema_errors = sorted(
                        paper_validator.iter_errors(candidate),
                        key=lambda item: list(item.path),
                    )
                    for schema_error in schema_errors:
                        field = ".".join(str(part) for part in schema_error.absolute_path)
                        add_error(
                            errors,
                            f"{path}.artifact_path"
                            + (f".{field}" if field else ""),
                            f"local paper_extraction violates the closed schema: {schema_error.message}",
                        )
                    if not schema_errors:
                        local_paper_extractions.append(candidate)
                else:
                    add_error(
                        errors,
                        f"{path}.artifact_path",
                        "local paper_extraction snapshot must contain a JSON object",
                    )
        if (
            artifact.get("artifact_role") in {"validation_report", "quality_report"}
            and digest_matches
            and size_matches
        ):
            try:
                report = json.loads(local_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                add_error(
                    errors,
                    f"{path}.artifact_path",
                    f"local {artifact.get('artifact_role')} is not readable JSON: {exc}",
                )
            else:
                if isinstance(report, dict):
                    local_reports.append(
                        (path, str(artifact.get("artifact_role")), local_path, report)
                    )
                else:
                    add_error(
                        errors,
                        f"{path}.artifact_path",
                        f"local {artifact.get('artifact_role')} must contain a JSON object",
                    )

    successfully_validated_digests: set[str] = set()
    for path, role, report_path, report in local_reports:
        fresh, stale_inputs = check_report_inputs(report_path, report)
        if not fresh:
            stale_summary = "; ".join(
                f"{item.get('input')}: {item.get('reason')}" for item in stale_inputs
            )
            add_error(
                errors,
                f"{path}.artifact_path",
                f"local {role} has stale or invalid inputs: {stale_summary}",
            )
        report_inputs = report.get("inputs")
        extraction_input = (
            report_inputs.get("extraction")
            if isinstance(report_inputs, dict)
            else None
        )
        extraction_digest = (
            extraction_input.get("sha256")
            if isinstance(extraction_input, dict)
            else None
        )
        if extraction_digest not in local_paper_digests:
            add_error(
                errors,
                f"{path}.artifact_path",
                f"local {role} does not reference a declared source paper_extraction digest",
            )
        if role == "validation_report":
            if report.get("ok") is not True:
                add_error(
                    errors,
                    f"{path}.artifact_path",
                    "local validation_report must record ok=true",
                )
            elif fresh and extraction_digest in local_paper_digests:
                successfully_validated_digests.add(extraction_digest)
        elif role == "quality_report":
            required_sections = {"completeness", "field_quality", "issues"}
            missing_sections = sorted(required_sections - set(report))
            if missing_sections:
                add_error(
                    errors,
                    f"{path}.artifact_path",
                    f"local quality_report is missing sections: {', '.join(missing_sections)}",
                )
            elif not isinstance(report.get("issues"), list):
                add_error(
                    errors,
                    f"{path}.artifact_path",
                    "local quality_report issues must be a list",
                )

    for digest in sorted(local_paper_digests - successfully_validated_digests):
        add_error(
            errors,
            "handoff.source_artifacts",
            "local paper_extraction requires a fresh successful validation_report "
            f"for digest {digest}",
        )

    source_object_ids = set().union(*(nested_ids(source) for source in local_paper_extractions))
    source_assertion_ids = {
        assertion.get("id")
        for source in local_paper_extractions
        for assertion in source.get("assertions") or []
        if isinstance(assertion, dict) and isinstance(assertion.get("id"), str)
    }
    source_gap_ids = {
        gap.get("id")
        for source in local_paper_extractions
        for gap in source.get("knowledge_gaps") or []
        if isinstance(gap, dict) and isinstance(gap.get("id"), str)
    }

    action_by_id = {
        action["id"]: action
        for action in actions
        if isinstance(action, dict) and isinstance(action.get("id"), str)
    }
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            continue
        action_id = action.get("id")
        dependencies = action.get("dependencies") or []
        require_refs(
            dependencies,
            action_ids,
            f"handoff.actions[{index}].dependencies",
            errors,
        )
        if action_id in dependencies:
            add_error(
                errors,
                f"handoff.actions[{index}].dependencies",
                "an action cannot depend on itself",
            )
        if local_paper_extractions:
            require_refs(
                action.get("target_assertions"),
                source_assertion_ids,
                f"handoff.actions[{index}].target_assertions",
                errors,
            )
            require_refs(
                action.get("target_knowledge_gaps"),
                source_gap_ids,
                f"handoff.actions[{index}].target_knowledge_gaps",
                errors,
            )
    for cycle in dependency_cycles(actions):
        add_error(errors, "handoff.actions", f"dependency cycle detected: {' -> '.join(cycle)}")

    completed_actions_with_runs: set[str] = set()
    for index, execution in enumerate(executions):
        if not isinstance(execution, dict):
            continue
        environment_ref = execution.get("environment")
        if isinstance(environment_ref, str) and "#sha256=" in environment_ref:
            environment_path, environment_digest = environment_ref.rsplit("#sha256=", 1)
            try:
                local_environment = local_artifact_path(
                    environment_path,
                    envelope_dir=envelope_path.parent,
                )
            except ValueError as exc:
                add_error(
                    errors,
                    f"handoff.executions[{index}].environment",
                    str(exc),
                )
                local_environment = None
            if local_environment is not None:
                if not local_environment.is_file():
                    add_error(
                        errors,
                        f"handoff.executions[{index}].environment",
                        f"local environment lockfile does not exist: {environment_path}",
                    )
                elif sha256_file(local_environment) != environment_digest:
                    add_error(
                        errors,
                        f"handoff.executions[{index}].environment",
                        f"digest does not match local environment lockfile: {environment_path}",
                    )
                else:
                    verified_local_paths.add(local_environment)
        action_ref = execution.get("action_ref")
        if action_ref not in action_ids:
            add_error(
                errors,
                f"handoff.executions[{index}].action_ref",
                f"reference does not resolve: {action_ref}",
            )
        status = execution.get("execution_status")
        if status in TERMINAL_EXECUTION_STATUSES:
            if not execution.get("completed_on"):
                add_error(
                    errors,
                    f"handoff.executions[{index}].completed_on",
                    f"{status} execution requires a completion timestamp",
                )
            if not execution.get("execution_outcome"):
                add_error(
                    errors,
                    f"handoff.executions[{index}].execution_outcome",
                    f"{status} execution requires an outcome",
                )
        if status == "completed":
            if not execution.get("outputs"):
                add_error(
                    errors,
                    f"handoff.executions[{index}].outputs",
                    "completed execution requires at least one content-hashed output",
                )
            if isinstance(action_ref, str):
                completed_actions_with_runs.add(action_ref)

    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            continue
        if action.get("action_status") == "completed" and action.get("id") not in completed_actions_with_runs:
            add_error(
                errors,
                f"handoff.actions[{index}].action_status",
                "completed action requires a linked completed execution",
            )
        for dependency in action.get("dependencies") or []:
            dependency_action = action_by_id.get(dependency)
            if action.get("action_status") in {"ready", "in_progress", "completed"} and dependency_action:
                if dependency_action.get("action_status") != "completed":
                    add_error(
                        errors,
                        f"handoff.actions[{index}].dependencies",
                        f"active or completed action depends on unfinished action: {dependency}",
                    )

    for index, assessment in enumerate(assessments):
        if not isinstance(assessment, dict):
            continue
        require_refs(
            assessment.get("basis_artifacts"),
            artifact_ids,
            f"handoff.assessments[{index}].basis_artifacts",
            errors,
        )
        require_refs(
            assessment.get("basis_executions"),
            execution_ids,
            f"handoff.assessments[{index}].basis_executions",
            errors,
        )
        if local_paper_extractions:
            require_refs(
                assessment.get("basis_refs"),
                source_object_ids,
                f"handoff.assessments[{index}].basis_refs",
                errors,
            )
            require_refs(
                assessment.get("target_assertions"),
                source_assertion_ids,
                f"handoff.assessments[{index}].target_assertions",
                errors,
            )
        if not any(
            assessment.get(field)
            for field in ("basis_artifacts", "basis_refs", "basis_executions")
        ):
            add_error(
                errors,
                f"handoff.assessments[{index}]",
                "assessment requires at least one artifact, source-object, or execution basis",
            )

    known_revisions = set(parents) | set(current_heads) | ({revision} if revision else set())
    has_open_conflict = False
    for index, conflict in enumerate(conflicts):
        if not isinstance(conflict, dict):
            continue
        heads = conflict.get("competing_heads") or []
        for head_index, head in enumerate(heads):
            if head not in known_revisions:
                add_error(
                    errors,
                    f"handoff.conflicts[{index}].competing_heads[{head_index}]",
                    f"revision is absent from revision, parents, and current_heads: {head}",
                )
        if conflict.get("conflict_status") == "open":
            has_open_conflict = True
            missing_heads = set(heads) - set(current_heads)
            if missing_heads:
                add_error(
                    errors,
                    f"handoff.conflicts[{index}].competing_heads",
                    f"open conflict heads must be current: {', '.join(sorted(missing_heads))}",
                )
            if conflict.get("resolution") or conflict.get("resolved_by_head"):
                add_error(
                    errors,
                    f"handoff.conflicts[{index}]",
                    "open conflict cannot record a resolution or resolved_by_head",
                )
        elif conflict.get("conflict_status") == "resolved":
            if not conflict.get("resolution"):
                add_error(
                    errors,
                    f"handoff.conflicts[{index}].resolution",
                    "resolved conflict requires a resolution",
                )
            resolved_head = conflict.get("resolved_by_head")
            if resolved_head not in current_heads:
                add_error(
                    errors,
                    f"handoff.conflicts[{index}].resolved_by_head",
                    "resolved conflict must point to a current head",
                )
    if not has_open_conflict and revision not in current_heads:
        add_error(
            errors,
            "handoff.current_heads",
            "the envelope revision must be a current head when no conflict is open",
        )
    return errors, sorted(verified_local_paths, key=str)


def main() -> int:
    args = parse_args()
    envelope_path = args.envelope_json.expanduser().resolve()
    report_path = args.report_out.expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    try:
        envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        envelope = None
        add_error(errors, "handoff", f"cannot load JSON: {exc}")

    verified_local_paths: list[Path] = []
    if isinstance(envelope, dict):
        schema = json.loads(JSON_SCHEMA_PATH.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for error in sorted(validator.iter_errors(envelope), key=lambda item: list(item.path)):
            path = ".".join(str(part) for part in error.absolute_path)
            add_error(errors, f"handoff.{path}" if path else "handoff", error.message)
        if not errors:
            semantic_errors, verified_local_paths = validate_semantics(
                envelope, envelope_path=envelope_path
            )
            errors.extend(semantic_errors)
    elif envelope is not None:
        add_error(errors, "handoff", "root value must be a JSON object")

    envelope_input = input_record(envelope_path, base_dir=report_path.parent) if envelope_path.is_file() else None
    inputs = {"envelope_json": envelope_input} if envelope_input else {}
    for index, artifact_path in enumerate(verified_local_paths, start=1):
        inputs[f"artifact_{index:03d}"] = input_record(
            artifact_path,
            base_dir=report_path.parent,
        )
    report = {
        "ok": not errors,
        "profile": args.profile,
        "validator_version": VALIDATOR_VERSION,
        "envelope_json": envelope_input["path"] if envelope_input else None,
        "inputs": inputs,
        "errors": errors,
        "metrics": {
            "source_artifacts": len(envelope.get("source_artifacts") or []) if isinstance(envelope, dict) else 0,
            "assessments": len(envelope.get("assessments") or []) if isinstance(envelope, dict) else 0,
            "actions": len(envelope.get("actions") or []) if isinstance(envelope, dict) else 0,
            "executions": len(envelope.get("executions") or []) if isinstance(envelope, dict) else 0,
            "conflicts": len(envelope.get("conflicts") or []) if isinstance(envelope, dict) else 0,
            "current_heads": len(envelope.get("current_heads") or []) if isinstance(envelope, dict) else 0,
        },
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
