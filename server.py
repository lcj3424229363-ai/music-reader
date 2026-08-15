from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from reader import SUPPORTED_EXTENSIONS, read_score
from omr import SUPPORTED_OMR_EXTENSIONS, OmrError, transcribe_with_audiveris
from manual_chords import analyze_manual_chords
from manual_notes import locate_manual_notes
# P8 (Level 2 integration, 2026-08-09): four_part.py has been removed.
# The Sposobin solver (solver.py, P0-P7 + bass-given) now handles ALL
# four-part problems — both melody-given and bass-given.  See git log
# for the removal commit.
import solver as sposobin_solver
from editor_to_solver import (
    _APPJS_ACCIDENTAL_TO_SOLVER,
    _APPJS_DURATION_TO_QUARTER,
    appjs_entry_to_soprano_note,
    appjs_entry_to_solver_beats,
    appjs_measures_to_solver_bass,
    appjs_measures_to_solver_melody,
)

# Back-compat aliases (P22 第一刀: 函数搬家, server 内部仍按 _appjs_* 名字调用).
_appjs_entry_to_soprano_note = appjs_entry_to_soprano_note
_appjs_entry_to_solver_beats = appjs_entry_to_solver_beats
_appjs_measures_to_solver_melody = appjs_measures_to_solver_melody
_appjs_measures_to_solver_bass = appjs_measures_to_solver_bass

# P19: LLM 增强层 (教师式中文讲解)
try:
    from llm import HarmonyExplainer, DeepSeekError  # type: ignore
    from llm.agent import MusicTheoryAgent, AgentResult  # type: ignore
    _LLM_AVAILABLE = True
except Exception as _llm_import_err:  # noqa: BLE001
    HarmonyExplainer = None  # type: ignore
    DeepSeekError = Exception  # type: ignore
    MusicTheoryAgent = None  # type: ignore
    AgentResult = None  # type: ignore
    _LLM_AVAILABLE = False
    print(f"[server] llm 模块未加载，/api/explain + /agent/* 将不可用：{_llm_import_err}", flush=True)


app = FastAPI(title="Music Reader MVP", version="0.1.0")
WEB_DIR = CURRENT_DIR / "web"
VEXFLOW_DIR = CURRENT_DIR / "node_modules" / "vexflow" / "build" / "cjs"


