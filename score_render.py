"""Render SATB solver answers as visible score images."""
from __future__ import annotations

import io
import math
from html import escape
from typing import Any

from PIL import Image, ImageDraw, ImageFont


VOICE_ORDER = ["soprano", "alto", "tenor", "bass"]
VOICE_LABELS = {
    "soprano": "S",
    "alto": "A",
    "tenor": "T",
    "bass": "B",
}
STAFF_VOICES = {
    "treble": ["soprano", "alto"],
    "bass": ["tenor", "bass"],
}
DURATION_UNITS = {
    "1": 32,
    "2": 16,
    "4": 8,
    "8": 4,
    "16": 2,
    "32": 1,
}
STEP_INDEX = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}


class RenderError(ValueError):
    """Raised when an answer cannot be rendered as notation."""


def answer_to_score_payload(answer: dict[str, Any]) -> dict[str, Any]:
    """Extract the four-part block from an endpoint response."""
    if "answer" in answer and isinstance(answer["answer"], dict):
        answer = answer["answer"]
    if "solution" in answer and isinstance(answer["solution"], dict):
        answer = answer["solution"]
    four_part = answer.get("fourPart") if isinstance(answer, dict) else None
    if not isinstance(four_part, dict):
        raise RenderError("No fourPart answer was found to render.")
    voices = four_part.get("voices") or []
    if not isinstance(voices, list) or len(voices) < 4:
        raise RenderError("The four-part answer does not contain SATB voices.")
    return {
        "title": "Four-Part Answer",
        "timeSignature": four_part.get("timeSignature") or "4/4",
        "voices": voices,
        "harmonies": four_part.get("harmonies") or [],
        "answerContract": four_part.get("answerContract") or {},
    }


def render_answer_svg(answer: dict[str, Any]) -> str:
    payload = answer_to_score_payload(answer)
    layout = _layout(payload)
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout["width"]}" height="{layout["height"]}" viewBox="0 0 {layout["width"]} {layout["height"]}">',
        '<rect width="100%" height="100%" fill="#fffdf8"/>',
        _svg_text(36, 42, payload["title"], 24, "700"),
        _svg_text(36, 70, f'Time: {payload["timeSignature"]}', 14, "400", "#4b5752"),
    ]
    for staff in layout["staves"]:
        elements.extend(_svg_staff(staff, layout))
    for note_item in layout["notes"]:
        elements.extend(_svg_note(note_item))
    for label in layout["harmonyLabels"]:
        elements.append(_svg_text(label["x"], label["y"], label["text"], 12, "400", "#314339"))
    elements.append("</svg>")
    return "\n".join(elements)


