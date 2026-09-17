from reader_to_editor import reader_payload_to_editor


def _measure(events, clef=None):
    return {
        "number": 1,
        "timeSignature": {"ratio": "4/4", "barDurationQuarterLength": 4.0},
        "keySignature": None,
        "clef": clef,
        "events": events,
    }


def _note(pitch, offset=0.0, duration=1.0, voice=None):
    return {
        "type": "note",
        "pitch": pitch,
        "offset": offset,
        "duration": duration,
        "voice": voice,
        "staff": 1,
    }


def _payload(parts):
    return {
        "summary": {"analyzedKey": {"label": "C major"}},
        "parts": parts,
        "warnings": [],
    }


def _pitched_displays(measures):
    return [
        entry["pitches"][0]["display"]
        for measure in measures
        for entry in measure
        if entry.get("kind") == "note"
    ]


def test_voice_identity_does_not_switch_when_primary_voice_rests_for_a_measure():
    part = {
        "id": "P1",
        "name": "Piano",
        "measures": [
            _measure([_note("E5", voice="1"), _note("C4", voice="2")]),
            _measure([_note("D4", voice="2")]),
        ],
    }

    editor = reader_payload_to_editor(_payload([part]))

    assert _pitched_displays(editor["sopranoMeasures"]) == ["E5"]
    assert _pitched_displays(editor["bassMeasures"]) == ["C4", "D4"]
    assert editor["sopranoMeasures"][1][0]["kind"] == "rest"


def test_omr_chords_on_two_staves_expand_to_four_vertical_voices():
    upper = {
        "id": "P1-Staff1",
        "name": "Piano",
        "staffNumber": 1,
        "measures": [_measure([{
            "type": "chord", "pitches": ["C5", "E5"], "offset": 0.0,
            "duration": 4.0, "voice": None, "staff": 1,
        }], {"sign": "G", "line": 2})],
    }
    lower = {
        "id": "P1-Staff2",
        "name": "Piano",
        "staffNumber": 2,
        "measures": [_measure([{
            "type": "chord", "pitches": ["A2", "A3"], "offset": 0.0,
            "duration": 4.0, "voice": None, "staff": 2,
        }], {"sign": "F", "line": 4})],
    }

    editor = reader_payload_to_editor(_payload([upper, lower]))

    assert _pitched_displays(editor["sopranoMeasures"]) == ["E5"]
    assert _pitched_displays(editor["altoMeasures"]) == ["C5"]
    assert _pitched_displays(editor["tenorMeasures"]) == ["A3"]
    assert _pitched_displays(editor["bassMeasures"]) == ["A2"]


def test_single_bass_clef_stream_is_a_bass_exercise_not_a_melody_exercise():
    part = {
        "id": "P1",
        "name": "Exercise",
        "measures": [_measure([_note("C3", duration=4.0)], {"sign": "F", "line": 4})],
    }

    editor = reader_payload_to_editor(_payload([part]))

    assert not _pitched_displays(editor["sopranoMeasures"])
    assert _pitched_displays(editor["bassMeasures"]) == ["C3"]
    assert editor["voiceAssignment"]["confidence"] == "high"
    assert editor["voiceAssignment"]["roles"][0]["source"] == "bass-clef"


def test_overlapping_single_inner_voice_is_preserved_without_guessing_a_role():
    part = {
        "id": "P1",
        "name": "Exercise",
        "measures": [_measure([_note("F4", duration=4.0)])],
    }

    editor = reader_payload_to_editor(_payload([part]))

    assert editor["voiceAssignment"]["confidence"] == "low"
    assert editor["voiceAssignment"]["roles"] == []
    assert _pitched_displays(editor["unassignedVoices"][0]["measures"]) == ["F4"]
    assert not any(_pitched_displays(editor[field]) for field in (
        "sopranoMeasures", "altoMeasures", "tenorMeasures", "bassMeasures"
    ))