@app.middleware("http")
async def no_cache_local_assets(request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith(("/assets/", "/vendor/")):
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response

if WEB_DIR.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")

if VEXFLOW_DIR.exists():
    app.mount("/vendor/vexflow", StaticFiles(directory=VEXFLOW_DIR), name="vexflow")


class ManualChordRequest(BaseModel):
    key: str
    progression: str
    timeSignature: str = "4/4"


class ManualNoteRequest(BaseModel):
    clef: str = "treble"
    notes: str
    measureNumber: int = 1


class FourPartRequest(BaseModel):
    key: str
    timeSignature: str = "4/4"
    melodyEntries: list[dict] = []
    melodyMeasures: list[list[dict]] | None = None
    questionType: str = "melody"
    # P8: bass-given mode.  Populated when questionType='bass'; the
    # solver anchors the chord via the bass line and fills in the
    # upper three voices.  Same shape as melodyEntries/melodyMeasures
    # but the notes are bass pitches (in bass range E2..D4).
    bassEntries: list[dict] = []
    bassMeasures: list[list[dict]] | None = None
    # P7.5: optional list of [measure_index, target_key_name] pairs for
    # modulation.  Defaults to [] (no modulation, single home key).
    keyChanges: list[list] | None = None
    # P17: chord pool profile.  When None or 'auto', server picks a profile
    # based on key signature (e.g. Ab major → ch1-4_triad_only).  When the
    # user picks a specific chapter range in the UI, the value is passed
    # through to solve_melody(chord_pool_profile=...).
    # Valid values: 'auto', 'ch1-4_triad_only', 'ch5-7_triad_plus_v64',
    # 'ch8-20_v7', 'ch21-22_d7_ii7_vii7', 'ch23_v9', 'ch24-26_dd',
    # 'full_p0-p7', 'full_p0-p9'.
    chordPoolProfile: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# P18.6: 全局兜底, 任何未捕获的 Python 异常都返回 200 + 安全 message,
# 永远不暴露 "list index out of range" 之类内部错误给用户.
from fastapi import Request as _FastAPIRequest
from fastapi.responses import JSONResponse as _JSONResponse

@app.exception_handler(Exception)
async def _safe_exception_handler(_request: _FastAPIRequest, exc: Exception) -> _JSONResponse:
    print(f"[server] unhandled exception: {type(exc).__name__}: {exc}", flush=True)
    return _JSONResponse(
        status_code=200,
        content={
            "source": {"engine": "sposobin-solver", "version": "P18.6", "fallback": False},
            "summary": {
                "status": "error",
                "partCount": 4,
                "measureCount": 0,
                "cadences": [],
                "keyPerMeasure": [],
                "confidence": 0,
                "confidenceEvidence": ["服务器内部错误, 请重试."],
            },
            "fourPart": {
                "voices": [],
                "harmonies": [],
                "qualityStatus": "error",
                "explanation": ["服务器内部错误, 请重试."],
            },
            "warnings": ["服务器内部错误, 请重试."],
            "harmonyTimeline": [],
        },
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/styles.css")
def root_styles() -> FileResponse:
    return FileResponse(WEB_DIR / "styles.css")


@app.get("/app.js")
def root_app_js() -> FileResponse:
    return FileResponse(WEB_DIR / "app.js")


# P22.4-B.2: CoordinateSystem v1 (统一坐标层)
@app.get("/coordinate-system.js")
def root_coordinate_system_js() -> FileResponse:
    return FileResponse(WEB_DIR / "coordinate-system.js")


# P22.5-B.1: Score Model (数据契约层)
@app.get("/score-model.js")
def root_score_model_js() -> FileResponse:
    return FileResponse(WEB_DIR / "score-model.js")


@app.post("/read-score")
async def read_score_upload(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    supported = SUPPORTED_EXTENSIONS | SUPPORTED_OMR_EXTENSIONS
    if suffix not in supported:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    with tempfile.TemporaryDirectory(prefix="music-reader-") as temp_dir:
        target = Path(temp_dir) / (file.filename or f"upload{suffix}")
        with target.open("wb") as handle:
            shutil.copyfileobj(file.file, handle)

        try:
            if suffix in SUPPORTED_OMR_EXTENSIONS:
                omr_dir = Path(temp_dir) / "omr-output"
                omr_result = transcribe_with_audiveris(target, omr_dir)
                result = read_score(omr_result["exportedPath"])
                result["omr"] = {
                    "engine": omr_result["engine"],
                    "exportedFileName": Path(omr_result["exportedPath"]).name,
                    "note": "OMR output should be treated as a draft and checked before analysis.",
                }
                result["warnings"].insert(
                    0,
                    "This file went through OMR. Please verify clef, key signature, time signature, notes, and barlines.",
                )
                result["summary"]["status"] = "readable_with_warnings"
                return result

            return read_score(target)
        except OmrError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/manual-chords")
def manual_chords(request: ManualChordRequest) -> dict:
    try:
        return analyze_manual_chords(request.key, request.progression, request.timeSignature)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/manual-notes")
def manual_notes(request: ManualNoteRequest) -> dict:
    try:
        return locate_manual_notes(request.clef, request.notes, request.measureNumber)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/four-part-answer")
def four_part_answer(request: FourPartRequest) -> dict:
    # P8 (Level 2 integration): /four-part-answer now forwards to the
    # Sposobin solver (same as /solve-melody).  The legacy four_part.py
    # (music21-based 5-chord pool) is no longer needed — the Sposobin
    # solver handles both melody-given and bass-given problems natively.
    try:
        return solve_melody_endpoint(request)
    except HTTPException:
        raise
    except Exception as exc:
        # UTF-8 safe detail: ensure the message is a clean unicode
        # string before it goes into the JSON response.  Pydantic /
        # FastAPI will then encode it as UTF-8, no GB18030 garbling
        # in the browser console.
        msg = str(exc)
        if not isinstance(msg, str):
            msg = repr(exc)
        raise HTTPException(status_code=422, detail=msg) from exc


# ---------------------------------------------------------------------------
# app.js → solver data conversion (P0-P8, P22 第一刀抽出到 editor_to_solver.py)
# ---------------------------------------------------------------------------
# 4 个转换函数 (_appjs_entry_to_soprano_note / _appjs_entry_to_solver_beats /
# _appjs_measures_to_solver_melody / _appjs_measures_to_solver_bass) 加 2 个常量
# 字典 (_APPJS_ACCIDENTAL_TO_SOLVER / _APPJS_DURATION_TO_QUARTER) 已在文件顶部
# import 引入. 真实定义在 editor_to_solver.py.
# 行为完全一致 (P22 第一刀: 纯抽公共转换层, 一字不改).


def _solver_cadence_per_measure(solver_result_dict: dict) -> list[str | None]:
    """Flatten the per-measure cadence list from solver's output."""
    return [m.get("cadence") for m in solver_result_dict.get("measures", [])]


def _solver_to_four_part_response(solver_result_dict: dict, request: FourPartRequest) -> dict:
    """Convert solver.to_dict() output into the response schema the
    frontend renders.  Single source of truth — the legacy
    four_part.generate_four_part_answer was removed in P8 (2026-08-09).
    """
    measures_data = solver_result_dict.get("measures", [])
    flat_beats: list[dict] = []
    for m in measures_data:
        for b in m.get("beats", []):
            flat_beats.append(b)

    def _parse_note_name(name: str) -> tuple[str, str, int]:
        """Decompose a note display name like 'F#3' / 'Eb4' / 'C5' into
        (step, accidental, octave).  Robust to both sharps and flats.

        Bug fix (caught by P8 review): the previous implementation
        used `name[:-1].rstrip("#")` which is wrong for 3-char names
        like 'F#3' — `name[:-1]` drops the octave digit, and `rstrip("#")`
        then sees no trailing '#', so 'F#' would leak into step.
        """
        if not name:
            return ("C", "", 4)
        # Strip octave (last char if digit)
        if name[-1].isdigit():
            octave = int(name[-1])
            rest = name[:-1]
        else:
            octave = 4
            rest = name
        # Strip accidental (last char of rest if # or b)
        if rest and rest[-1] in ("#", "b"):
            acc = rest[-1]
            step = rest[:-1]
        else:
            acc = ""
            step = rest
        return (step, acc, octave)

    def _beat_to_entry_dict(voice_name: str, b: dict) -> dict:
        """Convert a solver beat into a frontend entry with the correct
        rhythmic duration.

        P18 bug fix: previously every entry was hard-coded to
        duration=1 (whole note) units=8, which is why the rendered
        score always looked like a row of whole notes no matter what
        the user typed.

        P18.7 fix: app.js durationUnits is in 1/16-of-a-whole-note units
        (so 1 quarter = 8 units, 1 whole = 32 units).  The previous
        code here used 1 quarter = 2 units, which under-flowed 4× for
        every whole-note entry the solver emitted.

        Solver's beat duration is in quarter notes (1.0 = quarter, 0.5
        = eighth, 2.0 = half, 4.0 = whole).  VexFlow duration codes:
        '1' = whole, '2' = half, '4' = quarter, '8' = eighth,
        '16' = sixteenth.  app.js units for that code are 32/16/8/4/2.
        Map quarter-fraction -> (vex code, app.js units).
        """
        step, acc, oct_ = _parse_note_name(b[voice_name])
        # 0.25 -> "16"/2 ; 0.5 -> "8"/4 ; 1.0 -> "4"/8 ; 2.0 -> "2"/16 ; 4.0 -> "1"/32
        quarter = float(b.get("duration", 1.0) or 1.0)
        if quarter >= 4.0:
            dur_code, units = "1", 32
        elif quarter >= 2.0:
            dur_code, units = "2", 16
        elif quarter >= 1.0:
            dur_code, units = "4", 8
        elif quarter >= 0.5:
            dur_code, units = "8", 4
        else:
            dur_code, units = "16", 2
        return {
            "kind": "note",
            "pitches": [{
                "step": step,
                "octave": oct_,
                "accidental": acc,
                "display": b[voice_name],
            }],
            "duration": dur_code,
            "dotted": False,
            "units": units,
        }

    def voice_track(voice_name: str) -> dict:
        entries = [_beat_to_entry_dict(voice_name, b) for b in flat_beats]
        per_measure = []
        for mi, m in enumerate(measures_data):
            beats_in_measure = m.get("beats", [])
            per_measure.append({
                "number": mi + 1,
                "entries": [_beat_to_entry_dict(voice_name, b) for b in beats_in_measure],
            })
        return {
            "id": voice_name,
            "name": voice_name.capitalize(),
            "clef": "treble" if voice_name in ("soprano", "alto") else (
                "bass" if voice_name == "bass" else "tenor"),
            "entries": entries,
            "measures": per_measure,
        }

    summary = solver_result_dict.get("summary", {})
    key = summary.get("key", request.key)
    # Convert flat chord-per-beat → per-measure "harmonies" array
    harmonies_per_measure = []
    for mi, m in enumerate(measures_data):
        per_measure_harmonies = []
        for bi, b in enumerate(m.get("beats", [])):
            per_measure_harmonies.append({
                "offset": bi,
                "duration": b.get("duration"),
                "symbol": None,
                "root": None,
                "commonName": b.get("roman", "?"),
                "romanNumeral": b.get("roman"),
                "function": b.get("function"),
                "pitches": [b["soprano"], b["alto"], b["tenor"], b["bass"]],
                "pitchClasses": [],
            })
        harmonies_per_measure.append({
            "measure": mi + 1,
            "harmonies": per_measure_harmonies,
        })

    return {
        "source": {
            "engine": "sposobin-solver",
            "version": "P0-P8",  # P8 (2026-08-09) added bass-given mode
            "fallback": False,
        },
        "summary": {
            "status": "complete" if summary.get("qualify") else "complete_with_warnings",
            "analyzedKey": {
                "name": key.split()[0] if key else "",
                "mode": key.split()[1] if len(key.split()) > 1 else "",
                "label": key,
                "tonic": key.split()[0] if key else "",
            },
            "partCount": 4,
            "measureCount": summary.get("measureCount", len(measures_data)),
            "cadence": _solver_cadence_per_measure(solver_result_dict)[-1] if measures_data else None,
            "qualify": summary.get("qualify", False),
            "violations": summary.get("violations", []),
            "score": summary.get("score"),
            "cadences": _solver_cadence_per_measure(solver_result_dict),
            # P7.5.1: per-measure local key (empty when no modulation).
            "keyPerMeasure": summary.get("keyPerMeasure", []),
            # P18.5: 置信度 0-100% + 依据列表 — 这是用户要的"百分比依据".
            "confidence": summary.get("confidence"),
            "confidenceEvidence": summary.get("confidenceEvidence", []),
        },
        "fourPart": {
            "timeSignature": request.timeSignature,
            "voices": [voice_track("soprano"), voice_track("alto"),
                       voice_track("tenor"), voice_track("bass")],
            "qualityStatus": "pass" if summary.get("qualify") else "warn",
            "harmonies": harmonies_per_measure,
            # P18.7: explanation 必须传 array, 前端 (answer.explanation || []).map(...)
            # 直接 .map 一个 string 会抛 "answer.explanation.map is not a function".
            "explanation": [
                (
                    "由 Sposobin solver (P0-P7: 正三和弦, V7, 副属, "
                    "aug6/N6, 模进, NCT, SII7/DVII7/D9/DD 变音) 生成. "
                    "共 "
                    f"{sum(1 for c in _solver_cadence_per_measure(solver_result_dict) if c)} "
                    "个终止式.  规则约束: 平行 5/8, 声部交叉, 导音解决, "
                    "七音解决, 重属 (DD) 解决, 调性范围."
                )
            ],
        },
        "warnings": solver_result_dict.get("warnings", []),
        "harmonyTimeline": harmonies_per_measure,
    }


def _safe_four_part_error_response(request: FourPartRequest, user_message: str, internal: str | None = None) -> dict:
    """P18.6: build a graceful 200 response when the solver fails.

    Returns a fourPart block with empty voices + the user-facing message
    in `warnings`.  The frontend renders this as a clean red error box,
    never a raw Python exception.

    The `internal` arg is for server-side logs only — it must not leak
    to the user.
    """
    if internal:
        print(f"[server] /solve-melody internal error: {internal}", flush=True)
    key = (request.key or "C major").strip()
    key_name = key.split()[0] if key else "C"
    key_mode = key.split()[1] if len(key.split()) > 1 else "major"
    return {
        "source": {
            "engine": "sposobin-solver",
            "version": "P0-P18.6",
            "fallback": False,
        },
        "summary": {
            "status": "error",
            "analyzedKey": {
                "name": key_name,
                "mode": key_mode,
                "label": key,
                "tonic": key_name,
            },
            "partCount": 4,
            "measureCount": 0,
            "cadence": None,
            "qualify": False,
            "violations": [],
            "score": None,
            "cadences": [],
            "keyPerMeasure": [],
            "confidence": 0,
            "confidenceEvidence": [user_message],
        },
        "fourPart": {
            "timeSignature": request.timeSignature,
            "voices": [],
            "qualityStatus": "error",
            "harmonies": [],
            "explanation": [user_message],
        },
        "warnings": [user_message],
        "harmonyTimeline": [],
    }


@app.post("/solve-melody")
def solve_melody_endpoint(request: FourPartRequest) -> dict:
    """Level 1 endpoint: use the Sposobin solver (P0-P7 + P8) to harmonize
    the user's input melody OR bass line.

    Request schema is identical to /four-part-answer so the frontend
    can swap endpoints with no schema change.

    P8: bass-given problems (questionType='bass') are now supported
    natively.  The frontend populates request.bassMeasures (or
    request.bassEntries) and the solver runs in bass-given mode.
    """
    # P8: bass-given mode.  Pull the bass line from the request, pass
    # it to the solver.  Melody can still be present (used as soft
    # context for NCT classification) but is not enforced.
    bass_for_solver: list[list] | None = None
    if request.questionType == "bass":
        bass_for_solver = request.bassMeasures
        if not bass_for_solver and request.bassEntries:
            bass_for_solver = [request.bassEntries]
        if not bass_for_solver:
            # P18.6: 用友好 message + 200, 不要让前端看到 "HTTP 400" 错误.
            return _safe_four_part_error_response(
                request, "低音题需要在「3 五线谱制谱」区下方低音谱表 (声部 2) 输入低音序列, 再生成四部和声参考答案."
            )

    # Convert app.js format → solver format
    measures_for_solver = request.melodyMeasures
    if not measures_for_solver and request.melodyEntries:
        # Frontend may send a flat melodyEntries when there's only one
        # measure; wrap it.
        measures_for_solver = [request.melodyEntries]
    # P8: in bass-given mode, melodyMeasures may be empty (the user
    # only entered the bass line).  Synthesize a placeholder melody
    # with the same number of measures / beats as the bass line, all
    # rests.  The solver tolerates rest-only melody when bass_pitches
    # is given (it uses bass as the anchor, not soprano).  In
    # melody-given mode (or when no bass is provided either),
    # melodyMeasures must be non-empty.
    if not measures_for_solver and bass_for_solver is None:
        # P18.6: 用友好 message + 200, 不要让前端看到 "HTTP 400" 错误.
        return _safe_four_part_error_response(
            request, "旋律题需要在「3 五线谱制谱」区用鼠标点输入旋律, 或在下方文本框填好后点「填入到五线谱」按钮, 再生成四部和声参考答案."
        )
    if bass_for_solver is not None:
        # P8 review: regardless of whether the user passed melodyMeasures,
        # bass-given mode requires the bass to be the binding constraint.
        # If the user also sent a melody, the solver would treat
        # beat.soprano as fixed and beat.bass as fixed simultaneously,
        # triggering the enumerate_voicings mutex.  Force the melody
        # to a rest-only placeholder matching the bass line shape so
        # the soprano is free to be filled in by the search.
        target_shape = bass_for_solver
        measures_for_solver = [
            [None] * len(m)
            for m in target_shape
        ]

    try:
        melody_pitches = _appjs_measures_to_solver_melody(measures_for_solver)
        kwargs: dict = {}
        if request.keyChanges:
            # P7.5: pass modulation points as [(measure_idx, key_name), ...]
            kwargs["key_changes"] = [
                (int(kc[0]), kc[1]) for kc in request.keyChanges
            ]
        if bass_for_solver is not None:
            kwargs["bass_pitches"] = _appjs_measures_to_solver_bass(bass_for_solver)
        # P17: chord pool profile.  'auto' or None → server picks based on
        # the key signature accidentals.  Otherwise the user picked one
        # explicitly in the UI (see app.js chordPoolProfile select).
        profile = request.chordPoolProfile or "auto"
        if profile == "auto":
            profile = _auto_pick_profile(request.key)
        kwargs["chord_pool_profile"] = profile
        result = sposobin_solver.solve_melody(
            request.key, request.timeSignature, melody_pitches,
            **kwargs,
        )
        solver_dict = result.to_dict()
        return _solver_to_four_part_response(solver_dict, request)
    except ValueError as exc:
        # Common case: melody / bass note out of range, or empty input.
        # P18.6: return 200 + safe empty fourPart + warning, never 422/500
        # with raw Python internals.  Frontend already shows a clean error.
        msg = str(exc)
        if not isinstance(msg, str):
            msg = repr(exc)
        return _safe_four_part_error_response(request, msg)
    except Exception as exc:
        # P18.6: catch ALL exceptions.  Never let a Python internal error
        # like "list index out of range" leak to the user as the response
        # detail.  The frontend should never see a raw traceback or
        # Python exception message — only a friendly Chinese message.
        msg = f"和声生成遇到内部错误（{type(exc).__name__}），请重试或换一道题试试。"
        return _safe_four_part_error_response(request, msg, internal=msg)


def _auto_pick_profile(key: str) -> str:
    """P17: auto-pick a chord_pool_profile based on the key signature.

    Heuristic: the more accidentals a key has, the more advanced the
    Sposobin chapter range the user is likely studying.  Users working
    in 0-1 升降 are typically in ch1-4 (triad only), 2-3 升降 in
    ch5-7 / ch8-20, 4+ 升降 or minor with chromatic alterations in
    full_p0-p7.

    Returns the profile name to pass to solve_melody(chord_pool_profile=...).
    """
    try:
        k = sposobin_solver.Key.from_name(key)
    except Exception:
        return "full_p0-p7"
    # Local sharps table — solver.MAJOR_TO_SHARPS has incorrect values
    # for F/Bb/Eb/Ab (encodes them as Db/C# instead of flat counts), so
    # we maintain our own correct circle-of-fifths mapping here.
    MAJOR_SHARPS = {
        0: 0,    # C
        7: 1,    # G
        2: 2,    # D
        9: 3,    # A
        4: 4,    # E
        11: 5,   # B
        6: 6,    # F#
        1: 7,    # C#
        5: -1,   # F
        10: -2,  # Bb
        3: -3,   # Eb
        8: -4,   # Ab
    }
    if k.mode == "major":
        sharps = MAJOR_SHARPS.get(k.tonic_pc, 0)
    else:
        # minor: relative major's sharps
        rel_pc = (k.tonic_pc + 3) % 12
        sharps = MAJOR_SHARPS.get(rel_pc, 0)
    accidentals = abs(sharps)
    if k.mode == "minor":
        return "ch5-7_triad_plus_v64" if accidentals <= 1 else "ch8-20_v7"
    # Major
    if accidentals <= 1:
        return "ch1-4_triad_only"
    if accidentals == 2:
        return "ch5-7_triad_plus_v64"
    if accidentals == 3:
        return "ch8-20_v7"
    if accidentals == 4:
        return "ch21-22_d7_ii7_vii7"
    return "full_p0-p7"


# ---------------------------------------------------------------------------
# P19: LLM 讲解端点
# ---------------------------------------------------------------------------
class ExplainRequest(BaseModel):
    """LLM 讲解请求。前端从 /solve-melody 拿到结果后直接喂进来。

    注意：这个端点**不**重新跑 solver — 避免重复算 + 简化错误处理。
    """
    key: str
    timeSignature: str = "4/4"
    keyChanges: list[list] | None = None
    # 从 solver 拿到的关键字段
    measures: list[dict] = []  # 每小节：{ chord, voices: {S,A,T,B: [pitch,..] } }
    cadences: list[str | None] = []  # ["PAC", "IAC", "HC", ...] 每小节
    confidence: float | None = None
    score: float | None = None
    algorithm: str = "sposobin-solver"
    # 可选：原始旋律（用于在 prompt 里展示，不影响讲解）
    inputMelody: list[list] | None = None


@app.post("/api/explain")
def explain_harmony(request: ExplainRequest) -> dict:
    """P19: 用 LLM 把 solver 输出转成教师式中文讲解。

    P18.6 同款兜底：任何错误都返回 200 + safe response，
    不暴露内部 Python 异常。
    """
    if not _LLM_AVAILABLE or HarmonyExplainer is None:
        return {
            "explanation": "",
            "rulesUsed": [],
            "model": "",
            "error": "AI 讲解模块未启用（llm 模块加载失败）",
        }
    if not request.measures:
        return {
            "explanation": "",
            "rulesUsed": [],
            "model": "",
            "error": "需要先调用 /solve-melody 拿到四部和声结果再讲解。",
        }

    # 把请求转成 explainer 期望的 solver_output 形状
    solver_output = {
        "key": request.key,
        "time": request.timeSignature,
        "keyChanges": request.keyChanges or [],
        "measures": request.measures,
        "cadences": request.cadences,
        "confidence": int(request.confidence) if request.confidence is not None else None,
        "score": request.score,
        "algorithm": request.algorithm,
        "inputMelody": request.inputMelody,
    }

    try:
        explainer = HarmonyExplainer()
        result = explainer.explain(solver_output)
        return {
            "explanation": result.explanation,
            "rulesUsed": result.rules_used,
            "model": result.model,
            "error": result.error,
        }
    except DeepSeekError as e:
        print(f"[server] /api/explain deepseek error: {e}", flush=True)
        return {
            "explanation": "",
            "rulesUsed": [],
            "model": "",
            "error": f"AI 讲解服务暂时不可用：{type(e).__name__}",
        }
    except Exception as e:  # noqa: BLE001
        print(f"[server] /api/explain unexpected: {type(e).__name__}: {e}", flush=True)
        return {
            "explanation": "",
            "rulesUsed": [],
            "model": "",
            "error": "AI 讲解遇到内部错误，请稍后重试。",
        }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)


# ---------------------------------------------------------------------------
# P21.6: Music Theory Agent Runtime Layer
# ---------------------------------------------------------------------------
import json
import uuid
from typing import Any

# P21.6: trace 落盘目录
AGENT_TRACES_DIR = CURRENT_DIR / "data" / "agent_traces"


def _save_trace(trace_id: str, payload: dict[str, Any]) -> bool:
    """落盘 trace JSON。返回 True=写成功, False=跳过（已存在/失败）。

    P21.6 行为:
    - 已存在 → 跳过（防重写）
    - IO 失败 → log 后跳过（不影响 endpoint 200 响应）
    """
    try:
        AGENT_TRACES_DIR.mkdir(parents=True, exist_ok=True)
        path = AGENT_TRACES_DIR / f"{trace_id}.json"
        if path.exists():
            return False
        # atomic write: 写 .tmp 再 rename 防中断半成品
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[server] /agent trace save failed ({trace_id}): {type(e).__name__}: {e}", flush=True)
        return False


def _load_trace(trace_id: str) -> dict[str, Any] | None:
    """读 trace JSON。返回 None=不存在 / IO 失败。"""
    try:
        path = AGENT_TRACES_DIR / f"{trace_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"[server] /agent trace load failed ({trace_id}): {type(e).__name__}: {e}", flush=True)
        return None


class AgentExplainRequest(BaseModel):
    """P21.6: 调 MusicTheoryAgent 跑 5 步 preset pipeline。

    输入: score + melody + key + style_id + time_signature。
    输出: trace_id + AgentResult.to_dict()。
    """
    score: dict[str, Any] = {}
    melody: list[dict[str, Any]] = []
    key: str = "C major"
    styleId: str = "sposobin"
    timeSignature: str = "4/4"
    # 可选: 自定义 trace_id (幂等重跑用); 不传则自动生成 UUID4
    traceId: str | None = None


@app.post("/agent/explain")
def agent_explain(request: AgentExplainRequest) -> dict[str, Any]:
    """P21.6: Music Theory Agent Runtime — ReAct 5 步 preset pipeline + trace 落盘。

    错误降级: llm 不可用 / agent.run 抛错 → 200 + safe response,
    不暴露内部 Python 异常给前端。
    """
    if not _LLM_AVAILABLE or MusicTheoryAgent is None:
        return {
            "traceId": None,
            "agentAvailable": False,
            "explanation": "",
            "trace": {"steps": [], "toolCallCount": 0, "style": request.styleId},
            "rulesUsed": [],
            "casesCited": [],
            "errors": ["AI Agent 模块未启用（llm 模块加载失败）"],
        }
    if not request.melody:
        return {
            "traceId": None,
            "agentAvailable": True,
            "explanation": "",
            "trace": {"steps": [], "toolCallCount": 0, "style": request.styleId},
            "rulesUsed": [],
            "casesCited": [],
            "errors": ["需要提供 melody 列表才能跑 Agent。"],
        }

    # P21.6 行为: 强制 styleId = sposobin（V1 默认，未来 multi-style 扩展）
    style_id = request.styleId or "sposobin"
    trace_id = request.traceId or str(uuid.uuid4())

    try:
        agent = MusicTheoryAgent()
        result = agent.run(
            score=request.score,
            melody=request.melody,
            key=request.key,
            style_id=style_id,
            time_signature=request.timeSignature,
        )
    except DeepSeekError as e:
        print(f"[server] /agent/explain deepseek error: {e}", flush=True)
        return {
            "traceId": trace_id,
            "agentAvailable": True,
            "explanation": "",
            "trace": {"steps": [], "toolCallCount": 0, "style": style_id},
            "rulesUsed": [],
            "casesCited": [],
            "errors": [f"AI Agent 服务暂时不可用：{type(e).__name__}"],
        }
    except Exception as e:  # noqa: BLE001
        # P21.6: 错误信息不暴露 type(e).__name__ 给前端 (P19 沿用了 type(e).__name__, P21.6 收紧)
        print(f"[server] /agent/explain unexpected: {type(e).__name__}: {e}", flush=True)
        return {
            "traceId": trace_id,
            "agentAvailable": True,
            "explanation": "",
            "trace": {"steps": [], "toolCallCount": 0, "style": style_id},
            "rulesUsed": [],
            "casesCited": [],
            "errors": ["AI Agent 内部错误，请稍后重试。"],
        }

    # 序列化 trace + 落盘
    result_dict = {
        "explanation": result.explanation,
        "trace": result.trace.to_dict(),
        "rulesUsed": list(result.rules_used),
        "casesCited": list(result.cases_cited),
        "errors": list(result.errors),
    }
    _save_trace(trace_id, {
        "traceId": trace_id,
        "key": request.key,
        "styleId": style_id,
        "timeSignature": request.timeSignature,
        "savedAt": str(uuid.uuid1()),  # P21.6 简化: 用 UUID1 时间戳代替 ISO 字符串
        **result_dict,
    })

    return {
        "traceId": trace_id,
        "agentAvailable": True,
        **result_dict,
    }


@app.get("/agent/trace/{trace_id}")
def agent_get_trace(trace_id: str) -> dict[str, Any]:
    """P21.6: 读 trace JSON。404 友好（trace 不存在）。"""
    data = _load_trace(trace_id)
    if data is None:
        return {
            "traceId": trace_id,
            "found": False,
            "error": "trace 不存在或 IO 失败",
        }
    return {"found": True, **data}
