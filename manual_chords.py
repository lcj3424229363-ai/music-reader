from __future__ import annotations

import re
from typing import Any

from music21 import harmony, key, roman


TONIC_RE = re.compile(r"^([A-Ga-g])([#b-]?)(.*)$")
SLASH_RE = re.compile(r"/([A-Ga-g])([#b-]?)$")


def analyze_manual_chords(key_label: str, progression: str, time_signature: str = "4/4") -> dict[str, Any]:
    parsed_key = parse_key(key_label)
    measures = parse_progression(progression)
    analyzed_measures = []
    warnings = []

    for index, symbols in enumerate(measures, start=1):
        chords = []
        for symbol in symbols:
            try:
                chords.append(analyze_chord_symbol(symbol, parsed_key))
            except Exception as exc:
                warnings.append(f"Measure {index}, chord {symbol}: {exc}")
                chords.append(
                    {
                        "symbol": symbol,
                        "normalizedSymbol": normalize_chord_symbol(symbol),
                        "status": "unreadable",
                        "error": str(exc),
                    }
                )

        analyzed_measures.append(
            {
                "number": index,
                "timeSignature": time_signature,
                "chords": chords,
            }
        )

    return {
        "source": {
            "fileName": "manual-chords",
            "extension": ".manual",
            "path": "",
        },
        "summary": {
            "partCount": 1,
            "measureCount": len(analyzed_measures),
            "analyzedKey": {
                "name": parsed_key.tonic.name,
                "mode": parsed_key.mode,
                "label": f"{parsed_key.tonic.name} {parsed_key.mode}",
                "correlation": None,
            },
            "status": "manual_with_warnings" if warnings else "manual",
        },
        "manual": {
            "inputKey": key_label,
            "inputProgression": progression,
            "timeSignature": time_signature,
            "note": "Manual chord entry is a fallback draft for OMR failure or quick harmonic analysis.",
        },
        "parts": [
            {
                "index": 1,
                "id": "manual-chords",
                "name": "Manual Chords",
                "measureCount": len(analyzed_measures),
                "measures": [
                    {
                        "number": measure["number"],
                        "offset": measure["number"] - 1,
                        "timeSignature": {"ratio": time_signature, "barDurationQuarterLength": None},
                        "keySignature": None,
                        "expectedQuarterLength": None,
                        "actualQuarterLength": None,
                        "eventCount": len(measure["chords"]),
                        "events": [
                            {
                                "type": "chordSymbol",
                                "offset": chord_index,
                                "duration": None,
                                **chord_result,
                            }
                            for chord_index, chord_result in enumerate(measure["chords"])
                        ],
                        "warnings": [],
                    }
                    for measure in analyzed_measures
                ],
            }
        ],
        "harmonyTimeline": [
            {
                "measure": measure["number"],
                "harmonies": [
                    {
                        "offset": chord_index,
                        "duration": None,
                        "symbol": chord_result.get("symbol"),
                        "root": chord_result.get("root"),
                        "commonName": chord_result.get("commonName") or chord_result.get("error") or "unknown",
                        "romanNumeral": chord_result.get("romanNumeral"),
                        "function": chord_result.get("function"),
                        "pitches": chord_result.get("pitches", []),
                        "pitchClasses": chord_result.get("pitchClasses", []),
                    }
                    for chord_index, chord_result in enumerate(measure["chords"])
                ],
            }
            for measure in analyzed_measures
        ],
        "warnings": warnings,
    }


def parse_key(label: str) -> key.Key:
    cleaned = normalize_pitch_spelling(label.strip())
    if not cleaned:
        raise ValueError("Key is required.")

    parts = cleaned.replace("_", " ").split()
    first = parts[0]
    mode = "major"

    if first.lower().endswith("m") and len(first) > 1:
        first = first[:-1]
        mode = "minor"
    elif len(parts) > 1 and parts[1].lower().startswith("min"):
        mode = "minor"
    elif len(parts) > 1 and parts[1].lower().startswith("maj"):
        mode = "major"

    return key.Key(first, mode)


def parse_progression(progression: str) -> list[list[str]]:
    text = progression.strip()
    if not text:
        raise ValueError("Progression is required.")

    raw_measures = []
    for line in text.splitlines():
        raw_measures.extend(part.strip() for part in line.split("|"))

    measures = []
    for raw in raw_measures:
        if not raw:
            continue
        symbols = [item for item in re.split(r"[\s,]+", raw) if item]
        if symbols:
            measures.append(symbols)

    if not measures:
        raise ValueError("No chord symbols found.")
    return measures


def analyze_chord_symbol(symbol: str, parsed_key: key.Key) -> dict[str, Any]:
    normalized = normalize_chord_symbol(symbol)
    chord_symbol = harmony.ChordSymbol(normalized)
    roman_numeral = roman.romanNumeralFromChord(chord_symbol, parsed_key)

    return {
        "symbol": symbol,
        "normalizedSymbol": normalized,
        "status": "readable",
        "root": _safe_pitch_name(chord_symbol.root()),
        "bass": _safe_pitch_name(chord_symbol.bass()),
        "commonName": chord_symbol.commonName,
        "pitches": [pitch.nameWithOctave for pitch in chord_symbol.pitches],
        "pitchClasses": sorted(set(pitch.pitchClass for pitch in chord_symbol.pitches)),
        "romanNumeral": roman_numeral.figure,
        "scaleDegree": roman_numeral.scaleDegree,
        "function": harmonic_function(roman_numeral),
        "confidence": "high",
    }


def normalize_chord_symbol(symbol: str) -> str:
    cleaned = symbol.strip()
    cleaned = cleaned.replace("♭", "b").replace("♯", "#")
    cleaned = normalize_pitch_spelling(cleaned)
    cleaned = SLASH_RE.sub(lambda match: "/" + match.group(1).upper() + _accidental(match.group(2)), cleaned)
    return cleaned


def normalize_pitch_spelling(value: str) -> str:
    match = TONIC_RE.match(value)
    if not match:
        return value

    root, accidental, rest = match.groups()
    return root.upper() + _accidental(accidental) + rest


def _accidental(value: str) -> str:
    if value == "b":
        return "-"
    return value


def harmonic_function(roman_numeral: roman.RomanNumeral) -> str:
    degree = roman_numeral.scaleDegree
    if degree in {1, 3, 6}:
        return "tonic"
    if degree in {2, 4}:
        return "predominant"
    if degree in {5, 7}:
        return "dominant"
    return "other"


def _safe_pitch_name(value: Any) -> str | None:
    if value is None:
        return None
    return getattr(value, "name", str(value))