def render_answer_png(answer: dict[str, Any]) -> bytes:
    payload = answer_to_score_payload(answer)
    layout = _layout(payload)
    image = Image.new("RGB", (layout["width"], layout["height"]), "#fffdf8")
    draw = ImageDraw.Draw(image)
    font = _font(16)
    title_font = _font(24)
    small_font = _font(12)
    draw.text((36, 24), payload["title"], fill="#111715", font=title_font)
    draw.text((36, 62), f'Time: {payload["timeSignature"]}', fill="#4b5752", font=font)
    for staff in layout["staves"]:
        _draw_staff(draw, staff, layout, font)
    for note_item in layout["notes"]:
        _draw_note(draw, note_item, font)
    for label in layout["harmonyLabels"]:
        draw.text((label["x"], label["y"]), label["text"], fill="#314339", font=small_font)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _layout(payload: dict[str, Any]) -> dict[str, Any]:
    voices_by_id = {voice.get("id"): voice for voice in payload["voices"]}
    measure_count = _measure_count(payload["voices"])
    if measure_count <= 0:
        raise RenderError("The answer contains no renderable measures.")
    measures_per_system = 4
    systems = math.ceil(measure_count / measures_per_system)
    width = 1180
    top = 104
    system_height = 230
    staff_gap = 88
    staff_space = 10
    left = 92
    right = 36
    measure_width = (width - left - right) / measures_per_system
    staves = []
    notes = []
    harmony_labels = []

    for system_index in range(systems):
        system_y = top + system_index * system_height
        for staff_id, staff_voices in STAFF_VOICES.items():
            y = system_y if staff_id == "treble" else system_y + staff_gap
            staves.append({
                "id": staff_id,
                "x": left,
                "y": y,
                "width": width - left - right,
                "space": staff_space,
                "label": "Treble" if staff_id == "treble" else "Bass",
                "system": system_index,
            })
            for measure_offset in range(measures_per_system):
                measure_index = system_index * measures_per_system + measure_offset
                if measure_index >= measure_count:
                    continue
                x0 = left + measure_offset * measure_width
                x1 = x0 + measure_width
                if staff_id == "bass":
                    harmony_labels.extend(_harmony_labels(payload, measure_index, x0, x1, y + 72))
                for voice_id in staff_voices:
                    voice = voices_by_id.get(voice_id) or {}
                    measure = (voice.get("measures") or [])[measure_index]
                    notes.extend(_measure_notes(
                        voice_id, measure.get("entries") or [], x0, x1, y, staff_id, staff_space
                    ))

    return {
        "width": width,
        "height": top + systems * system_height + 24,
        "left": left,
        "measureWidth": measure_width,
        "measuresPerSystem": measures_per_system,
        "staves": staves,
        "notes": notes,
        "harmonyLabels": harmony_labels,
    }


def _measure_count(voices: list[dict[str, Any]]) -> int:
    counts = [len(voice.get("measures") or []) for voice in voices]
    return max(counts) if counts else 0


def _measure_notes(
    voice_id: str,
    entries: list[dict[str, Any]],
    x0: float,
    x1: float,
    staff_y: float,
    staff_id: str,
    staff_space: int,
) -> list[dict[str, Any]]:
    total_units = sum(_entry_units(entry) for entry in entries) or 32
    cursor = 0
    notes = []
    for entry in entries:
        units = _entry_units(entry)
        x = x0 + 24 + ((cursor + units / 2) / total_units) * max(32, (x1 - x0 - 48))
        cursor += units
        pitches = entry.get("pitches") or []
        if entry.get("kind") == "rest" or not pitches:
            notes.append({
                "kind": "rest",
                "voice": voice_id,
                "label": VOICE_LABELS.get(voice_id, voice_id[:1].upper()),
                "x": x,
                "y": staff_y + staff_space * 2,
            })
            continue
        for pitch in pitches[:2]:
            notes.append({
                "kind": "note",
                "voice": voice_id,
                "label": VOICE_LABELS.get(voice_id, voice_id[:1].upper()),
                "pitch": _pitch_label(pitch),
                "x": x,
                "y": _pitch_y(_pitch_label(pitch), staff_y, staff_id, staff_space),
                "stemUp": voice_id in {"soprano", "tenor"},
            })
    return notes


def _entry_units(entry: dict[str, Any]) -> int:
    duration = str(entry.get("duration") or "4").replace("r", "")
    return DURATION_UNITS.get(duration, 8)


def _pitch_label(pitch: Any) -> str:
    if isinstance(pitch, dict):
        step = str(pitch.get("step") or "C")
        accidental = str(pitch.get("accidental") or "")
        octave = str(pitch.get("octave") or "4")
        return f"{step}{accidental}{octave}"
    return str(pitch or "C4")


def _pitch_y(pitch: str, staff_y: float, staff_id: str, staff_space: int) -> float:
    step = pitch[0].upper() if pitch else "C"
    octave_digits = "".join(ch for ch in pitch if ch.isdigit() or ch == "-")
    octave = int(octave_digits or 4)
    diatonic = octave * 7 + STEP_INDEX.get(step, 0)
    reference = 5 * 7 + STEP_INDEX["F"] if staff_id == "treble" else 3 * 7 + STEP_INDEX["A"]
    return staff_y + (reference - diatonic) * (staff_space / 2)


