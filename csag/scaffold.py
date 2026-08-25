from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .paths import CommandResult

DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
PMID_RE = re.compile(r"\bPMID[:\s]+(\d{6,9})\b", re.IGNORECASE)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug[:80] or "untitled"


def _title_from_markdown(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or fallback
    return fallback


def _first_sentence(text: str, fallback: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return fallback
    match = re.search(r"(.+?[.!?])(?:\s|$)", cleaned)
    return (match.group(1) if match else cleaned[:240]).strip()


def _body_text(text: str) -> str:
    """Join non-empty, non-heading Markdown lines into one searchable string."""
    parts = [line.strip() for line in (text or "").splitlines()]
    return " ".join(line for line in parts if line and not line.startswith("#"))


def _span(markdown: str, exact: str, document_id: str, span_id: str, section_type: str = "other") -> list[dict]:
    exact = (exact or "").strip()
    if not exact:
        return []
    start = markdown.find(exact)
    if start < 0:
        start = markdown.lower().find(exact.lower())
    if start >= 0:
        end = start + len(exact)
    else:
        # Tolerate whitespace differences (e.g. a sentence wrapped across Markdown lines).
        pattern = re.compile(r"\s+".join(re.escape(token) for token in exact.split()), re.IGNORECASE)
        match = pattern.search(markdown)
        if not match:
            return []
        start, end = match.start(), match.end()
    return [{"id": span_id, "document_id": document_id, "section_type": section_type, "start_char": start, "end_char": end, "exact_text": markdown[start:end]}]


def _authors(value: object, document_id: str) -> list[dict]:
    if isinstance(value, list):
        authors = [dict(item) if isinstance(item, dict) else {"label": str(item)} for item in value]
    elif isinstance(value, str) and value.strip():
        parts = re.split(r"\s+(?:and|&)\s+|\s*;\s*", value.strip())
        authors = [{"label": part.strip()} for part in parts if part.strip()]
    else:
        authors = []
    for index, author in enumerate(authors, start=1):
        author.setdefault("id", f"csag:author/{document_id}/AU{index:04d}")
    return authors


def _strip_references(markdown: str) -> str:
    """Drop a trailing references/bibliography section so cited DOIs are not mistaken for the paper's own."""
    lines = markdown.splitlines()
    for index, line in enumerate(lines):
        if re.match(r"^#{1,6}\s*(references|bibliography|works cited|literature cited)\b", line.strip(), re.IGNORECASE):
            return "\n".join(lines[:index])
    return markdown


def _identifiers(article: dict, markdown: str) -> tuple[str, str]:
    """Resolve (doi, pmid), preferring explicit article fields over scanned body text.

    Body scanning is limited to the title/abstract and the pre-references Markdown so a
    cited reference DOI/PMID is not promoted to the document's own identifier.
    """
    doi = str(article.get("doi") or "").strip()
    pmid = str(article.get("pmid") or "").strip()
    if doi and pmid:
        return doi, pmid
    header = "\n".join([str(article.get("title") or ""), str(article.get("abstract") or ""), _strip_references(markdown)])
    if not doi:
        match = DOI_RE.search(header)
        doi = match.group(0) if match else ""
    if not pmid:
        match = PMID_RE.search(header)
        pmid = match.group(1) if match else ""
    return doi, pmid


def build_scaffold(markdown_path: Path, article_json_path: Path | None = None, *, profile: str = "lite") -> dict:
    markdown_path = markdown_path.expanduser().resolve()
    markdown = markdown_path.read_text(encoding="utf-8")
    article = {}
    if article_json_path:
        article_json_path = article_json_path.expanduser().resolve()
        article = json.loads(article_json_path.read_text(encoding="utf-8"))
    title = str(article.get("title") or _title_from_markdown(markdown, markdown_path.stem))
    doi, pmid = _identifiers(article, markdown)
    if pmid:
        doc_id = f"pmid:{pmid}"
    elif doi:
        doc_id = f"doi:{doi}"
    else:
        doc_id = f"csag:doc/{_slug(title)}"
    ns_doc = doc_id
    context_id = f"csag:context/{ns_doc}/C0001"
    evidence_context_id = f"csag:context/{ns_doc}/C0002"
    assertion_id = f"csag:assertion/{ns_doc}/A0001"
    evidence_id = f"csag:evidence/{ns_doc}/E0001"
    link_id = f"csag:elink/{ns_doc}/L0001"
    activity_id = f"csag:activity/{ns_doc}/ACT0001"
    assertion_span_id = f"csag:span/{ns_doc}/S0001"
    evidence_span_id = f"csag:span/{ns_doc}/S0002"
    abstract = str(article.get("abstract") or "")
    markdown_body = _body_text(markdown)
    assertion_sentence = _first_sentence(_body_text(abstract) or markdown_body, f"TODO: curate the central claim for {title}.")
    evidence_sentence = _first_sentence(_body_text(str(article.get("main") or "")) or _body_text(abstract) or markdown_body, assertion_sentence)
    # Ground the central Lite assertion/evidence; fall back to the first Markdown body
    # sentence so the lite profile (which requires source spans) always passes.
    assertion_spans = _span(markdown, assertion_sentence, doc_id, assertion_span_id, "abstract") or _span(markdown, _first_sentence(markdown_body, ""), doc_id, assertion_span_id, "other")
    evidence_spans = _span(markdown, evidence_sentence, doc_id, evidence_span_id, "other")
    if not evidence_spans and assertion_spans:
        evidence_spans = [{**assertion_spans[0], "id": evidence_span_id}]
    context = {"id": context_id, "label": "TODO: broad source context", "context_facet": "other"}
    evidence_context = {"id": evidence_context_id, "label": "TODO: broad source context", "context_facet": "other"}
    extraction = {
        "id": doc_id,
        "title": title,
        "schema_version": "1.0.0",
        "validator_version": "1.0.0",
        "doi": doi,
        "pmid": pmid,
        "authors": _authors(article.get("authors"), doc_id),
        "abstract": abstract,
        "artifacts": [],
        "datasets": [],
        "entities": [],
        "studies": [],
        "assertions": [
            {
                "id": assertion_id,
                "assertion_text": assertion_sentence,
                "claim_role": "objective",
                "normalization_status": "raw",
                "contexts": [context],
                "text_spans": assertion_spans,
                "notes": "TODO: replace this draft assertion with a curator-confirmed claim.",
            }
        ],
        "evidence_items": [
            {
                "id": evidence_id,
                "evidence_type": "other",
                "evidence_text": evidence_sentence,
                "contexts": [evidence_context],
                "text_spans": evidence_spans,
                "notes": "TODO: replace this draft evidence with the decisive source observation or analysis.",
            }
        ],
        "evidence_links": [
            {
                "id": link_id,
                "evidence_item": evidence_id,
                "assertion": assertion_id,
                "polarity": "supports",
                "strength": "unknown",
                "rationale": "TODO: curator must confirm polarity and strength.",
            }
        ],
        "inferences": [],
        "assertion_relations": [],
        "critiques": [],
        "knowledge_gaps": [],
        "qa_items": [],
        "extraction_activities": [
            {
                "id": activity_id,
                "activity_type": "scaffold",
                "tool_name": "csag scaffold",
                "run_datetime": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "parameters": [
                    {"key": "profile", "value": profile},
                    {"key": "doi_status", "value": "resolved" if doi else "unresolved"},
                    {"key": "pmid_status", "value": "resolved" if pmid else "unresolved"},
                ],
            }
        ],
        "notes": "Draft scaffold: replace TODO fields before using this extraction as curated evidence.",
    }
    return extraction


def scaffold_extraction(markdown_path: Path, *, article_json: Path | None = None, output: Path | None = None, profile: str = "lite") -> CommandResult:
    try:
        extraction = build_scaffold(markdown_path, article_json, profile=profile)
        output_path = output.expanduser().resolve() if output else None
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(extraction, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return CommandResult(True, 0, report_path=output_path, data=extraction, stdout=(json.dumps(extraction, indent=2) + "\n" if not output_path else f"wrote {output_path}\n"))
    except Exception as exc:
        return CommandResult(False, 1, stderr=f"ERROR: {exc}\n")
