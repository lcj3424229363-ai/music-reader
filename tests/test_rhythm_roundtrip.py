"""Round-trip test: 输入节奏在 solver + response 转换后必须原样保留。

验证 Bug #1 修复 —— 全音符/二分音符旋律在答案的 soprano 声部里应回到
一个全音符/二分音符，而不是被拍平成重复的四分音符。同时验证低音题
(bass-given) 的 bass 声部节奏保留。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from solver import solve_melody
from editor_to_solver import (
    appjs_measures_subdivision,
    appjs_measures_to_solver_melody,
    appjs_measures_to_solver_bass,
)
from server import _solver_to_four_part_response, FourPartRequest


def _note(step, octave, duration, units):
    return {
        "kind": "note", "voice": "1",
        "pitches": [{"step": step, "octave": octave, "accidental": "",
                     "display": f"{step}{octave}"}],
        "duration": duration, "dotted": False, "units": units,
    }


def _rest(duration, units):
    return {"kind": "rest", "voice": "1", "duration": duration,
            "dotted": False, "units": units}


def _voice_entries(out, voice_id):
    voice = next(v for v in out["fourPart"]["voices"] if v["id"] == voice_id)
    return voice["measures"][0]["entries"]


def test_whole_note_roundtrip():
    """全音符旋律 → 答案 soprano 应是一个全音符, 不是 4 个四分音符。"""
    measures = [[_note("C", 5, "1", 32)]]
    melody = appjs_measures_to_solver_melody(measures, "4/4")
    res = solve_melody("C", "4/4", melody)
    req = FourPartRequest(key="C major", timeSignature="4/4",
                          melodyMeasures=measures, questionType="melody")
    out = _solver_to_four_part_response(res.to_dict(), req, melody_rhythm=measures)

    entries = _voice_entries(out, "soprano")
    assert len(entries) == 1, f"whole note must merge to 1 entry, got {len(entries)}"
    assert entries[0]["duration"] == "1", f"expected whole note, got {entries[0]['duration']}"
    assert entries[0]["units"] == 32
    assert entries[0]["pitches"][0]["display"] == "C5"


def test_two_half_notes_roundtrip():
    """两个二分音符 → 答案 soprano 应是两个二分音符。"""
    measures = [[_note("C", 5, "2", 16), _note("D", 5, "2", 16)]]
    melody = appjs_measures_to_solver_melody(measures, "4/4")
    res = solve_melody("C", "4/4", melody)
    req = FourPartRequest(key="C major", timeSignature="4/4",
                          melodyMeasures=measures, questionType="melody")
    out = _solver_to_four_part_response(res.to_dict(), req, melody_rhythm=measures)

    entries = _voice_entries(out, "soprano")
    assert len(entries) == 2, f"expected 2 entries, got {len(entries)}"
    assert [e["duration"] for e in entries] == ["2", "2"]
    assert entries[0]["pitches"][0]["display"] == "C5"
    assert entries[1]["pitches"][0]["display"] == "D5"


def test_mixed_quarter_half_roundtrip():
    """四分+二分+四分 (4 拍) → soprano 节奏与输入一致。"""
    measures = [[_note("C", 5, "4", 8), _note("D", 5, "2", 16), _note("E", 5, "4", 8)]]
    melody = appjs_measures_to_solver_melody(measures, "4/4")
    res = solve_melody("C", "4/4", melody)
    req = FourPartRequest(key="C major", timeSignature="4/4",
                          melodyMeasures=measures, questionType="melody")
    out = _solver_to_four_part_response(res.to_dict(), req, melody_rhythm=measures)

    entries = _voice_entries(out, "soprano")
    assert [e["duration"] for e in entries] == ["4", "2", "4"]
    assert [e["pitches"][0]["display"] for e in entries] == ["C5", "D5", "E5"]


def test_alto_tenor_still_quarter_notes():
    """非锚定声部 (alto/tenor) 由 solver 逐拍生成, 保持四分音符。"""
    measures = [[_note("C", 5, "1", 32)]]
    melody = appjs_measures_to_solver_melody(measures, "4/4")
    res = solve_melody("C", "4/4", melody)
    req = FourPartRequest(key="C major", timeSignature="4/4",
                          melodyMeasures=measures, questionType="melody")
    out = _solver_to_four_part_response(res.to_dict(), req, melody_rhythm=measures)

    alto = _voice_entries(out, "alto")
    assert len(alto) == 4, f"alto should stay per-beat (4 quarters), got {len(alto)}"


def test_bass_mode_bass_roundtrip():
    """低音题: bass 声部节奏按输入模板重建。"""
    bass_measures = [[_note("C", 3, "1", 32)]]
    bass_pitches = appjs_measures_to_solver_bass(bass_measures, "4/4")
    res = solve_melody("C", "4/4", [[None] * 4], bass_pitches=bass_pitches)
    req = FourPartRequest(key="C major", timeSignature="4/4",
                          bassMeasures=bass_measures, questionType="bass")
    out = _solver_to_four_part_response(res.to_dict(), req, bass_rhythm=bass_measures)

    bass = _voice_entries(out, "bass")
    assert len(bass) == 1, f"bass whole note must merge to 1 entry, got {len(bass)}"
    assert bass[0]["duration"] == "1"
    assert bass[0]["pitches"][0]["display"] == "C3"


def test_inner_voice_anchor_and_rhythm_roundtrip():
    cases = (("alto", "C", 4), ("tenor", "G", 3))
    for voice, step, octave in cases:
        measures = [[_note(step, octave, "1", 32)]]
        fixed = appjs_measures_to_solver_melody(measures, "4/4")
        kwargs = {f"{voice}_pitches": fixed}
        result = solve_melody("C", "4/4", [[None] * 4], **kwargs)
        request_kwargs = {f"{voice}Measures": measures}
        request = FourPartRequest(
            key="C major", timeSignature="4/4", questionType=voice,
            **request_kwargs,
        )
        response_kwargs = {f"{voice}_rhythm": measures}
        out = _solver_to_four_part_response(
            result.to_dict(), request, **response_kwargs,
        )

        entries = _voice_entries(out, voice)
        assert len(entries) == 1
        assert entries[0]["duration"] == "1"
        assert entries[0]["pitches"][0]["display"] == f"{step}{octave}"


def test_ornament_and_grace_passthrough():
    """修饰音/演奏记号 (ornament/grace/articulation/fermata/dynamic/slur/
    textMark/chordSymbol) 在往返后必须原样保留, 不能丢。"""
    entry = _note("C", 5, "1", 32)
    entry.update({
        "ornament": "trill",
        "articulation": "staccato",
        "grace": {"step": "D", "octave": 5, "accidental": ""},
        "fermata": True,
        "dynamic": "f",
        "slurStart": True,
        "textMark": "dolce",
        "chordSymbol": "C",
        "rehearsalMark": "B",
        "volta": 2,
    })
    measures = [[entry]]
    melody = appjs_measures_to_solver_melody(measures, "4/4")
    res = solve_melody("C", "4/4", melody)
    req = FourPartRequest(key="C major", timeSignature="4/4",
                          melodyMeasures=measures, questionType="melody")
    out = _solver_to_four_part_response(res.to_dict(), req, melody_rhythm=measures)

    soprano = _voice_entries(out, "soprano")[0]
    assert soprano["ornament"] == "trill"
    assert soprano["articulation"] == "staccato"
    assert soprano["grace"] == {"step": "D", "octave": 5, "accidental": ""}
    assert soprano["fermata"] is True
    assert soprano["dynamic"] == "f"
    assert soprano["slurStart"] is True
    assert soprano["textMark"] == "dolce"
    assert soprano["chordSymbol"] == "C"
    assert soprano["rehearsalMark"] == "B"
    assert soprano["volta"] == 2


def test_eighth_notes_roundtrip():
    """B1: 8 个八分音符旋律 → 答案 soprano 应是 8 个八分音符 (不是 4 个四分)。"""
    measures = [[_note("C", 5, "8", 4) for _ in range(8)]]
    melody = appjs_measures_to_solver_melody(measures, "4/4")
    subdiv = appjs_measures_subdivision(measures, "4/4")
    assert subdiv == 2
    res = solve_melody("C", "4/4", melody, subdivision=subdiv)
    req = FourPartRequest(key="C major", timeSignature="4/4",
                          melodyMeasures=measures, questionType="melody")
    out = _solver_to_four_part_response(res.to_dict(), req, melody_rhythm=measures)

    soprano = _voice_entries(out, "soprano")
    assert len(soprano) == 8, f"expected 8 eighths, got {len(soprano)}"
    assert all(e["duration"] == "8" for e in soprano)
    # 非锚定声部 (alto) 也应是八分 (同节奏).
    alto = _voice_entries(out, "alto")
    assert len(alto) == 8
    assert all(e["duration"] == "8" for e in alto)