def _harmony_labels(payload: dict[str, Any], measure_index: int, x0: float, x1: float, y: float) -> list[dict[str, Any]]:
    items = payload.get("harmonies") or []
    if measure_index >= len(items):
        return []
    harmonies = (items[measure_index] or {}).get("harmonies") or []
    labels = []
    span = max(32, x1 - x0 - 40)
    count = max(1, len(harmonies))
    for index, harmony in enumerate(harmonies[:6]):
        text = harmony.get("romanNumeral") or harmony.get("commonName") or harmony.get("symbol")
        if text:
            labels.append({"x": x0 + 20 + (index / count) * span, "y": y, "text": str(text)})
    return labels


def _svg_staff(staff: dict[str, Any], layout: dict[str, Any]) -> list[str]:
    x = staff["x"]
    y = staff["y"]
    width = staff["width"]
    space = staff["space"]
    elements = [_svg_text(x - 58, y + 26, staff["label"], 12, "600", "#314339")]
    for line in range(5):
        yy = y + line * space
        elements.append(f'<line x1="{x}" y1="{yy}" x2="{x + width}" y2="{yy}" stroke="#1c2723" stroke-width="1"/>')
    for measure_offset in range(layout["measuresPerSystem"] + 1):
        xx = x + measure_offset * layout["measureWidth"]
        elements.append(f'<line x1="{xx}" y1="{y}" x2="{xx}" y2="{y + 4 * space}" stroke="#1c2723" stroke-width="1"/>')
    return elements


def _svg_note(note: dict[str, Any]) -> list[str]:
    x = note["x"]
    y = note["y"]
    label = escape(note.get("label", ""))
    if note["kind"] == "rest":
        return [
            f'<rect x="{x - 6}" y="{y - 4}" width="12" height="8" fill="#1c2723"/>',
            _svg_text(x + 9, y + 4, label, 9, "600", "#516159"),
        ]
    stem_y = y - 36 if note.get("stemUp") else y + 36
    return [
        f'<ellipse cx="{x}" cy="{y}" rx="8" ry="6" fill="#111715" transform="rotate(-18 {x} {y})"/>',
        f'<line x1="{x + 7}" y1="{y}" x2="{x + 7}" y2="{stem_y}" stroke="#111715" stroke-width="2"/>',
        _svg_text(x + 10, y + 4, label, 9, "600", "#516159"),
    ]


def _svg_text(x: float, y: float, text: str, size: int, weight: str, fill: str = "#111715") -> str:
    return f'<text x="{x}" y="{y}" font-family="Segoe UI, Arial, sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}">{escape(str(text))}</text>'


def _draw_staff(draw: ImageDraw.ImageDraw, staff: dict[str, Any], layout: dict[str, Any], font: ImageFont.ImageFont) -> None:
    x = staff["x"]
    y = staff["y"]
    width = staff["width"]
    space = staff["space"]
    draw.text((x - 58, y + 18), staff["label"], fill="#314339", font=font)
    for line in range(5):
        yy = int(y + line * space)
        draw.line((x, yy, x + width, yy), fill="#1c2723", width=1)
    for measure_offset in range(layout["measuresPerSystem"] + 1):
        xx = int(x + measure_offset * layout["measureWidth"])
        draw.line((xx, y, xx, y + 4 * space), fill="#1c2723", width=1)


def _draw_note(draw: ImageDraw.ImageDraw, note: dict[str, Any], font: ImageFont.ImageFont) -> None:
    x = int(note["x"])
    y = int(note["y"])
    label = note.get("label", "")
    if note["kind"] == "rest":
        draw.rectangle((x - 6, y - 4, x + 6, y + 4), fill="#1c2723")
        draw.text((x + 9, y - 8), label, fill="#516159", font=font)
        return
    draw.ellipse((x - 8, y - 6, x + 8, y + 6), fill="#111715")
    stem_y = y - 36 if note.get("stemUp") else y + 36
    draw.line((x + 7, y, x + 7, stem_y), fill="#111715", width=2)
    draw.text((x + 10, y - 8), label, fill="#516159", font=font)


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("segoeui.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()
