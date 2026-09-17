"""Helpers for routing bounded MusicXML regions to visual review."""
from __future__ import annotations

import io
import json
import math
import hashlib
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path
from typing import Any

from PIL import Image


MODEL_RHYTHM_REVIEW_THRESHOLD = 0.895


def _canonical_correction(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def save_review_run(
    root: Path,
    run_id: str,
    image_bytes: bytes,
    image_suffix: str,
    homr_musicxml: str,
    record: dict[str, Any],
    artifacts: dict[str, bytes] | None = None,
) -> Path:
    """Persist the four artifacts needed for later evaluation or fine-tuning."""
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / f"source{image_suffix}").write_bytes(image_bytes)
    (run_dir / "homr.musicxml").write_text(homr_musicxml, encoding="utf-8")
    artifact_names: list[str] = []
    for relative_name, payload in sorted((artifacts or {}).items()):
        relative_path = Path(relative_name)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError(f"Unsafe OMR review artifact path: {relative_name}")
        target = run_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        artifact_names.append(relative_path.as_posix())
    record = {
        **record,
        "runId": run_id,
        "sourceSha256": hashlib.sha256(image_bytes).hexdigest(),
        "reviewArtifacts": artifact_names,
        "humanFinalAvailable": False,
    }
    (run_dir / "review.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return run_dir


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _child(element: ET.Element, name: str) -> ET.Element | None:
    return next((item for item in element if _tag(item) == name), None)


def _text(element: ET.Element, name: str, default: str = "") -> str:
    item = _child(element, name)
    return (item.text or default).strip() if item is not None else default


def summarize_recognition_confidence(pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize model uncertainty without treating softmax as correctness."""
    systems = []
    for page in pages:
        confidence = page.get("recognitionConfidence") or {}
        for system in confidence.get("systems", []) or []:
            rhythm = (system.get("branches") or {}).get("rhythm") or {}
            mean = rhythm.get("mean")
            if not isinstance(mean, (int, float)):
                continue
            systems.append({
                "page": int(page.get("page") or 1),
                "system": int(system.get("index") or 0),
                "rhythmMean": float(mean),
                "reviewRecommended": mean < MODEL_RHYTHM_REVIEW_THRESHOLD,
            })
    flagged = [system for system in systems if system["reviewRecommended"]]
    return {
        "available": bool(systems),
        "status": "review" if flagged else "model-stable" if systems else "unavailable",
        "threshold": MODEL_RHYTHM_REVIEW_THRESHOLD,
        "systems": systems,
        "reviewSystemCount": len(flagged),
        "limitations": [
            "Decoder probability measures model uncertainty, not transcription correctness.",
            "High-confidence context and notation errors still require sentinel review.",
        ],
    }


def assess_omr_readiness(
    quality: dict[str, Any],
    confidence: dict[str, Any],
    vision: dict[str, Any],
) -> dict[str, Any]:
    """Gate solver use on known OMR risks without claiming visual correctness."""
    issues = []
    confirmed_corrections = {
        _canonical_correction(item)
        for item in (vision.get("confirmedCorrections", []) or [])
        if isinstance(item, dict)
    }
    if quality.get("status") == "invalid":
        issues.append({"code": "OMR_STRUCTURE_INVALID", "message": "MusicXML structure is invalid."})
    elif quality.get("reviewRequired"):
        issues.append({"code": "OMR_STRUCTURE_REVIEW", "message": "MusicXML structure needs review."})
    if not confidence.get("available"):
        issues.append({
            "code": "OMR_CONFIDENCE_UNAVAILABLE",
            "message": "HOMR decoder confidence diagnostics are unavailable.",
        })
    if confidence.get("status") == "review" and not vision.get("enabled"):
        issues.append({
            "code": "OMR_MODEL_UNCERTAINTY",
            "message": "Low-confidence recognition has not been visually reviewed.",
        })
    if vision.get("errors"):
        issues.append({"code": "OMR_VISION_ERROR", "message": "One or more visual reviews failed."})
    for region in vision.get("reviewedRegions", []) or []:
        final = (region.get("review") or {}).get("final") or {}
        validator = final.get("validator") or {}
        if not validator.get("accepted") or final.get("decision") == "uncertain":
            issues.append({
                "code": "OMR_VISION_UNRESOLVED",
                "message": f"Visual review for measure {region.get('measure')} is unresolved.",
                "measure": region.get("measure"),
            })
        elif final.get("decision") == "replace_candidate":
            proposed = [
                correction for correction in (final.get("corrections", []) or [])
                if isinstance(correction, dict)
            ]
            if not proposed or any(
                _canonical_correction(correction) not in confirmed_corrections
                for correction in proposed
            ):
                issues.append({
                    "code": "OMR_CORRECTION_PENDING",
                    "message": f"Measure {region.get('measure')} has corrections awaiting confirmation.",
                    "measure": region.get("measure"),
                })
    blocking_codes = sorted({issue["code"] for issue in issues})
    return {
        "status": "needs-review" if issues else "provisional",
        "solverAllowed": not issues,
        "issues": issues,
        "blockingCodes": blocking_codes,
        "limitations": [
            "Provisional means no known blocker; it does not prove transcription correctness."
        ],
    }


def _confidence_review_measures(pages: list[dict[str, Any]]) -> list[int]:
    measures = []
    offset = 0
    for page in pages:
        count = max(0, int(page.get("measureCount") or 0))
        confidence = page.get("recognitionConfidence") or {}
        systems = confidence.get("systems", []) or []
        system_count = max(1, len(systems))
        for system in systems:
            branches = system.get("branches") or {}
            rhythm_mean = (branches.get("rhythm") or {}).get("mean")
            if not isinstance(rhythm_mean, (int, float)) or rhythm_mean >= MODEL_RHYTHM_REVIEW_THRESHOLD:
                continue
            system_index = max(0, min(int(system.get("index") or 0), system_count - 1))
            start = system_index * count // system_count + 1
            end = max(start, (system_index + 1) * count // system_count)
            measure = offset + (start + end) // 2
            if measure not in measures:
                measures.append(measure)
        offset += count
    return measures


def select_review_measures(
    audit: dict[str, Any], maximum: int, pages: list[dict[str, Any]] | None = None,
) -> list[int]:
    maximum = max(0, min(maximum, 8))
    count = int(audit.get("stats", {}).get("measureCount") or 0)
    flagged = []
    for value in audit.get("flaggedMeasures", []):
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= number <= count and number not in flagged:
            flagged.append(number)
    if len(flagged) >= maximum or count <= 0:
        return flagged[:maximum]
    for number in _confidence_review_measures(pages or []):
        if 1 <= number <= count and number not in flagged:
            flagged.append(number)
        if len(flagged) >= maximum:
            return flagged
    # Structural checks cannot detect every wrong pitch. Sample the page at
    # evenly spaced sentinel measures so clean-looking XML is still audited.
    sentinels = [1, max(1, math.ceil(count / 2)), count]
    for number in sentinels:
        if number not in flagged:
            flagged.append(number)
        if len(flagged) >= maximum:
            break
    return flagged


def extract_measure_candidate(path: str | Path, measure_number: int) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    parts = [item for item in root if _tag(item) == "part"]
    result: list[dict[str, Any]] = []
    tracks: list[tuple[int, str, str]] = []
    for part_index, part in enumerate(parts, start=1):
        measures = [item for item in part if _tag(item) == "measure"]
        if not 1 <= measure_number <= len(measures):
            continue
        measure = measures[measure_number - 1]
        divisions = 1
        for prior in measures[:measure_number]:
            attributes = _child(prior, "attributes")
            if attributes is not None:
                try:
                    divisions = max(1, int(_text(attributes, "divisions", str(divisions))))
                except ValueError:
                    pass
        cursor = Fraction(0)
        previous_onset = Fraction(0)
        grouped: dict[tuple[str, str, Fraction, int, bool], dict[str, Any]] = {}
        for item in measure:
            name = _tag(item)
            if name in {"backup", "forward"}:
                try:
                    duration = int(_text(item, "duration"))
                except ValueError:
                    continue
                cursor += duration * (-1 if name == "backup" else 1)
                continue
            if name != "note" or _child(item, "grace") is not None:
                continue
            try:
                duration = int(_text(item, "duration"))
            except ValueError:
                continue
            onset = previous_onset if _child(item, "chord") is not None else cursor
            if _child(item, "chord") is None:
                previous_onset = onset
                cursor += duration
            pitch = _child(item, "pitch")
            voice = _text(item, "voice", "1")
            staff = _text(item, "staff", "1")
            rest = _child(item, "rest") is not None
            key = (voice, staff, onset, duration, rest)
            value = grouped.setdefault(key, {
                "voice": voice,
                "staff": staff,
                "onsetDivisions": int(onset),
                "durationDivisions": duration,
                "onset": _fraction_text(onset / (divisions * 4)),
                "duration": _fraction_text(Fraction(duration, divisions * 4)),
                "kind": "rest" if rest else "note",
                "pitches": [],
            })
            if pitch is not None:
                value["pitches"].append({
                    "step": _text(pitch, "step"),
                    "alter": int(_text(pitch, "alter", "0")),
                    "octave": int(_text(pitch, "octave", "4")),
                })
            track = (part_index, staff, voice)
            if track not in tracks:
                tracks.append(track)
        result.append({
            "part": part.get("id") or f"P{part_index}",
            "partIndex": part_index,
            "divisions": divisions,
            "events": list(grouped.values()),
        })

    ordered_tracks = sorted(tracks, key=lambda value: (value[0], _sort_number(value[1]), _sort_number(value[2])))
    if len(ordered_tracks) == 1:
        roles = ["soprano"]
    elif len(ordered_tracks) == 2:
        roles = ["soprano", "bass"]
    elif len(ordered_tracks) == 3:
        roles = ["soprano", "alto", "bass"]
    else:
        roles = ["soprano", "alto", "tenor", "bass"]
    role_by_track = dict(zip(ordered_tracks, roles))
    for part in result:
        for event in part["events"]:
            event["role"] = role_by_track.get(
                (part["partIndex"], event["staff"], event["voice"]), "unknown"
            )
    return {"measure": measure_number, "timeUnit": "whole-note", "parts": result}


def _fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _sort_number(value: str) -> tuple[int, int | str]:
    try:
        return (0, int(value))
    except ValueError:
        return (1, value)


def crop_measure_region(
    image_bytes: bytes,
    mime_type: str,
    staff_positions: list[dict[str, Any]],
    measure_number: int,
    measure_count: int,
    staves_per_system: int,
) -> tuple[bytes, dict[str, Any]]:
    """Create a conservative crop using HOMR staff boxes plus page position."""
    with Image.open(io.BytesIO(image_bytes)) as image:
        image = image.convert("RGB")
        width, height = image.size
        page_positions = sorted(
            [item for item in staff_positions if item.get("page", 1) == 1],
            key=lambda item: float(item.get("centerY", 0)),
        )
        staves_per_system = max(1, min(staves_per_system or 1, len(page_positions) or 1))
        systems = [
            page_positions[index:index + staves_per_system]
            for index in range(0, len(page_positions), staves_per_system)
        ] or [[]]
        measures_per_system = max(1, math.ceil(max(measure_count, 1) / len(systems)))
        system_index = min((measure_number - 1) // measures_per_system, len(systems) - 1)
        local_index = (measure_number - 1) % measures_per_system
        system = systems[system_index]
        if system:
            left = min((item["centerX"] - item["width"] / 2) * width for item in system)
            right = max((item["centerX"] + item["width"] / 2) * width for item in system)
            top = min((item["centerY"] - item["height"] / 2) * height for item in system)
            bottom = max((item["centerY"] + item["height"] / 2) * height for item in system)
        else:
            left, right, top, bottom = 0, width, 0, height
        slot_width = (right - left) / measures_per_system
        margin_x = max(20, slot_width * 0.12)
        margin_y = max(24, (bottom - top) * 0.12)
        box = (
            max(0, int(left + local_index * slot_width - margin_x)),
            max(0, int(top - margin_y)),
            min(width, int(left + (local_index + 1) * slot_width + margin_x)),
            min(height, int(bottom + margin_y)),
        )
        crop = image.crop(box)
        output = io.BytesIO()
        crop.save(output, format="PNG", optimize=True)
    return output.getvalue(), {
        "box": list(box), "width": crop.width, "height": crop.height,
        "mappingConfidence": 0.7 if staff_positions else 0.35,
        "method": "homr-staff-box-proportional-measure",
        "systemIndex": system_index,
        "systemCount": len(systems),
        "measureSlot": local_index,
        "mimeType": "image/png",
    }


def prepend_previous_system_context(
    target_crop_bytes: bytes,
    context_page_bytes: bytes,
    context_staff_positions: list[dict[str, Any]],
    context_system_index: int,
) -> tuple[bytes, dict[str, Any]]:
    """Stack the preceding full system above a target crop for inherited context."""
    positions = sorted(
        context_staff_positions,
        key=lambda item: float(item.get("centerY", 0)),
    )
    if not positions or not 0 <= context_system_index < len(positions):
        return target_crop_bytes, {"included": False}
    with Image.open(io.BytesIO(context_page_bytes)) as source:
        source = source.convert("RGB")
        width, height = source.size
        position = positions[context_system_index]
        left = (float(position["centerX"]) - float(position["width"]) / 2) * width
        right = (float(position["centerX"]) + float(position["width"]) / 2) * width
        top = (float(position["centerY"]) - float(position["height"]) / 2) * height
        bottom = (float(position["centerY"]) + float(position["height"]) / 2) * height
        margin_x = max(20, (right - left) * 0.03)
        margin_y = max(24, (bottom - top) * 0.12)
        box = (
            max(0, int(left - margin_x)),
            max(0, int(top - margin_y)),
            min(width, int(right + margin_x)),
            min(height, int(bottom + margin_y)),
        )
        context_crop = source.crop(box)
    with Image.open(io.BytesIO(target_crop_bytes)) as target:
        target = target.convert("RGB")
        output_width = max(context_crop.width, target.width)
        separator = 16
        target_left = (output_width - target.width) // 2
        target_top = context_crop.height + separator
        combined = Image.new(
            "RGB", (output_width, context_crop.height + separator + target.height), "white"
        )
        combined.paste(context_crop, ((output_width - context_crop.width) // 2, 0))
        combined.paste(target, (target_left, target_top))
        output = io.BytesIO()
        combined.save(output, format="PNG", optimize=True)
    return output.getvalue(), {
        "included": True,
        "layout": "previous-system-above-target-crop",
        "contextSystemIndex": context_system_index,
        "contextBox": list(box),
        "targetBox": [
            target_left, target_top,
            target_left + target.width, target_top + target.height,
        ],
        "width": combined.width,
        "height": combined.height,
    }
