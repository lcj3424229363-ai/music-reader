from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from music21 import chord, converter, key, meter, note, stream

# 把项目根目录加到 sys.path, 让 from theory import ... 能找到
_PROJECT_ROOT = Path(__file__).parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from theory import analyze_score as _theory_analyze_score  # noqa: E402


SUPPORTED_EXTENSIONS = {".musicxml", ".xml", ".mxl", ".mid", ".midi"}


def read_score(path: str | Path) -> dict[str, Any]:
    score_path = Path(path)
    if not score_path.exists():
        raise FileNotFoundError(f"Score file not found: {score_path}")

    extension = score_path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported score type: {extension}")

    parsed = converter.parse(str(score_path))
    score = _ensure_score(parsed)
    parts = list(score.parts)

    analysis_key = _analyze_key(score)
    part_results = [_read_part(part, index) for index, part in enumerate(parts, start=1)]

    # ---- 斯波索宾和声分析(替代原来的字面 chordify) ----
    theory_result = _theory_analyze_score(score)
    harmony_timeline = _build_harmony_timeline(theory_result)

    warnings = _collect_warnings(part_results, harmony_timeline)

    return {
        "source": {
            "fileName": score_path.name,
            "extension": extension,
            "path": str(score_path.resolve()),
        },
        "summary": {
            "partCount": len(parts),
            "measureCount": max((part["measureCount"] for part in part_results), default=0),
            "analyzedKey": analysis_key,
            "theory": {
                "key": theory_result.get("key", {}),
                "cadences": theory_result.get("cadences", []),
                "tonicizations": theory_result.get("tonicizations", []),
                "modulations": theory_result.get("modulations", []),
            },
            "status": "readable" if not warnings else "readable_with_warnings",
        },
        "parts": part_results,
        "harmonyTimeline": harmony_timeline,
        "warnings": warnings,
    }


def _build_harmony_timeline(theory_result: dict) -> list[dict]:
    """把 theory.analyze_score 的输出翻译成 harmonyTimeline (前端的旧结构 + 新字段)。"""
    timeline = []
    for m in theory_result.get("harmonyByMeasure", []):
        harmonies = []
        for ch in m.get("chords", []):
            a = ch.get("analysis", {}) or {}
            harmonies.append({
                "offset": ch.get("beat", 1.0),
                "duration": ch.get("duration", 0.0),
                "pitches": ch.get("pitches", []),
                "pitchClasses": ch.get("pitchClasses", []),
                "commonName": a.get("qualityZh", "未知"),
                "root": ch.get("pitches", [None])[0] if ch.get("pitches") else None,
                # 斯波索宾扩展字段
                "figure": a.get("figure", "?"),
                "figureWithInversion": a.get("figureWithInversion", a.get("figure", "?")),
                "function": a.get("function"),         # T / S / D
                "role": a.get("role"),                 # primary / extension / borrowed / applied / ...
                "scaleDegree": a.get("scaleDegree"),
                "quality": a.get("quality"),
                "qualityZh": a.get("qualityZh"),
                "inversion": a.get("inversion", ""),
                "isSeventh": a.get("isSeventh", False),
                "isSecondary": a.get("isSecondary", False),
                "secondaryOf": a.get("secondaryOf"),
                "secondaryTargetKey": a.get("secondaryTargetKey"),
                "isBorrowed": a.get("isBorrowed", False),
                "confidence": a.get("confidence", "low"),
            })
        timeline.append({
            "measure": m.get("measure"),
            "timeSignature": m.get("ts"),
            "harmonies": harmonies,
        })
    return timeline


def _ensure_score(parsed: stream.Stream) -> stream.Score:
    if isinstance(parsed, stream.Score):
        return parsed

    score = stream.Score()
    if isinstance(parsed, stream.Part):
        score.insert(0, parsed)
    else:
        part = stream.Part()
        for element in parsed:
            part.insert(element.offset, element)
        score.insert(0, part)
    return score


def _analyze_key(score: stream.Score) -> dict[str, Any]:
    try:
        analyzed = score.analyze("key")
        if isinstance(analyzed, key.Key):
            return {
                "name": analyzed.tonic.name,
                "mode": analyzed.mode,
                "label": f"{analyzed.tonic.name} {analyzed.mode}",
                "correlation": round(float(getattr(analyzed, "correlationCoefficient", 0.0)), 4),
            }
    except Exception as exc:
        return {"label": "unknown", "error": str(exc)}
    return {"label": "unknown"}


