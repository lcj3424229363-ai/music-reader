import pytest

import solver


def test_enumerate_voicings_returns_global_top_k():
    key = solver.Key.from_name("C")
    chord = solver.Chord(4, "maj", "root")
    all_results = solver.enumerate_voicings(
        chord, key, max_results=10_000
    )
    limited = solver.enumerate_voicings(
        chord, key, max_results=40
    )

    assert len(all_results) > 40
    assert [(v, score) for v, score, _ in limited] == [
        (v, score) for v, score, _ in all_results[:40]
    ]


def test_bass_anchor_survives_every_fallback_layer():
    bass = [solver.Note.from_name("F#2"), solver.Note.from_name("C3")]
    result = solver.solve_melody(
        "C",
        "4/4",
        [[None, None]],
        measure_count=1,
        bass_pitches=[bass],
    ).to_dict()

    assert [beat["bass"] for beat in result["measures"][0]["beats"]] == ["F#2", "C3"]


@pytest.mark.parametrize(
    ("voice", "note_name"),
    [("alto", "C4"), ("tenor", "G3")],
)
def test_inner_voice_anchor_is_preserved_exactly(voice, note_name):
    note = solver.Note.from_name(note_name)
    result = solver.solve_melody(
        "C", "4/4", [[None] * 4],
        **{f"{voice}_pitches": [[note] * 4]},
    ).to_dict()

    assert [beat[voice] for beat in result["measures"][0]["beats"]] == [note_name] * 4


@pytest.mark.parametrize(
    ("name", "tonic", "accidentals"),
    [
        ("Db", "Db", -5),
        ("Gb", "Gb", -6),
        ("Cb", "Cb", -7),
        ("C#", "C#", 7),
        ("B- major", "Bb", -2),
    ],
)
def test_key_spelling_and_signature_are_enharmonic(name, tonic, accidentals):
    key = solver.Key.from_name(name)
    assert key.tonic_name == tonic
    assert solver._key_accidentals(key) == accidentals


def test_chord_aware_spelling_and_accidental_octave():
    c_major = solver.Key.from_name("C")
    borrowed_iv = solver.Chord(4, "modal_iv", "root")
    names = [
        solver._spell_note(solver.Note(pc, 4), c_major, borrowed_iv)
        for pc in borrowed_iv.pitch_classes(c_major)
    ]
    assert names == ["F4", "Ab4", "C4"]
    assert solver._spell_note(solver.Note(0, 4), solver.Key.from_name("C#")) == "B#3"


def test_relative_and_close_related_keys_keep_circle_of_fifths_spelling():
    d_flat = solver.Key.from_name("Db")
    assert d_flat.relative().tonic_name == "Bb"
    assert [key.tonic_name for key in d_flat.close_related_keys()[:4]] == [
        "Ab", "Gb", "Eb", "Cb"
    ]


def test_lydian_cadence_requires_tonic_in_soprano():
    key = solver.Key.from_name("C")
    previous = solver.Chord(2, "maj", "root")
    tonic = solver.Chord(1, "maj", "root")
    voicing = solver.Voicing(
        soprano=solver.Note.from_name("E5"),
        alto=solver.Note.from_name("C4"),
        tenor=solver.Note.from_name("E3"),
        bass=solver.Note.from_name("C3"),
    )
    assert solver.detect_cadence(previous, tonic, voicing, key) is None


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"subdivision": 0}, "subdivision"),
        ({"measure_count": 2}, "不一致"),
        ({"bass_pitches": [[solver.Note.from_name("C3")], []]}, "低音小节数"),
    ],
)
def test_solver_rejects_malformed_shapes(kwargs, message):
    with pytest.raises(ValueError, match=message):
        solver.solve_melody("C", "4/4", [[solver.Note.from_name("C4")]], **kwargs)


def test_solver_rejects_bad_time_signature_cleanly():
    with pytest.raises(ValueError, match="拍号格式无效"):
        solver.solve_melody("C", "not-a-meter", [[solver.Note.from_name("C4")]])


def test_full_measure_rest_is_preserved_without_fake_cadence():
    result = solver.solve_melody(
        "C",
        "4/4",
        [[solver.Note.from_name("C4")], [], [solver.Note.from_name("C4")]],
    ).to_dict()
    assert result["measures"][1]["beats"] == []
    assert result["measures"][1]["cadence"] is None
