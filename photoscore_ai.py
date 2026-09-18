"""PhotoScore MusicXML -> compact AI-readable analysis context.

PhotoScore is a strong interactive OMR front-end, but its raw MusicXML is too
large and too low-level to send directly to an AI analysis step.  This module
turns exported MusicXML into a bounded summary that preserves musical facts:
metadata, OMR quality risks, per-part measure previews, harmonic timeline, and
review targets.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from musicxml_quality import audit_musicxml
from reader import read_score


DEFAULT_MEASURE_LIMIT = 32
DEFAULT_EVENTS_PER_MEASURE = 12
DEFAULT_HARMONIES_PER_MEASURE = 6


def build_photoscore_ai_context(
    path: str | Path,
    *,
    measure_limit: int = DEFAULT_MEASURE_LIMIT,
    events_per_measure: int = DEFAULT_EVENTS_PER_MEASURE,
    harmonies_per_measure: int = DEFAULT_HARMONIES_PER_MEASURE,
) -> dict[str, Any]:
    """Return a compact, LLM-oriented payload for a PhotoScore MusicXML export."""
    source = Path(path)
    reader_payload = read_score(source)
    quality = audit_musicxml(source)
    summary = reader_payload.get("summary", {}) or {}
    parts = reader_payload.get("parts", []) or []
    harmony_timeline = reader_payload.get("harmonyTimeline", []) or []
    warnings = reader_payload.get("warnings", []) or []

    compact_parts = [
        _compact_part(part, measure_limit, events_per_measure)
        for part in parts
    ]
    compact_harmony = [
        _compact_harmony_measure(item, harmonies_per_measure)
        for item in harmony_timeline[:measure_limit]
    ]
    review_targets = _review_targets(quality, limit=24)

    context = {
        "source": {
            "fileName": source.name,
            "format": source.suffix.lower().lstrip("."),
            "recognitionEngine": _recognition_engine(reader_payload),
        },
        "summary": {
            "partCount": summary.get("partCount"),
            "measureCount": summary.get("measureCount"),
            "analyzedKey": summary.get("analyzedKey"),
            "theory": summary.get("theory"),
            "readerStatus": summary.get("status"),
        },
        "quality": {
            "status": quality.get("status"),
            "score": quality.get("score"),
            "reviewRequired": quality.get("reviewRequired"),
            "stats": quality.get("stats"),
            "issueCounts": _issue_counts(quality.get("issues", []) or []),
            "reviewTargets": review_targets,
        },
        "parts": compact_parts,
        "harmonyTimeline": compact_harmony,
        "readerWarnings": warnings[:24],
        "aiInstructions": [
            "Treat this as an OMR-derived score, not ground truth.",
            "Base analysis on the compact parts and harmony timeline.",
            "Call out reviewTargets before making strong claims about those measures.",
            "Ignore garbled title/composer text unless verified by the user.",
        ],
    }
    context["markdown"] = render_ai_context_markdown(context)
    return context


def _recognition_engine(reader_payload: dict[str, Any]) -> str:
    source = reader_payload.get("source", {}) or {}
    name = str(source.get("fileName") or "").lower()
    if "photoscore" in json.dumps(reader_payload.get("source", {}), ensure_ascii=False).lower():
        return "PhotoScore"
    # PhotoScore writes the actual software marker in the XML, but reader.py
    # intentionally abstracts that away.  For this dedicated entrypoint the
    # engine is named by workflow.
    return "PhotoScore" if name.endswith((".xml", ".musicxml", ".mxl")) else "unknown"


def _compact_part(part: dict[str, Any], measure_limit: int, events_per_measure: int) -> dict[str, Any]:
    measures = part.get("measures", []) or []
    return {
        "index": part.get("index"),
        "id": part.get("id"),
        "name": part.get("name"),
        "staffNumber": part.get("staffNumber"),
        "measureCount": part.get("measureCount"),
        "measures": [
            _compact_measure(measure, events_per_measure)
            for measure in measures[:measure_limit]
        ],
        "truncated": len(measures) > measure_limit,
    }


def _compact_measure(measure: dict[str, Any], events_per_measure: int) -> dict[str, Any]:
    events = measure.get("events", []) or []
    return {
        "number": measure.get("number"),
        "timeSignature": (measure.get("timeSignature") or {}).get("ratio"),
        "keySignature": _key_label(measure.get("keySignature")),
        "clef": (measure.get("clef") or {}).get("name"),
        "expected": measure.get("expectedQuarterFraction"),
        "actual": measure.get("actualQuarterFraction"),
        "events": [_compact_event(event) for event in events[:events_per_measure]],
        "eventCount": len(events),
        "truncated": len(events) > events_per_measure,
        "warnings": measure.get("warnings", []) or [],
    }


def _key_label(key_signature: dict[str, Any] | None) -> str | None:
    if not key_signature:
        return None
    declared = key_signature.get("declaredLabel")
    if declared:
        return declared
    return f"{key_signature.get('majorName')} / {key_signature.get('minorName')}"


def _compact_event(event: dict[str, Any]) -> dict[str, Any]:
    base = {
        "at": event.get("offsetFraction"),
        "dur": event.get("durationFraction"),
        "voice": event.get("voice"),
        "staff": event.get("staff"),
    }
    event_type = event.get("type")
    if event_type == "note":
        base.update({"type": "note", "pitch": event.get("pitch")})
    elif event_type == "chord":
        base.update({"type": "chord", "pitches": event.get("pitches")})
    elif event_type == "rest":
        base.update({"type": "rest"})
    else:
        base.update({"type": event_type or "unknown"})
    return {key: value for key, value in base.items() if value not in (None, [], "")}


def _compact_harmony_measure(item: dict[str, Any], limit: int) -> dict[str, Any]:
    harmonies = item.get("harmonies", []) or []
    return {
        "measure": item.get("measure"),
        "timeSignature": item.get("timeSignature"),
        "harmonies": [
            {
                "at": harmony.get("offset"),
                "dur": harmony.get("duration"),
                "figure": harmony.get("figureWithInversion") or harmony.get("figure"),
                "function": harmony.get("function"),
                "role": harmony.get("role"),
                "root": harmony.get("root"),
                "quality": harmony.get("qualityZh") or harmony.get("quality"),
                "confidence": harmony.get("confidence"),
                "pitches": harmony.get("pitches"),
            }
            for harmony in harmonies[:limit]
        ],
        "truncated": len(harmonies) > limit,
    }


def _review_targets(quality: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
    targets = []
    seen = set()
    for issue in quality.get("issues", []) or []:
        key = (issue.get("part"), str(issue.get("measure")), issue.get("code"))
        if key in seen:
            continue
        seen.add(key)
        targets.append({
            "part": issue.get("part"),
            "measure": issue.get("measure"),
            "code": issue.get("code"),
            "severity": issue.get("severity"),
            "message": issue.get("message"),
        })
        if len(targets) >= limit:
            break
    return targets


def _issue_counts(issues: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in issues:
        severity = str(issue.get("severity") or "unknown")
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def render_ai_context_markdown(context: dict[str, Any]) -> str:
    """Render a concise prompt-ready representation of the context payload."""
    summary = context.get("summary", {}) or {}
    quality = context.get("quality", {}) or {}
    analyzed_key = summary.get("analyzedKey") or {}
    lines = [
        "# PhotoScore MusicXML Analysis Context",
        "",
        f"- Source: {context.get('source', {}).get('fileName')}",
        f"- Engine: {context.get('source', {}).get('recognitionEngine')}",
        f"- Parts: {summary.get('partCount')}, measures: {summary.get('measureCount')}",
        f"- Estimated key: {analyzed_key.get('label', 'unknown')}",
        f"- Quality: {quality.get('status')} / reviewRequired={quality.get('reviewRequired')}",
    ]

    issue_counts = quality.get("issueCounts") or {}
    if issue_counts:
        lines.append(f"- Quality issue counts: {issue_counts}")

    review_targets = quality.get("reviewTargets") or []
    if review_targets:
        lines.extend(["", "## Review Targets"])
        for item in review_targets[:12]:
            lines.append(
                f"- {item.get('part')} m.{item.get('measure')}: "
                f"{item.get('code')} ({item.get('severity')})"
            )

    lines.extend(["", "## Parts"])
    for part in context.get("parts", []) or []:
        lines.append(f"### {part.get('name') or part.get('id')}")
        for measure in (part.get("measures") or [])[:8]:
            events = []
            for event in measure.get("events", [])[:8]:
                label = event.get("pitch") or "+".join(event.get("pitches", []) or []) or "R"
                events.append(f"{event.get('at')}:{label}/{event.get('dur')}")
            lines.append(
                f"- m.{measure.get('number')} {measure.get('timeSignature') or '?'} "
                f"{measure.get('keySignature') or ''}: "
                f"{'; '.join(events) if events else 'empty'}"
            )
        if part.get("truncated"):
            lines.append("- ...")

    lines.extend(["", "## Harmony Timeline"])
    for item in (context.get("harmonyTimeline") or [])[:16]:
        cells = []
        for harmony in item.get("harmonies", [])[:4]:
            figure = harmony.get("figure") or "?"
            function = harmony.get("function") or "?"
            root = harmony.get("root") or "?"
            cells.append(f"{harmony.get('at')}: {figure}/{function}/{root}")
        lines.append(f"- m.{item.get('measure')}: {'; '.join(cells) if cells else 'none'}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build AI context from PhotoScore MusicXML.")
    parser.add_argument("path", help="PhotoScore-exported .xml/.musicxml/.mxl file")
    parser.add_argument("--pretty", action="store_true", help="Print Markdown instead of JSON")
    parser.add_argument("--measure-limit", type=int, default=DEFAULT_MEASURE_LIMIT)
    args = parser.parse_args()

    context = build_photoscore_ai_context(args.path, measure_limit=args.measure_limit)
    if args.pretty:
        print(context["markdown"])
    else:
        print(json.dumps(context, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