def _read_part(part: stream.Part, index: int) -> dict[str, Any]:
    measures = list(part.getElementsByClass(stream.Measure))
    part_name = part.partName or part.partAbbreviation or f"Part {index}"
    measure_results = [_read_measure(measure) for measure in measures]

    return {
        "index": index,
        "id": part.id,
        "name": part_name,
        "measureCount": len(measure_results),
        "measures": measure_results,
    }


def _read_measure(measure: stream.Measure) -> dict[str, Any]:
    time_signature = _active_time_signature(measure)
    key_signature = _active_key_signature(measure)
    events = []

    for element in measure.recurse().notesAndRests:
        if isinstance(element, note.Rest):
            events.append(_rest_event(element, measure))
        elif isinstance(element, note.Note):
            events.append(_note_event(element, measure))
        elif isinstance(element, chord.Chord):
            events.append(_chord_event(element, measure))

    expected_quarters = _expected_quarter_length(time_signature)
    actual_quarters = _measure_actual_quarter_length(measure)
    local_warnings = []
    if expected_quarters is not None and actual_quarters is not None:
        if abs(actual_quarters - expected_quarters) > 0.001:
            local_warnings.append(
                f"Measure duration is {actual_quarters:g} quarter lengths, expected {expected_quarters:g}."
            )

    return {
        "number": measure.measureNumber,
        "offset": _round_float(measure.offset),
        "timeSignature": time_signature,
        "keySignature": key_signature,
        "expectedQuarterLength": expected_quarters,
        "actualQuarterLength": actual_quarters,
        "eventCount": len(events),
        "events": events,
        "warnings": local_warnings,
    }


def _active_time_signature(measure: stream.Measure) -> dict[str, Any] | None:
    ts = measure.getTimeSignatures(returnDefault=False)
    if ts:
        active = ts[0]
    else:
        active = measure.getContextByClass(meter.TimeSignature)

    if not active:
        return None
    return {
        "ratio": active.ratioString,
        "barDurationQuarterLength": _round_float(active.barDuration.quarterLength),
    }


def _active_key_signature(measure: stream.Measure) -> dict[str, Any] | None:
    signatures = list(measure.getElementsByClass(key.KeySignature))
    active = signatures[0] if signatures else measure.getContextByClass(key.KeySignature)
    if not active:
        return None

    return {
        "sharps": active.sharps,
        "majorName": active.asKey("major").name,
        "minorName": active.asKey("minor").name,
    }


def _note_event(element: note.Note, measure: stream.Measure) -> dict[str, Any]:
    return {
        "type": "note",
        "offset": _round_float(element.getOffsetInHierarchy(measure)),
        "duration": _round_float(element.duration.quarterLength),
        "pitch": element.pitch.nameWithOctave,
        "pitchClass": element.pitch.pitchClass,
    }


def _rest_event(element: note.Rest, measure: stream.Measure) -> dict[str, Any]:
    return {
        "type": "rest",
        "offset": _round_float(element.getOffsetInHierarchy(measure)),
        "duration": _round_float(element.duration.quarterLength),
    }


def _chord_event(element: chord.Chord, measure: stream.Measure) -> dict[str, Any]:
    return {
        "type": "chord",
        "offset": _round_float(element.getOffsetInHierarchy(measure)),
        "duration": _round_float(element.duration.quarterLength),
        "pitches": [pitch.nameWithOctave for pitch in element.pitches],
        "pitchClasses": sorted(set(pitch.pitchClass for pitch in element.pitches)),
        "commonName": _safe_common_name(element),
        "root": _safe_root(element),
    }


def _read_chordified_harmony(score: stream.Score) -> list[dict[str, Any]]:
    try:
        chordified = score.chordify()
    except Exception:
        return []

    measures = list(chordified.getElementsByClass(stream.Measure))
    result = []

    for measure in measures:
        harmonies = []
        for element in measure.recurse().notes:
            if isinstance(element, chord.Chord):
                harmonies.append(
                    {
                        "offset": _round_float(element.getOffsetInHierarchy(measure)),
                        "duration": _round_float(element.duration.quarterLength),
                        "pitches": [pitch.nameWithOctave for pitch in element.pitches],
                        "pitchClasses": sorted(set(pitch.pitchClass for pitch in element.pitches)),
                        "commonName": _safe_common_name(element),
                        "root": _safe_root(element),
                    }
                )
            elif isinstance(element, note.Note):
                harmonies.append(
                    {
                        "offset": _round_float(element.getOffsetInHierarchy(measure)),
                        "duration": _round_float(element.duration.quarterLength),
                        "pitches": [element.pitch.nameWithOctave],
                        "pitchClasses": [element.pitch.pitchClass],
                        "commonName": "single note",
                        "root": element.pitch.name,
                    }
                )

        result.append(
            {
                "measure": measure.measureNumber,
                "harmonies": harmonies,
            }
        )

    return result


def _collect_warnings(part_results: list[dict[str, Any]], harmony_timeline: list[dict[str, Any]]) -> list[str]:
    warnings = []
    if not part_results:
        warnings.append("No parts were found in the score.")

    if not harmony_timeline:
        warnings.append("Chordified harmony timeline could not be generated.")

    for part in part_results:
        for measure in part["measures"]:
            for local_warning in measure["warnings"]:
                warnings.append(f"{part['name']} measure {measure['number']}: {local_warning}")

    return warnings


def _expected_quarter_length(time_signature: dict[str, Any] | None) -> float | None:
    if not time_signature:
        return None
    return time_signature["barDurationQuarterLength"]


def _measure_actual_quarter_length(measure: stream.Measure) -> float | None:
    try:
        return _round_float(measure.duration.quarterLength)
    except Exception:
        return None


def _safe_common_name(element: chord.Chord) -> str:
    try:
        return element.commonName
    except Exception:
        return "unknown chord"


def _safe_root(element: chord.Chord) -> str | None:
    try:
        root = element.root()
        return root.name if root else None
    except Exception:
        return None


def _round_float(value: Any) -> float:
    return round(float(value), 4)


def _format_pretty(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        f"文件：{result['source']['fileName']}",
        f"状态：{summary['status']}",
        f"声部：{summary['partCount']}，小节：{summary['measureCount']}",
        f"推测调性：{summary['analyzedKey'].get('label', 'unknown')}",
        "",
        "声部与小节：",
    ]

    for part in result["parts"]:
        lines.append(f"- {part['name']}：{part['measureCount']} 小节")
        for measure in part["measures"][:8]:
            ts = measure["timeSignature"]["ratio"] if measure["timeSignature"] else "unknown"
            ks = measure["keySignature"]["majorName"] if measure["keySignature"] else "unknown"
            preview = _event_preview(measure["events"])
            lines.append(f"  第 {measure['number']} 小节 | {ts} | 调号参考 {ks} | {preview}")
        if part["measureCount"] > 8:
            lines.append("  ...")

    lines.append("")
    lines.append("纵向和声音响：")
    for item in result["harmonyTimeline"][:8]:
        preview = []
        for harmony in item["harmonies"][:4]:
            name = harmony["commonName"]
            root = harmony.get("root") or "?"
            preview.append(f"{root}: {name}")
        lines.append(f"- 第 {item['measure']} 小节：{'; '.join(preview) if preview else '无'}")

    if result["warnings"]:
        lines.append("")
        lines.append("警告：")
        lines.extend(f"- {warning}" for warning in result["warnings"])

    return "\n".join(lines)


def _event_preview(events: list[dict[str, Any]]) -> str:
    if not events:
        return "无事件"
    labels = []
    for event in events[:6]:
        if event["type"] == "note":
            labels.append(event["pitch"])
        elif event["type"] == "chord":
            labels.append("+".join(event["pitches"]))
        else:
            labels.append("rest")
    suffix = " ..." if len(events) > 6 else ""
    return ", ".join(labels) + suffix


def main() -> None:
    parser = argparse.ArgumentParser(description="Read MusicXML/MIDI and emit structured score data.")
    parser.add_argument("score", help="Path to a MusicXML, MXL, XML, MIDI, or MID file.")
    parser.add_argument("--pretty", action="store_true", help="Print a human-readable summary.")
    args = parser.parse_args()

    result = read_score(args.score)
    if args.pretty:
        print(_format_pretty(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

