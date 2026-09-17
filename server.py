from __future__ import annotations

import hashlib
import mimetypes
import json
import re
import shutil
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Register woff2 mime (Python <3.13 不自带). StaticFiles 用 mimetypes 推断 Content-Type.
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")
mimetypes.add_type("font/ttf", ".ttf")
mimetypes.add_type("font/otf", ".otf")

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from reader import SUPPORTED_EXTENSIONS, read_score
from omr import SUPPORTED_OMR_EXTENSIONS, OmrError, transcribe_with_audiveris
from musicxml_quality import audit_musicxml
from omr_semantic_metrics import score_musicxml_semantics
from harmony_validator import validate_four_part_solution
from exercise_extractor import extract_exercise_constraints
from score_ir import validate_score_ir
from score_ir_patch import ScoreIrPatchError, apply_confirmed_corrections
from omr_review_pipeline import (
    assess_omr_readiness,
    crop_measure_region,
    extract_measure_candidate,
    prepend_previous_system_context,
    save_review_run,
    select_review_measures,
    summarize_recognition_confidence,
)
from vision_review import (
    MAX_IMAGE_BYTES,
    VisionConfigurationError,
    VisionUpstreamError,
    review_score_region,
    review_score_region_with_escalation,
    vision_status,
)
from manual_chords import analyze_manual_chords
from manual_notes import locate_manual_notes
# P8 (Level 2 integration, 2026-08-09): four_part.py has been removed.
# The Sposobin solver (solver.py) now handles ALL four-part problems —
# both melody-given and bass-given.
#
# 阶段0 (架构清理): solver.py 是唯一求解器 (v1.6, beam K=50 / top_n=50),
# frozen_v1_6/ 已合并进来.  SOLVER_VERSION=v1.5 只是把 beam 收紧到
# K=3 / top_n=1 (历史回退), 不再切换代码文件.
import os

import solver as sposobin_solver

# 历史回退: SOLVER_VERSION=v1.5 → K=3 / top_n=1 (否则默认 v1.6 K=50).
_SOLVER_BEAM_K = 3 if os.environ.get("SOLVER_VERSION") == "v1.5" else 50
_SOLVER_TOP_N = 1 if os.environ.get("SOLVER_VERSION") == "v1.5" else 50

from editor_to_solver import (
    _APPJS_ACCIDENTAL_TO_SOLVER,
    _APPJS_DURATION_TO_QUARTER,
    appjs_entry_to_soprano_note,
    appjs_measures_subdivision,
    appjs_measures_to_solver_bass,
    appjs_measures_to_solver_melody,
    appjs_measures_rhythm_template,
)

# Back-compat aliases (P22 第一刀: 函数搬家, server 内部仍按 _appjs_* 名字调用).
_appjs_entry_to_soprano_note = appjs_entry_to_soprano_note
_appjs_measures_subdivision = appjs_measures_subdivision
_appjs_measures_to_solver_melody = appjs_measures_to_solver_melody
_appjs_measures_to_solver_bass = appjs_measures_to_solver_bass
_appjs_measures_rhythm_template = appjs_measures_rhythm_template

# 修饰音 / 演奏记号字段: 前端 entry → 答案 entry 必须原样透传, 否则在
# solve-melody 往返里会丢失. solver 只理解音高 + 时值, 不理解这些符号,
# 所以锚定声部 (旋律/低音) 的答案把这些字段从输入模板原样带回.
_ENTRY_PASSTHROUGH_FIELDS = (
    "tieStart", "tieStop", "slurStart", "slurStop", "fermata", "dynamic",
    "chordSymbol", "articulation", "ornament", "grace", "pedal", "hairpin",
    "fingering", "arpeggiate", "phraseStart", "phraseStop", "textMark",
    "breath", "tupletType", "tupletGroup", "tupletPosition",
    "rehearsalMark", "volta",
)

_FRONTEND_MUSICXML_SCHEMA_MARKER = "music-reader-schema"
_FRONTEND_MUSICXML_SCHEMA_VERSION = "manual-score-v1"


def _read_source_musicxml(path: Path) -> str | None:
    """Read canonical XML text for an unpacked MusicXML source."""
    if path.suffix.lower() not in {".xml", ".musicxml"}:
        return None
    return path.read_text(encoding="utf-8-sig")


def _musicxml_import_route(source_musicxml: str | None) -> str:
    """Choose the editor import path without treating arbitrary XML as ours."""
    if source_musicxml:
        marker = (
            rf'<miscellaneous-field\s+name=["\']{_FRONTEND_MUSICXML_SCHEMA_MARKER}["\']\s*>'
            rf'\s*{_FRONTEND_MUSICXML_SCHEMA_VERSION}\s*</miscellaneous-field>'
        )
        if re.search(marker, source_musicxml, flags=re.IGNORECASE):
            return "frontend-canonical"
    return "reader-projection"

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
OMR_REVIEW_ROOT = CURRENT_DIR / "data" / "omr-review-runs"
MAX_OMR_SOURCE_BYTES = 32 * 1024 * 1024
MAX_FINAL_MUSICXML_BYTES = 10 * 1024 * 1024


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _atomic_write_text(path: Path, value: str) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(value, encoding="utf-8", newline="")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


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
    melodyEntries: list[dict] = Field(default_factory=list)
    melodyMeasures: list[list[dict]] | None = None
    questionType: str = "melody"
    # P8: bass-given mode.  Populated when questionType='bass'; the
    # solver anchors the chord via the bass line and fills in the
    # upper three voices.  Same shape as melodyEntries/melodyMeasures
    # but the notes are bass pitches (in bass range D2..D4).
    bassEntries: list[dict] = Field(default_factory=list)
    bassMeasures: list[list[dict]] | None = None
    altoEntries: list[dict] = Field(default_factory=list)
    altoMeasures: list[list[dict]] | None = None
    tenorEntries: list[dict] = Field(default_factory=list)
    tenorMeasures: list[list[dict]] | None = None
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
    # Import provenance travels back with the editor projection so a lossy
    # MusicXML/OMR conversion cannot be silently submitted to the solver.
    sourceProjection: dict | None = None


class ScoreIrCorrectionRequest(BaseModel):
    scoreIr: dict
    corrections: list[dict] = Field(default_factory=list)
    confirmed: bool = False
    source: str = "vlm"
    reviewId: str | None = None


_SOLVER_INPUT_MAX_MEASURES = 16


def _entry_units_for_solver(entry: dict) -> float:
    """Return an editor entry's duration in 1/32-note units."""
    units = entry.get("units")
    if isinstance(units, (int, float)) and units > 0:
        return float(units)
    quarter = _APPJS_DURATION_TO_QUARTER.get(str(entry.get("duration") or "4"), 1.0)
    dotted = int(entry.get("dotted") or 0)
    multiplier = 1.75 if dotted >= 2 else 1.5 if dotted == 1 else 1.0
    return quarter * 8.0 * multiplier


def _measure_units_for_time_signature(time_signature: str) -> float | None:
    """Return one measure's capacity in editor units, or None for bad input."""
    try:
        beats, beat_type = (int(value) for value in str(time_signature).split("/", 1))
    except (TypeError, ValueError):
        return None
    if beats <= 0 or beat_type <= 0 or 32 % beat_type:
        return None
    return float(beats * (32 // beat_type))


def _solver_input_eligibility(
    melody_measures: list[list[dict]] | None,
    bass_measures: list[list[dict]] | None,
    time_signature: str,
    question_type: str,
    alto_measures: list[list[dict]] | None = None,
    tenor_measures: list[list[dict]] | None = None,
) -> dict:
    """Check whether editor data is a bounded SATB exercise input.

    This deliberately validates only the voice that anchors the solver.  A
    full piano score may still be imported and edited, but it must be reduced
    to one unambiguous SATB voice before automatic harmonization.
    """
    mode = question_type if question_type in {"alto", "tenor", "bass"} else "melody"
    measures_by_mode = {
        "melody": melody_measures,
        "alto": alto_measures,
        "tenor": tenor_measures,
        "bass": bass_measures,
    }
    measures = measures_by_mode[mode]
    issues: list[dict[str, str | int | float]] = []
    expected_units = _measure_units_for_time_signature(time_signature)
    if expected_units is None:
        issues.append({
            "code": "BAD_TIME_SIGNATURE",
            "message": "拍号无效，无法判断每小节应有的时值。",
        })
        expected_units = 0.0

    if not measures or not any(measure for measure in measures):
        issues.append({
            "code": "EMPTY_INPUT",
            "message": "没有可用于四部和声的给定声部。",
        })
        measures = []
    elif len(measures) > _SOLVER_INPUT_MAX_MEASURES:
        issues.append({
            "code": "TOO_MANY_MEASURES",
            "message": f"自动求解最多处理 {_SOLVER_INPUT_MAX_MEASURES} 小节；请先截取练习片段。",
            "actual": len(measures),
            "expected": _SOLVER_INPUT_MAX_MEASURES,
        })

    voice = "soprano" if mode == "melody" else mode
    range_low, range_high = sposobin_solver.VOICE_RANGES[voice]
    for index, measure in enumerate(measures, start=1):
        if not isinstance(measure, list) or not measure:
            issues.append({
                "code": "EMPTY_MEASURE",
                "message": f"第 {index} 小节为空，无法保持节奏对齐。",
                "measure": index,
            })
            continue
        actual_units = sum(_entry_units_for_solver(entry) for entry in measure if isinstance(entry, dict))
        if expected_units and abs(actual_units - expected_units) > 1e-6:
            issues.append({
                "code": "MEASURE_DURATION_MISMATCH",
                "message": f"第 {index} 小节时值为 {actual_units:g} 单位，应为 {expected_units:g} 单位。",
                "measure": index,
                "actual": actual_units,
                "expected": expected_units,
            })
        for entry in measure:
            if not isinstance(entry, dict) or entry.get("kind") != "note":
                continue
            pitches = entry.get("pitches") or []
            if len(pitches) != 1:
                issues.append({
                    "code": "MULTI_PITCH_INPUT",
                    "message": f"第 {index} 小节的给定声部含和弦；请先只保留一条独立声部线。",
                    "measure": index,
                })
                continue
            note = _appjs_entry_to_soprano_note(entry)
            if note is None:
                issues.append({
                    "code": "INVALID_PITCH",
                    "message": f"第 {index} 小节存在无法识别的音高。",
                    "measure": index,
                })
            elif not range_low.midi <= note.midi <= range_high.midi:
                issues.append({
                    "code": "OUT_OF_RANGE",
                    "message": f"第 {index} 小节音高 {note.name} 超出 {voice} 可用音域。",
                    "measure": index,
                })

    return {
        "eligible": not issues,
        "mode": mode,
        "measureCount": len(measures),
        "issues": issues,
    }


def _editor_solver_eligibility(editor_payload: dict) -> dict:
    """Expose readiness for each single-voice SATB exercise mode."""
    time_signature = editor_payload.get("timeSignature", "4/4")
    melody_measures = editor_payload.get("melodyMeasures")
    bass_measures = editor_payload.get("bassMeasures")
    alto_measures = editor_payload.get("altoMeasures")
    tenor_measures = editor_payload.get("tenorMeasures")
    result = {
        mode: _solver_input_eligibility(
            melody_measures, bass_measures, time_signature, mode,
            alto_measures=alto_measures, tenor_measures=tenor_measures,
        )
        for mode in ("melody", "alto", "tenor", "bass")
    }
    projection = editor_payload.get("editorProjection") or {}
    blocking_codes = {
        "CHORD_REDUCED_TO_TOP_NOTE",
        "DURATION_QUANTIZED",
        "EXTRA_PARTS_IGNORED",
        "EXTRA_VOICES_IGNORED",
    }
    blocking_losses = [
        loss for loss in projection.get("losses", [])
        if loss.get("code") in blocking_codes
    ]
    if blocking_losses:
        issue = {
            "code": "SOURCE_PROJECTION_LOSS",
            "message": "The imported score cannot be projected to the teaching solver without changing musical data.",
            "losses": blocking_losses,
        }
        for mode in result.values():
            mode["issues"].append(issue)
            mode["eligible"] = False
    return result


def _annotate_editor_analysis(editor_payload: dict) -> None:
    editor_payload["solverEligibility"] = _editor_solver_eligibility(editor_payload)
    editor_payload["exerciseExtraction"] = extract_exercise_constraints(editor_payload)


def _editor_source_projection(editor_payload: dict) -> dict | None:
    projection = editor_payload.get("editorProjection")
    if not isinstance(projection, dict):
        return None
    return {
        "schemaVersion": (editor_payload.get("scoreIr") or {}).get("schemaVersion"),
        "scoreIrValid": (editor_payload.get("scoreIrValidation") or {}).get("valid") is not False,
        "lossless": projection.get("lossless") is True,
        "losses": list(projection.get("losses", []) or [])[:64],
    }


def _solve_imported_exercise(editor_payload: dict) -> dict:
    """Run the solver only when OMR, projection, and exercise gates agree."""
    extraction = editor_payload.get("exerciseExtraction") or {}
    question_type = extraction.get("recommendedQuestionType")
    omr = editor_payload.get("omr") or {}
    readiness = omr.get("transcriptionReadiness")
    if isinstance(readiness, dict) and not readiness.get("solverAllowed"):
        return {
            "status": "review-required",
            "stage": "recognition",
            "questionType": question_type,
            "exerciseKind": extraction.get("kind"),
            "issues": readiness.get("issues", []),
        }

    if question_type not in {"melody", "alto", "tenor", "bass"}:
        exercise_kind = extraction.get("kind", "unknown")
        if exercise_kind == "ambiguous-key":
            assessment = extraction.get("keyAssessment") or editor_payload.get("keyAssessment") or {}
            issue = {
                "code": "KEY_CONFIRMATION_REQUIRED",
                "message": "The key is based on low-confidence pitch analysis; confirm the key before solving.",
                "key": assessment.get("key") or editor_payload.get("key"),
                "source": assessment.get("source"),
                "correlation": assessment.get("correlation"),
                "candidates": assessment.get("candidates", []),
            }
        elif exercise_kind == "ambiguous-voice-assignment":
            issue = {
                "code": "VOICE_ASSIGNMENT_REQUIRED",
                "message": "The notes were preserved, but their SATB role cannot be inferred safely from clef, label, and range.",
                "assignment": extraction.get("voiceAssignment") or editor_payload.get("voiceAssignment"),
            }
        else:
            issue = {
                "code": "EXERCISE_TYPE_AMBIGUOUS",
                "message": "The imported score is not an unambiguous melody-given or bass-given exercise.",
            }
        return {
            "status": "selection-required",
            "stage": "exercise",
            "questionType": None,
            "exerciseKind": exercise_kind,
            "issues": [issue],
        }

    eligibility = (editor_payload.get("solverEligibility") or {}).get(question_type) or {}
    if not eligibility.get("eligible"):
        return {
            "status": "review-required",
            "stage": "exercise",
            "questionType": question_type,
            "exerciseKind": extraction.get("kind"),
            "issues": eligibility.get("issues", []),
        }

    request = FourPartRequest(
        key=str(editor_payload.get("key") or "C major"),
        timeSignature=str(editor_payload.get("timeSignature") or "4/4"),
        melodyMeasures=editor_payload.get("melodyMeasures") or [],
        altoMeasures=editor_payload.get("altoMeasures") or [],
        tenorMeasures=editor_payload.get("tenorMeasures") or [],
        bassMeasures=editor_payload.get("bassMeasures") or [],
        questionType=question_type,
        chordPoolProfile="auto",
        sourceProjection=_editor_source_projection(editor_payload),
    )
    solution = solve_melody_endpoint(request)
    answer_contract = (solution.get("fourPart") or {}).get("answerContract") or {}
    successful = answer_contract.get("valid") is True
    return {
        "status": "complete" if successful else "failed",
        "stage": "answer" if successful else "solver",
        "questionType": question_type,
        "exerciseKind": extraction.get("kind"),
        "issues": [] if successful else [{
            "code": solution.get("errorCode", "SOLVER_ERROR"),
            "message": (solution.get("warnings") or ["Four-part solving failed."])[0],
        }],
        "solution": solution,
    }


def _source_projection_blocker(value: dict | None) -> dict | None:
    if not isinstance(value, dict):
        return None
    if value.get("scoreIrValid") is False:
        return {
            "code": "INVALID_SOURCE_SCORE_IR",
            "message": "The imported source failed ScoreIR validation and cannot be solved safely.",
        }
    losses = value.get("losses", [])
    if not isinstance(losses, list) or len(losses) > 64:
        return {
            "code": "INVALID_SOURCE_PROJECTION",
            "message": "The imported source projection metadata is invalid.",
        }
    blocking_codes = {
        "CHORD_REDUCED_TO_TOP_NOTE",
        "DURATION_QUANTIZED",
        "EXTRA_PARTS_IGNORED",
        "EXTRA_VOICES_IGNORED",
    }
    blocking = [
        loss for loss in losses
        if isinstance(loss, dict) and loss.get("code") in blocking_codes
    ]
    if blocking:
        return {
            "code": "SOURCE_PROJECTION_LOSS",
            "message": "The imported score would change musical data before solving. Correct or simplify the source first.",
            "losses": blocking,
        }
    return None


def _safe_upload_name(filename: str | None, suffix: str) -> str:
    """Drop client-supplied directory components before writing a temp file."""
    name = Path(filename or f"upload{suffix}").name
    return name if name not in ("", ".", "..") else f"upload{suffix}"


def _remove_source_path(payload: dict) -> dict:
    """Uploaded temp paths are internal and cease to exist after the request."""
    source = payload.get("source")
    if isinstance(source, dict):
        source.pop("path", None)
    score_ir_source = (payload.get("scoreIr") or {}).get("source")
    if isinstance(score_ir_source, dict):
        score_ir_source.pop("path", None)
    return payload


def _annotate_score_ir_source(payload: dict, engine: str) -> None:
    score_ir = payload.get("scoreIr")
    if not isinstance(score_ir, dict):
        return
    score_ir.setdefault("source", {})["engine"] = engine
    for part in score_ir.get("parts", []) or []:
        for measure in part.get("measures", []) or []:
            for event in measure.get("events", []) or []:
                event.setdefault("provenance", {}).setdefault("engine", engine)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _multipart_json_object(raw: str, field_name: str) -> dict:
    if len(raw) > 20_000:
        raise HTTPException(status_code=413, detail=f"{field_name} JSON is too large.")
    try:
        value = json.loads(raw or "{}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{field_name} must be valid JSON.") from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail=f"{field_name} must be a JSON object.")
    return value


@app.get("/api/vision/status")
def get_vision_status() -> dict:
    return vision_status()


@app.post("/api/score-ir/validate")
def validate_score_ir_payload(score_ir: dict) -> dict:
    """Validate the canonical score contract without converting to MusicXML."""
    return validate_score_ir(score_ir)


@app.post("/api/score-ir/apply-corrections")
def apply_score_ir_corrections(request: ScoreIrCorrectionRequest) -> dict:
    """Apply a bounded, human-confirmed VLM/human patch atomically."""
    review_record = _review_record_for_corrections(
        request.reviewId, request.corrections, request.source
    )
    try:
        result = apply_confirmed_corrections(
            request.scoreIr,
            request.corrections,
            confirmed=request.confirmed,
            source=request.source,
            review_id=request.reviewId,
        )
    except ScoreIrPatchError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    from reader_to_editor import reader_payload_to_editor

    metadata = result["scoreIr"].get("metadata", {}) or {}
    editor_payload = reader_payload_to_editor({
        "scoreIr": result["scoreIr"],
        "summary": {"analyzedKey": metadata.get("analyzedKey")},
        "warnings": [],
    })
    _annotate_editor_analysis(editor_payload)
    editor_payload["importRoute"] = "score-ir-correction"
    if review_record is not None:
        editor_payload["omr"] = _confirmed_omr_metadata(
            review_record, request.reviewId or "", request.corrections
        )
        readiness = editor_payload["omr"]["transcriptionReadiness"]
        if not readiness["solverAllowed"]:
            blocker = {
                "code": "OMR_REVIEW_REQUIRED",
                "message": "OMR contains unresolved recognition risks.",
                "details": readiness["issues"],
            }
            for mode in editor_payload.get("solverEligibility", {}).values():
                mode["eligible"] = False
                mode.setdefault("issues", []).append(blocker)
        _save_confirmed_score_ir_patch(
            request.reviewId or "", review_record, result, request.corrections
        )
        editor_payload["endToEnd"] = _solve_imported_exercise(editor_payload)
        result["reviewRunUpdated"] = True
    else:
        result["reviewRunUpdated"] = False
    result["editorPayload"] = editor_payload
    return result


def _review_record_for_corrections(
    review_id: str | None,
    corrections: list[dict],
    source: str,
) -> dict | None:
    """Bind persisted VLM confirmations to proposals from the same run."""
    if source != "vlm" or not review_id or not re.fullmatch(r"[a-f0-9]{32}", review_id):
        return None
    record_path = OMR_REVIEW_ROOT / review_id / "review.json"
    if not record_path.is_file():
        raise HTTPException(status_code=404, detail="OMR review run was not found.")
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="OMR review record is invalid.") from exc
    if not isinstance(record, dict):
        raise HTTPException(status_code=422, detail="OMR review record is invalid.")
    proposed = []
    for region in (record.get("vision", {}) or {}).get("reviewedRegions", []) or []:
        final = (region.get("review", {}) or {}).get("final", {}) or {}
        if final.get("decision") == "replace_candidate":
            proposed.extend(final.get("corrections", []) or [])
    proposal_keys = {_canonical_json(item) for item in proposed if isinstance(item, dict)}
    if not corrections or any(_canonical_json(item) not in proposal_keys for item in corrections):
        raise HTTPException(
            status_code=422,
            detail="Corrections must be selected from this OMR review run.",
        )
    return record


def _canonical_json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _confirmed_omr_metadata(
    record: dict, review_id: str, corrections: list[dict]
) -> dict:
    confirmed = [
        item for item in (record.get("vlmConfirmedCorrections", []) or [])
        if isinstance(item, dict)
    ]
    seen = {_canonical_json(item) for item in confirmed}
    for correction in corrections:
        key = _canonical_json(correction)
        if key not in seen:
            confirmed.append(correction)
            seen.add(key)
    vision = json.loads(json.dumps(record.get("vision") or {}))
    vision["confirmedCorrections"] = confirmed
    readiness = assess_omr_readiness(
        record.get("quality") or {},
        record.get("recognitionConfidence") or {},
        vision,
    )
    record["vision"] = vision
    record["vlmConfirmedCorrections"] = confirmed
    record["transcriptionReadiness"] = readiness
    return {
        "datasetRunId": review_id,
        "engine": record.get("engine"),
        "quality": record.get("quality") or {},
        "recognitionConfidence": record.get("recognitionConfidence") or {},
        "vision": vision,
        "transcriptionReadiness": readiness,
    }


def _save_confirmed_score_ir_patch(
    review_id: str,
    record: dict,
    result: dict,
    corrections: list[dict],
) -> None:
    run_dir = OMR_REVIEW_ROOT / review_id
    score_path = run_dir / "vlm-confirmed.score-ir.json"
    temporary_score_path = run_dir / ".vlm-confirmed.score-ir.json.tmp"
    temporary_score_path.write_text(
        json.dumps(result["scoreIr"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary_score_path.replace(score_path)
    record["vlmConfirmedAvailable"] = True
    record["vlmConfirmedApplied"] = result["applied"]
    record_path = run_dir / "review.json"
    temporary_record_path = run_dir / ".review.json.tmp"
    temporary_record_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary_record_path.replace(record_path)


@app.post("/api/vision/review-region")
async def review_vision_region(
    image: UploadFile = File(...),
    candidate: str = Form("{}"),
    context: str = Form("{}"),
) -> dict:
    """Review one ambiguous crop; never mutate MusicXML automatically."""
    mime_type = (image.content_type or "").lower()
    image_bytes = await image.read(MAX_IMAGE_BYTES + 1)
    await image.close()
    candidate_data = _multipart_json_object(candidate, "candidate")
    context_data = _multipart_json_object(context, "context")
    try:
        return review_score_region(image_bytes, mime_type, candidate_data, context_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VisionConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VisionUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/omr/review-runs/{run_id}/artifacts/{artifact_path:path}")
def get_omr_review_artifact(run_id: str, artifact_path: str) -> FileResponse:
    """Serve only image artifacts explicitly recorded for one review run."""
    if not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise HTTPException(status_code=400, detail="Invalid OMR review run id.")
    relative_path = Path(artifact_path)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise HTTPException(status_code=400, detail="Invalid OMR review artifact path.")

    run_dir = OMR_REVIEW_ROOT / run_id
    record_path = run_dir / "review.json"
    if not record_path.is_file():
        raise HTTPException(status_code=404, detail="OMR review run was not found.")
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="OMR review record is invalid.") from exc

    normalized = relative_path.as_posix()
    allowed = {
        str(name) for name in (record.get("reviewArtifacts", []) or [])
        if isinstance(name, str)
    }
    if normalized not in allowed:
        raise HTTPException(status_code=404, detail="OMR review artifact was not found.")
    target = (run_dir / relative_path).resolve()
    resolved_run = run_dir.resolve()
    if resolved_run not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail="OMR review artifact was not found.")
    media_types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
    media_type = media_types.get(target.suffix.lower())
    if media_type is None:
        raise HTTPException(status_code=415, detail="Unsupported review artifact type.")
    return FileResponse(
        target,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=300"},
    )


@app.post("/api/omr/audit-musicxml")
async def audit_musicxml_upload(file: UploadFile = File(...)) -> dict:
    if Path(file.filename or "").suffix.lower() not in {".xml", ".musicxml"}:
        raise HTTPException(status_code=400, detail="A MusicXML file is required.")
    payload = await file.read(10 * 1024 * 1024 + 1)
    await file.close()
    if len(payload) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="MusicXML exceeds 10 MB.")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="MusicXML must be UTF-8 encoded.") from exc
    return audit_musicxml(text)


@app.post("/api/omr/enhanced-parse")
async def enhanced_omr_parse(
    file: UploadFile = File(...),
    useVision: bool = Form(True),
    maxRegions: int = Form(3),
    autoSolve: bool = Form(True),
) -> dict:
    """HOMR -> semantic audit -> bounded VLM review -> editor projection."""
    from reader_to_editor import reader_payload_to_editor

    source_filename = Path(file.filename or "").name
    suffix = Path(source_filename).suffix.lower()
    source_mime_type = file.content_type or "application/octet-stream"
    if suffix not in SUPPORTED_OMR_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Enhanced OMR accepts score images or PDF files.")
    maxRegions = max(0, min(int(maxRegions), 8))
    image_bytes = await file.read(MAX_OMR_SOURCE_BYTES + 1)
    await file.close()
    if len(image_bytes) > MAX_OMR_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="OMR source exceeds 32 MB.")

    with tempfile.TemporaryDirectory(prefix="music-reader-enhanced-omr-") as temp_dir:
        target = Path(temp_dir) / _safe_upload_name(source_filename, suffix)
        target.write_bytes(image_bytes)
        try:
            omr_result = transcribe_with_audiveris(target, Path(temp_dir) / "homr")
            xml_path = Path(omr_result["exportedPath"])
            quality = audit_musicxml(xml_path)
            raw_payload = _remove_source_path(read_score(xml_path))
            _annotate_score_ir_source(raw_payload, omr_result["engine"])
            editor_payload = reader_payload_to_editor(raw_payload)
        except OmrError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        reviews = []
        review_errors = []
        review_artifacts: dict[str, bytes] = {}
        if useVision and maxRegions:
            measures = select_review_measures(quality, maxRegions, omr_result.get("pages", []))
            for measure_number in measures:
                try:
                    page_info, local_measure = _omr_page_for_measure(
                        omr_result.get("pages", []), measure_number
                    )
                    page_bytes = Path(page_info["imagePath"]).read_bytes()
                    page_positions = [
                        {**position, "page": 1}
                        for position in page_info.get("staffPositions", [])
                    ]
                    crop_bytes, crop = crop_measure_region(
                        page_bytes,
                        "image/png" if suffix == ".pdf" else source_mime_type,
                        page_positions,
                        local_measure,
                        max(1, int(page_info.get("measureCount") or 1)),
                        quality["stats"]["partCount"],
                    )
                    context_page = None
                    context_system_index = int(crop.get("systemIndex") or 0) - 1
                    if context_system_index >= 0:
                        context_page = page_info
                    else:
                        page_number = int(page_info.get("page") or 1)
                        context_page = next((
                            page for page in omr_result.get("pages", [])
                            if int(page.get("page") or 1) == page_number - 1
                        ), None)
                        if context_page is not None:
                            context_system_index = len(context_page.get("staffPositions", [])) - 1
                    context_metadata = {"included": False}
                    if context_page is not None and context_system_index >= 0:
                        context_positions = [
                            {**position, "page": 1}
                            for position in context_page.get("staffPositions", [])
                        ]
                        crop_bytes, context_metadata = prepend_previous_system_context(
                            crop_bytes,
                            Path(context_page["imagePath"]).read_bytes(),
                            context_positions,
                            context_system_index,
                        )
                    crop["previousSystemContext"] = context_metadata
                    crop["page"] = page_info.get("page", 1)
                    crop["localMeasure"] = local_measure
                    artifact_name = f"review-crops/measure-{measure_number:04d}.png"
                    crop["artifact"] = artifact_name
                    review_artifacts[artifact_name] = crop_bytes
                    candidate = extract_measure_candidate(xml_path, measure_number)
                    previous_candidate = (
                        extract_measure_candidate(xml_path, measure_number - 1)
                        if measure_number > 1 else None
                    )
                    review = review_score_region_with_escalation(
                        crop_bytes,
                        "image/png",
                        candidate,
                        {
                            "measure": measure_number,
                            "measureCount": quality["stats"]["measureCount"],
                            "auditIssues": [
                                issue for issue in quality["issues"]
                                if str(issue.get("measure")) == str(measure_number)
                            ],
                            "imageLayout": (
                                "previous system above target crop"
                                if context_metadata.get("included") else "target crop only"
                            ),
                            "previousMeasureCandidate": previous_candidate,
                        },
                    )
                    reviews.append({
                        "measure": measure_number,
                        "crop": crop,
                        "candidate": candidate,
                        "review": review,
                    })
                except (
                    KeyError, TypeError, OmrError, OSError, ValueError,
                    VisionConfigurationError, VisionUpstreamError,
                ) as exc:
                    review_errors.append({"measure": measure_number, "error": str(exc)})

        editor_payload["rawSummary"] = raw_payload.get("summary", {})
        editor_payload["readerResult"] = raw_payload
        _annotate_editor_analysis(editor_payload)
        editor_payload["importRoute"] = "reader-projection"
        source_musicxml = xml_path.read_text(encoding="utf-8-sig")
        editor_payload["sourceMusicXml"] = source_musicxml
        confidence_summary = summarize_recognition_confidence(
            omr_result.get("pages", [])
        )
        vision_summary = {
            "enabled": useVision,
            "reviewedRegions": reviews,
            "errors": review_errors,
            "autoApplied": False,
        }
        readiness = assess_omr_readiness(quality, confidence_summary, vision_summary)
        editor_payload["omr"] = {
            "engine": omr_result["engine"],
            "quality": quality,
            "pageCount": len(omr_result.get("pages", [])),
            "staffPositions": omr_result.get("staffPositions", []),
            "recognitionConfidence": confidence_summary,
            "vision": vision_summary,
            "transcriptionReadiness": readiness,
        }
        if not readiness["solverAllowed"]:
            blocker = {
                "code": "OMR_REVIEW_REQUIRED",
                "message": "OMR contains unresolved recognition risks.",
                "details": readiness["issues"],
            }
            for mode in editor_payload.get("solverEligibility", {}).values():
                mode["eligible"] = False
                mode.setdefault("issues", []).append(blocker)
        run_id = uuid.uuid4().hex
        save_review_run(
            OMR_REVIEW_ROOT,
            run_id,
            image_bytes,
            suffix,
            source_musicxml,
            {
                "engine": omr_result["engine"],
                "createdAt": _utc_timestamp(),
                "sourceFileName": source_filename,
                "sourceSuffix": suffix,
                "quality": quality,
                "recognitionConfidence": confidence_summary,
                "vision": editor_payload["omr"]["vision"],
                "transcriptionReadiness": readiness,
            },
            artifacts=review_artifacts,
        )
        editor_payload["omr"]["datasetRunId"] = run_id
        editor_payload["endToEnd"] = (
            _solve_imported_exercise(editor_payload)
            if autoSolve else {
                "status": "ready",
                "stage": "exercise",
                "questionType": (editor_payload.get("exerciseExtraction") or {}).get("recommendedQuestionType"),
                "issues": [],
            }
        )
        return editor_payload


def _omr_page_for_measure(
    pages: list[dict[str, Any]], measure_number: int
) -> tuple[dict[str, Any], int]:
    """Map a merged score measure to its source page and page-local measure."""
    if not pages:
        raise OmrError("OMR did not report rendered page metadata.")
    offset = 0
    for page in pages:
        count = max(0, int(page.get("measureCount") or 0))
        if count and measure_number <= offset + count:
            return page, measure_number - offset
        offset += count
    raise OmrError(f"Measure {measure_number} cannot be mapped to a rendered page.")


@app.post("/api/omr/review-runs/{run_id}/final-musicxml")
async def save_human_final_musicxml(run_id: str, file: UploadFile = File(...)) -> dict:
    """Attach a validated, versioned human target without altering HOMR output."""
    if not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise HTTPException(status_code=400, detail="Invalid OMR review run id.")
    run_dir = OMR_REVIEW_ROOT / run_id
    record_path = run_dir / "review.json"
    if not record_path.is_file():
        raise HTTPException(status_code=404, detail="OMR review run was not found.")
    submitted_name = Path(file.filename or "").name
    if Path(submitted_name).suffix.lower() not in {".xml", ".musicxml"}:
        raise HTTPException(status_code=400, detail="A MusicXML file is required.")
    payload = await file.read(MAX_FINAL_MUSICXML_BYTES + 1)
    await file.close()
    if len(payload) > MAX_FINAL_MUSICXML_BYTES:
        raise HTTPException(status_code=413, detail="MusicXML exceeds 10 MB.")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="MusicXML must be UTF-8 encoded.") from exc
    audit = audit_musicxml(text)
    if audit["status"] == "invalid":
        raise HTTPException(status_code=422, detail={"message": "Final MusicXML failed validation.", "audit": audit})

    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="OMR review record is invalid.") from exc
    if not isinstance(record, dict):
        raise HTTPException(status_code=422, detail="OMR review record is invalid.")

    with tempfile.TemporaryDirectory(prefix="music-reader-human-final-") as temp_dir:
        candidate_path = Path(temp_dir) / "human-final.musicxml"
        candidate_path.write_text(text, encoding="utf-8")
        try:
            parsed = read_score(candidate_path)
            score_ir_validation = validate_score_ir(parsed.get("scoreIr", {}))
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Final MusicXML cannot be converted to the internal score representation.",
                    "error": str(exc)[:500],
                },
            ) from exc
        if not score_ir_validation["valid"]:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Final MusicXML produced an invalid internal score representation.",
                    "validation": score_ir_validation,
                },
            )
        try:
            comparison = {
                "available": True,
                **score_musicxml_semantics(candidate_path, run_dir / "homr.musicxml"),
            }
        except Exception as exc:
            comparison = {"available": False, "error": str(exc)[:500]}

    normalized_bytes = text.encode("utf-8")
    final_sha256 = hashlib.sha256(normalized_bytes).hexdigest()
    final_path = run_dir / "human-final.musicxml"
    existing_sha256 = None
    try:
        existing_revision = max(0, int(record.get("humanFinalRevision") or 0))
    except (TypeError, ValueError):
        existing_revision = 0
    if final_path.is_file():
        existing_bytes = final_path.read_bytes()
        existing_sha256 = hashlib.sha256(existing_bytes).hexdigest()
        existing_revision = max(existing_revision, 1)

    idempotent = existing_sha256 == final_sha256
    if final_path.is_file() and not idempotent:
        archive_dir = run_dir / "human-final-revisions"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_name = f"revision-{existing_revision:04d}-{existing_sha256[:12]}.musicxml"
        archive_path = archive_dir / archive_name
        if not archive_path.exists():
            _atomic_write_text(archive_path, final_path.read_text(encoding="utf-8-sig"))
        history = record.get("humanFinalHistory")
        if not isinstance(history, list):
            history = []
        if not any(item.get("sha256") == existing_sha256 for item in history if isinstance(item, dict)):
            history.append({
                "revision": existing_revision,
                "sha256": existing_sha256,
                "savedAt": record.get("humanFinalSavedAt"),
                "archive": archive_path.relative_to(run_dir).as_posix(),
            })
        record["humanFinalHistory"] = history

    revision = existing_revision if idempotent else existing_revision + 1
    if revision == 0:
        revision = 1
    _atomic_write_text(final_path, text)
    record["humanFinalAvailable"] = True
    record["humanFinalRevision"] = revision
    record["humanFinalSha256"] = final_sha256
    record["humanFinalFileName"] = submitted_name
    record["humanFinalSavedAt"] = _utc_timestamp()
    record["humanFinalAudit"] = audit
    record["humanFinalScoreIrValidation"] = score_ir_validation
    record["homrVsHuman"] = comparison
    record["labelStatus"] = "gold-human"
    record["trainingEvidence"] = {
        "labelEligible": True,
        "realImageAligned": False,
        "reason": "The stored source is page/document-level; HOMR staff-window training uses synthetic renders until explicit staff alignment exists.",
    }
    _atomic_write_text(record_path, json.dumps(record, ensure_ascii=False, indent=2))
    return {
        "runId": run_id,
        "saved": True,
        "idempotent": idempotent,
        "revision": revision,
        "audit": audit,
        "scoreIrValidation": score_ir_validation,
        "homrVsHuman": comparison,
        "trainingEvidence": record["trainingEvidence"],
    }


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
            "errorCode": "SOLVER_ERROR",
            "source": {"engine": "sposobin-solver", "version": "P0-P2.6 v1.6", "fallback": False},
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
        target = Path(temp_dir) / _safe_upload_name(file.filename, suffix)
        with target.open("wb") as handle:
            shutil.copyfileobj(file.file, handle)

        try:
            if suffix in SUPPORTED_OMR_EXTENSIONS:
                omr_dir = Path(temp_dir) / "omr-output"
                omr_result = transcribe_with_audiveris(target, omr_dir)
                result = _remove_source_path(read_score(omr_result["exportedPath"]))
                _annotate_score_ir_source(result, omr_result["engine"])
                result["omr"] = {
                    "engine": omr_result["engine"],
                    "exportedFileName": Path(omr_result["exportedPath"]).name,
                    "quality": audit_musicxml(omr_result["exportedPath"]),
                    "staffPositions": omr_result.get("staffPositions", []),
                    "note": "OMR output should be treated as a draft and checked before analysis.",
                }
                result["warnings"].insert(
                    0,
                    "This file went through OMR. Please verify clef, key signature, time signature, notes, and barlines.",
                )
                result["summary"]["status"] = "readable_with_warnings"
                return result

            return _remove_source_path(read_score(target))
        except OmrError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/parse-score")
async def parse_score_to_editor(file: UploadFile = File(...)) -> dict:
    """P2.7+: take a MusicXML file → run reader.py → run reader_to_editor.py →
    return editor entry format (melodyMeasures + bassMeasures) that the
    frontend can directly feed to /solve-melody or load into the editor.

    The key difference from /read-score:
      /read-score:      returns raw reader output (parts + events, no voice
                        separation).  Frontend only displays it.
      /parse-score:     returns editor entry format (melody/bass already
                        separated by voice).  Frontend can load directly.

    Both endpoints share the same upload + tempdir + OMR fallback path.
    """
    from reader_to_editor import reader_payload_to_editor  # P2.7+

    suffix = Path(file.filename or "").suffix.lower()
    supported = SUPPORTED_EXTENSIONS | SUPPORTED_OMR_EXTENSIONS
    if suffix not in supported:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    omr_metadata = None
    with tempfile.TemporaryDirectory(prefix="music-reader-parse-") as temp_dir:
        target = Path(temp_dir) / _safe_upload_name(file.filename, suffix)
        with target.open("wb") as handle:
            shutil.copyfileobj(file.file, handle)

        source_musicxml = _read_source_musicxml(target)

        try:
            if suffix in SUPPORTED_OMR_EXTENSIONS:
                omr_dir = Path(temp_dir) / "omr-output"
                omr_result = transcribe_with_audiveris(target, omr_dir)
                raw_payload = _remove_source_path(read_score(omr_result["exportedPath"]))
                _annotate_score_ir_source(raw_payload, omr_result["engine"])
                omr_metadata = {
                    "engine": omr_result["engine"],
                    "quality": audit_musicxml(omr_result["exportedPath"]),
                    "staffPositions": omr_result.get("staffPositions", []),
                    "visionAvailable": vision_status().get("configured", False),
                }
            else:
                raw_payload = _remove_source_path(read_score(target))
        except OmrError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    # 把 reader output 转 editor entry format (voice separation 做完)
    editor_payload = reader_payload_to_editor(raw_payload)
    # 附上原始 summary 给前端 (keyPerMeasure, cadences, etc.)
    editor_payload["rawSummary"] = raw_payload.get("summary", {})
    _annotate_editor_analysis(editor_payload)
    editor_payload["importRoute"] = _musicxml_import_route(source_musicxml)
    if source_musicxml is not None:
        editor_payload["sourceMusicXml"] = source_musicxml
    if omr_metadata is not None:
        editor_payload["omr"] = omr_metadata
    return editor_payload


# ---------------------------------------------------------------------------
# P2.7+: XML 文件列表 + 按 file_id 解析
# ---------------------------------------------------------------------------
# 用户在 step 3 五线谱制谱区点 XML 文件名 → 直接灌入五线谱 (不走 OS file dialog).
# 全部 XML 在 SHTE_ROOT (eval-data/extracted/hamony dataset/) 下面, 388 个.
# 限制: 一次最多返 N 个 (默认 1 个, 让用户先试通流程).

SHTE_ROOT = Path(os.environ.get(
    "SHTE_ROOT",
    str(CURRENT_DIR / "data" / "external" / "sposobin-shte" / "SHTE_V1" / "hamony dataset"),
))
_XML_FILE_REGISTRY: dict[str, Path] = {}


def _index_xml_files() -> None:
    """Walk SHTE_ROOT and index all .xml files by an opaque id.

    P2.7+ 策略: SHTE dataset 每个 case 有 2 个版本:
      - ch4/original/ch4-01_a minor.xml  → 单声部 melody (用户输入形态)
      - ch4/four/ch4-01_a minor.xml      → 4 voice SATB gold 答案
    默认 id 指向 `original/` (单声部), 让 user 看到的是题, 不是 gold 答案.
    `four/` 版本用 disambiguated id ("four/ch4-01_a minor").
    """
    if _XML_FILE_REGISTRY:
        return
    # 按 path 排序保证 deterministic; original/ 优先匹配 stem.
    for xml in sorted(SHTE_ROOT.glob("**/*.xml"), key=lambda p: (p.stem, 0 if "original" in p.parts else 1)):
        fid = xml.stem
        if fid in _XML_FILE_REGISTRY:
            # 已经指向 original/, 跳过后续的 four/ (因为 sort 把 original 排前面)
            stem_with_parent = f"{xml.parent.name}/{xml.stem}"
            _XML_FILE_REGISTRY[stem_with_parent] = xml
        else:
            # 第一次: 指向 original/ (单声部)
            _XML_FILE_REGISTRY[fid] = xml


@app.get("/list-xml")
async def list_xml_files(query: str = "", limit: int = 1) -> dict:
    """List XML files in SHTE dataset, with optional query filter and limit.

    Args:
      query: case-insensitive substring filter on filename.  e.g. "ch4-01" or "f minor".
      limit: max number of results (default 1, capped at 50).

    Returns:
      {
        "files": [{"id": "ch4-01_a minor", "name": "ch4-01_a minor.xml", "chapter": "ch4"}],
        "total": 388,
        "filtered": 1,
        "limit": 1
      }
    """
    _index_xml_files()
    all_ids = sorted(_XML_FILE_REGISTRY.keys())
    if query:
        q = query.lower()
        all_ids = [fid for fid in all_ids if q in fid.lower()]
    total = len(_XML_FILE_REGISTRY)
    filtered = len(all_ids)
    limit = max(1, min(int(limit), 50))
    items = []
    for fid in all_ids[:limit]:
        path = _XML_FILE_REGISTRY[fid]
        # chapter: ch4 (取 fid 第一个 ch 段)
        chapter = ""
        for seg in path.parts:
            if seg.startswith("ch") and seg[2:].isdigit():
                chapter = seg
                break
        items.append({
            "id": fid,
            "name": path.name,
            "chapter": chapter,
        })
    return {"files": items, "total": total, "filtered": filtered, "limit": limit}


@app.post("/parse-score-by-id")
async def parse_score_by_id(request: Request) -> dict:
    """Same as /parse-score but takes a file_id (from /list-xml) instead of multipart upload.

    Used by the in-page XML file list (P2.7+): user clicks a filename, this endpoint
    loads it by id and returns the editor entry payload.

    Body: {"file_id": "ch4-01_a minor"}
    """
    body = await request.json()
    file_id = body.get("file_id")
    if not file_id:
        raise HTTPException(status_code=400, detail="file_id is required in request body")

    _index_xml_files()
    if file_id not in _XML_FILE_REGISTRY:
        raise HTTPException(status_code=404, detail=f"file_id not found: {file_id}")
    target = _XML_FILE_REGISTRY[file_id]
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"file no longer exists: {target}")

    from reader_to_editor import reader_payload_to_editor
    try:
        raw_payload = read_score(target)
    except OmrError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    editor_payload = reader_payload_to_editor(raw_payload)
    editor_payload["rawSummary"] = raw_payload.get("summary", {})
    _annotate_editor_analysis(editor_payload)
    source_musicxml = _read_source_musicxml(target)
    editor_payload["importRoute"] = _musicxml_import_route(source_musicxml)
    if source_musicxml is not None:
        editor_payload["sourceMusicXml"] = source_musicxml
    return editor_payload


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


def _solver_to_four_part_response(
    solver_result_dict: dict,
    request: FourPartRequest,
    melody_rhythm: list | None = None,
    alto_rhythm: list | None = None,
    tenor_rhythm: list | None = None,
    bass_rhythm: list | None = None,
) -> dict:
    """Convert solver.to_dict() output into the response schema the
    frontend renders.  Single source of truth — the legacy
    four_part.generate_four_part_answer was removed in P8 (2026-08-09).

    ``melody_rhythm`` / ``bass_rhythm`` are the raw per-measure input
    entries (the rhythm template).  When present, the anchored voice
    (soprano in melody mode, bass in bass mode) is rebuilt from them so
    the original durations (whole/half/quarter) survive the beat-level
    solver round-trip instead of being flattened into repeated quarters.
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

    def _rest_entry_from_template(entry: dict) -> dict:
        """Rest entry reconstructed from an input rhythm-template entry."""
        out = {
            "kind": "rest",
            "duration": str(entry.get("duration") or "4"),
            "dotted": entry.get("dotted", False),
            "units": entry.get("units"),
        }
        for _f in _ENTRY_PASSTHROUGH_FIELDS:
            if _f in entry:
                out[_f] = entry[_f]
        return out

    def _template_entries(voice_name: str, template: list) -> tuple[list[dict], list[dict]]:
        """Rebuild one voice's entries from the input rhythm template so the
        original note durations survive the beat-level solver round-trip.

        The solver works at one note per beat, so a whole note in the input
        becomes 4 identical quarter beats in ``measures_data``.  This walks
        the template (per-measure ``(entry, beat_count)``) and merges those
        beats back into a single entry with the original duration/dotted/units.
        Pitches come from the solver output (authoritative for the anchored
        voice); only the rhythm is restored from the template.
        """
        try:
            tmpl_rows = _appjs_measures_rhythm_template(template, request.timeSignature)
        except ValueError:
            # Off-grid input already rejected upstream; degrade to per-beat.
            tmpl_rows = []
        flat_entries: list[dict] = []
        per_measure: list[dict] = []
        for mi, m in enumerate(measures_data):
            beats_in_measure = m.get("beats", [])
            row = tmpl_rows[mi] if mi < len(tmpl_rows) else []
            entries: list[dict] = []
            cursor = 0
            for entry, n_beats in row:
                seg = beats_in_measure[cursor:cursor + n_beats]
                cursor += n_beats
                if entry.get("kind") == "rest":
                    entries.append(_rest_entry_from_template(entry))
                    continue
                # P0-2: 锚定声部直接用输入模板的音高拼写 (输入拼写就是对的),
                # 不用 solver 的 flat-first 重拼写 (否则升号调里 C# 会变 Db).
                # 只有输入没给音高时才退回 solver 输出的音.
                src_pitch = (entry.get("pitches") or [{}])[0] if entry.get("pitches") else None
                if src_pitch and src_pitch.get("step"):
                    step = src_pitch.get("step")
                    oct_ = src_pitch.get("octave")
                    acc = src_pitch.get("accidental", "")
                    display = src_pitch.get("display") or f"{step}{acc}{oct_}"
                else:
                    pitches = [b.get(voice_name) for b in seg if b.get(voice_name)]
                    if not pitches:
                        entries.append(_rest_entry_from_template(entry))
                        continue
                    step, acc, oct_ = _parse_note_name(pitches[0])
                    display = pitches[0]
                note_entry = {
                    "kind": "note",
                    "pitches": [{
                        "step": step,
                        "octave": oct_,
                        "accidental": acc,
                        "display": display,
                    }],
                    "duration": str(entry.get("duration") or "4"),
                    "dotted": entry.get("dotted", False),
                    "units": entry.get("units"),
                }
                # 透传修饰音/演奏记号 (grace/ornament/articulation/fermata/...)
                for _f in _ENTRY_PASSTHROUGH_FIELDS:
                    if _f in entry:
                        note_entry[_f] = entry[_f]
                entries.append(note_entry)
            # Defensive: if the template under-covered the measure, pad the
            # remaining beats with plain quarter-note entries.
            if cursor < len(beats_in_measure):
                entries.extend(
                    _beat_to_entry_dict(voice_name, b)
                    for b in beats_in_measure[cursor:]
                )
            per_measure.append({"number": mi + 1, "entries": entries})
            flat_entries.extend(entries)
        return flat_entries, per_measure

    def voice_track(voice_name: str, template: list | None = None) -> dict:
        if template is not None:
            entries, per_measure = _template_entries(voice_name, template)
        else:
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
            # P22.5-SATB-render: standard SATB clefs (alto=C clef 3rd line, tenor=C clef 4th line)
            "clef": {"soprano": "treble", "alto": "alto", "tenor": "tenor", "bass": "bass"}.get(voice_name, "treble"),
            "entries": entries,
            "measures": per_measure,
        }

    summary = solver_result_dict.get("summary", {})
    key = summary.get("key", request.key)
    independent_validation = validate_four_part_solution(
        solver_result_dict,
        key=key,
        question_type=request.questionType,
    )
    solver_qualifies = bool(summary.get("qualify"))
    independently_valid = bool(independent_validation["valid"])
    qualifies = solver_qualifies and independently_valid
    has_validation_warnings = bool(independent_validation.get("warningCount"))
    violations = list(summary.get("violations", []) or [])
    violations.extend(
        f"{issue['code']}: {issue['message']}"
        for issue in independent_validation["errors"]
    )
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

    # P2.6-C3 (2026-08-15): solver.alternatives is the multi-solution payload
    # (top-50 in v1.6, top-1 in legacy).  Surface it at the top level so
    # the frontend can render alternative voicings.
    raw_alternatives = solver_result_dict.get("alternatives", []) or []

    voice_tracks = [
        voice_track("soprano", melody_rhythm if request.questionType == "melody" else None),
        voice_track("alto", alto_rhythm if request.questionType == "alto" else None),
        voice_track("tenor", tenor_rhythm if request.questionType == "tenor" else None),
        voice_track("bass", bass_rhythm if request.questionType == "bass" else None),
    ]
    expected_roles = ["soprano", "alto", "tenor", "bass"]
    measure_counts = [len(track.get("measures", [])) for track in voice_tracks]
    contract_issues = []
    if [track.get("id") for track in voice_tracks] != expected_roles:
        contract_issues.append("SATB_VOICES_INCOMPLETE")
    if not measure_counts or min(measure_counts) <= 0 or len(set(measure_counts)) != 1:
        contract_issues.append("SATB_MEASURES_MISALIGNED")
    for track in voice_tracks:
        if any(not (measure.get("entries") or []) for measure in track.get("measures", [])):
            contract_issues.append("SATB_MEASURE_EMPTY")
            break
    answer_contract = {
        "version": "satb-grand-staff-v1",
        "valid": not contract_issues,
        "issues": contract_issues,
        "measureCount": measure_counts[0] if measure_counts and len(set(measure_counts)) == 1 else 0,
        "staves": [
            {"id": "treble", "number": 1, "clef": "treble", "voices": ["soprano", "alto"]},
            {"id": "bass", "number": 2, "clef": "bass", "voices": ["tenor", "bass"]},
        ],
    }

    return {
        "source": {
            "engine": "sposobin-solver",
            # P2.6-C3 (2026-08-15): v1.6 = v1.5 + K=50 default (top_n=50)
            "version": "P0-P2.6 v1.6",
            "fallback": False,
        },
        "summary": {
            "status": "complete" if qualifies and not has_validation_warnings else "complete_with_warnings",
            "analyzedKey": {
                "name": key.split()[0] if key else "",
                "mode": key.split()[1] if len(key.split()) > 1 else "",
                "label": key,
                "tonic": key.split()[0] if key else "",
            },
            "partCount": 4,
            "measureCount": summary.get("measureCount", len(measures_data)),
            "cadence": _solver_cadence_per_measure(solver_result_dict)[-1] if measures_data else None,
            "qualify": qualifies,
            "violations": violations,
            "independentValidation": independent_validation,
            "score": summary.get("score"),
            "cadences": _solver_cadence_per_measure(solver_result_dict),
            # P7.5.1: per-measure local key (empty when no modulation).
            "keyPerMeasure": summary.get("keyPerMeasure", []),
            # P18.5: 置信度 0-100% + 依据列表 — 这是用户要的"百分比依据".
            "confidence": summary.get("confidence"),
            "confidenceEvidence": summary.get("confidenceEvidence", []),
            # P2: 被降级合成的小节 (1-indexed), 前端据此标 ⚠.
            "degradedMeasures": summary.get("degradedMeasures", []),
        },
        "fourPart": {
            "timeSignature": request.timeSignature,
            "voices": voice_tracks,
            "answerContract": answer_contract,
            "qualityStatus": "pass" if qualifies and not has_validation_warnings else "warn",
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
        # P2.6-C3 (2026-08-15): 透传 v1.6 的 50 alternatives 到前端.
        # 每个 alternative 是 {rank, deltaScore, summary, measures} dict.
        "alternatives": raw_alternatives,
        "alternativesCount": len(raw_alternatives),
    }


def _safe_four_part_error_response(
    request: FourPartRequest,
    user_message: str,
    internal: str | None = None,
    error_code: str = "SOLVER_ERROR",
) -> dict:
    """P18.6: build a graceful 200 response when the solver fails.

    Returns a fourPart block with empty voices + the user-facing message
    in `warnings`.  The frontend renders this as a clean red error box,
    never a raw Python exception.

    P5-3: ``error_code`` 是稳定的机器可读错误码 (EMPTY_MELODY / EMPTY_BASS /
    OUT_OF_RANGE / BAD_DURATION / SOLVER_ERROR), 前端据此映射文案和动作,
    不再靠解析中文字符串.

    The `internal` arg is for server-side logs only — it must not leak
    to the user.
    """
    if internal:
        print(f"[server] /solve-melody internal error: {internal}", flush=True)
    key = (request.key or "C major").strip()
    key_name = key.split()[0] if key else "C"
    key_mode = key.split()[1] if len(key.split()) > 1 else "major"
    return {
        "errorCode": error_code,
        "source": {
            "engine": "sposobin-solver",
            # P2.6-C3 (2026-08-15): mirror the success-path version
            "version": "P0-P2.6 v1.6",
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


def _classify_value_error(msg: str, question_type: str) -> str:
    """P5-3: 把 ValueError 文案归类为稳定的 errorCode."""
    if "拍号" in msg or "time signature" in msg.lower():
        return "BAD_TIME_SIGNATURE"
    if "empty" in msg.lower() or "没有" in msg:
        return "EMPTY_BASS" if question_type == "bass" else "EMPTY_MELODY"
    if "range" in msg.lower() or "音域" in msg or "范围" in msg:
        return "OUT_OF_RANGE"
    if ("网格" in msg or "时值" in msg or "超拍" in msg
            or "无法落到" in msg or "落格" in msg):
        return "BAD_DURATION"
    return "SOLVER_ERROR"


def _public_value_error_message(error_code: str, question_type: str) -> str:
    range_message = (
        "输入低音超出低音声部的可用音域范围，请调整后重试。"
        if question_type == "bass"
        else "输入旋律超出女高音声部的可用音域范围，请调整后重试。"
    )
    messages = {
        "EMPTY_MELODY": "旋律为空，请先输入至少一个音符。",
        "EMPTY_BASS": "低音为空，请先输入至少一个低音。",
        "OUT_OF_RANGE": range_message,
        "BAD_DURATION": "小节时值或网格数量不正确，请检查拍号与音符时值。",
        "BAD_TIME_SIGNATURE": "拍号格式无效，请使用如 4/4、3/4 的格式。",
        "SOLVER_ERROR": "输入数据无法用于和声求解，请检查调号、拍号和音符。",
    }
    return messages[error_code]


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
    source_blocker = _source_projection_blocker(request.sourceProjection)
    if source_blocker is not None:
        return _safe_four_part_error_response(
            request,
            str(source_blocker["message"]),
            internal=f"source projection rejected: {source_blocker['code']}",
            error_code=str(source_blocker["code"]),
        )

    # P8: bass-given mode.  Pull the bass line from the request, pass
    # it to the solver.  Melody can still be present (used as soft
    # context for NCT classification) but is not enforced.
    if request.questionType not in ("melody", "alto", "tenor", "bass"):
        return _safe_four_part_error_response(
            request, "题型必须是 melody 或 bass。", error_code="BAD_QUESTION_TYPE"
        )

    bass_for_solver: list[list] | None = None
    alto_for_solver: list[list] | None = None
    tenor_for_solver: list[list] | None = None
    if request.questionType == "bass":
        bass_for_solver = request.bassMeasures
        if not bass_for_solver and request.bassEntries:
            bass_for_solver = [request.bassEntries]
        if not bass_for_solver:
            # P18.6: 用友好 message + 200, 不要让前端看到 "HTTP 400" 错误.
            return _safe_four_part_error_response(
                request, "低音题需要在「3 五线谱制谱」区下方低音谱表 (声部 2) 输入低音序列, 再生成四部和声参考答案.",
                error_code="EMPTY_BASS",
            )

    # Convert app.js format → solver format
    if request.questionType == "alto":
        alto_for_solver = request.altoMeasures
        if not alto_for_solver and request.altoEntries:
            alto_for_solver = [request.altoEntries]
        if not alto_for_solver:
            return _safe_four_part_error_response(
                request, "Alto-given mode requires an alto line.",
                error_code="EMPTY_ALTO",
            )
    elif request.questionType == "tenor":
        tenor_for_solver = request.tenorMeasures
        if not tenor_for_solver and request.tenorEntries:
            tenor_for_solver = [request.tenorEntries]
        if not tenor_for_solver:
            return _safe_four_part_error_response(
                request, "Tenor-given mode requires a tenor line.",
                error_code="EMPTY_TENOR",
            )

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
    fixed_for_solver = bass_for_solver or alto_for_solver or tenor_for_solver
    if not measures_for_solver and fixed_for_solver is None:
        # P18.6: 用友好 message + 200, 不要让前端看到 "HTTP 400" 错误.
        return _safe_four_part_error_response(
            request, "旋律题需要在「3 五线谱制谱」区用鼠标点输入旋律, 或在下方文本框填好后点「填入到五线谱」按钮, 再生成四部和声参考答案.",
            error_code="EMPTY_MELODY",
        )
    if fixed_for_solver is not None:
        # P8 review: regardless of whether the user passed melodyMeasures,
        # bass-given mode requires the bass to be the binding constraint.
        # If the user also sent a melody, the solver would treat
        # beat.soprano as fixed and beat.bass as fixed simultaneously,
        # triggering the enumerate_voicings mutex.  Force the melody
        # to a rest-only placeholder matching the bass line shape so
        # the soprano is free to be filled in by the search.
        target_shape = fixed_for_solver
        measures_for_solver = [
            [None] * len(m)
            for m in target_shape
        ]

    eligibility = _solver_input_eligibility(
        measures_for_solver if fixed_for_solver is None else [],
        bass_for_solver,
        request.timeSignature,
        request.questionType,
        alto_measures=alto_for_solver,
        tenor_measures=tenor_for_solver,
    )
    if not eligibility["eligible"]:
        first_issue = eligibility["issues"][0]
        error_code = (
            "BAD_TIME_SIGNATURE"
            if first_issue["code"] == "BAD_TIME_SIGNATURE"
            else "INPUT_NOT_SOLVER_READY"
        )
        return _safe_four_part_error_response(
            request,
            str(first_issue["message"]),
            internal=f"solver input rejected: {first_issue['code']}",
            error_code=error_code,
        )

    try:
        # B1: 网格细分因子由"活跃输入"的最细时值决定 (旋律题看旋律, 低音题看低音).
        subdiv_source = fixed_for_solver if fixed_for_solver is not None else measures_for_solver
        kwargs: dict = {
            "subdivision": _appjs_measures_subdivision(subdiv_source, request.timeSignature),
        }
        if bass_for_solver is not None:
            converted_bass = _appjs_measures_to_solver_bass(
                bass_for_solver, request.timeSignature
            )
            # Durations expand entries into solver cells. Build the placeholder
            # soprano after that expansion so held bass notes cannot make the
            # two per-measure grids diverge.
            melody_pitches = [[None] * len(measure) for measure in converted_bass]
            kwargs["bass_pitches"] = converted_bass
        elif alto_for_solver is not None:
            converted_alto = _appjs_measures_to_solver_melody(
                alto_for_solver, request.timeSignature
            )
            melody_pitches = [[None] * len(measure) for measure in converted_alto]
            kwargs["alto_pitches"] = converted_alto
        elif tenor_for_solver is not None:
            converted_tenor = _appjs_measures_to_solver_melody(
                tenor_for_solver, request.timeSignature
            )
            melody_pitches = [[None] * len(measure) for measure in converted_tenor]
            kwargs["tenor_pitches"] = converted_tenor
        else:
            melody_pitches = _appjs_measures_to_solver_melody(
                measures_for_solver, request.timeSignature
            )
        if request.keyChanges:
            # P7.5: pass modulation points as [(measure_idx, key_name), ...]
            kwargs["key_changes"] = [
                (int(kc[0]), kc[1]) for kc in request.keyChanges
            ]
        # P17: chord pool profile.  'auto' or None → server picks based on
        # the key signature accidentals.  Otherwise the user picked one
        # explicitly in the UI (see app.js chordPoolProfile select).
        profile = request.chordPoolProfile or "auto"
        if profile == "auto":
            profile = _auto_pick_profile(request.key)
        kwargs["chord_pool_profile"] = profile
        # 阶段0: beam 参数由 SOLVER_VERSION 决定 (默认 v1.6 K=50 / v1.5 K=3).
        kwargs.setdefault("beam_k", _SOLVER_BEAM_K)
        kwargs.setdefault("top_n", _SOLVER_TOP_N)
        result = sposobin_solver.solve_melody(
            request.key, request.timeSignature, melody_pitches,
            **kwargs,
        )
        solver_dict = result.to_dict()
        # Pass the raw input entries through as the rhythm template so the
        # anchored voice's original durations survive the round-trip.
        return _solver_to_four_part_response(
            solver_dict, request,
            melody_rhythm=measures_for_solver,
            alto_rhythm=alto_for_solver,
            tenor_rhythm=tenor_for_solver,
            bass_rhythm=bass_for_solver,
        )
    except ValueError as exc:
        # Common case: melody / bass note out of range, or empty input.
        # P18.6: return 200 + safe empty fourPart + warning, never 422/500
        # with raw Python internals.  P5-3: 归类为稳定 errorCode.
        msg = str(exc)
        if not isinstance(msg, str):
            msg = repr(exc)
        error_code = _classify_value_error(msg, request.questionType)
        return _safe_four_part_error_response(
            request, _public_value_error_message(error_code, request.questionType),
            internal=f"{type(exc).__name__}: {msg}",
            error_code=error_code,
        )
    except Exception as exc:
        # P18.6: catch ALL exceptions.  Never let a Python internal error
        # like "list index out of range" leak to the user as the response
        # detail.  The frontend should never see a raw traceback or
        # Python exception message — only a friendly Chinese message.
        msg = f"和声生成遇到内部错误（{type(exc).__name__}），请重试或换一道题试试。"
        return _safe_four_part_error_response(request, msg, internal=msg,
                                              error_code="SOLVER_ERROR")


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
    # 本地五度圈表 (solver.MAJOR_TO_SHARPS 的降号值已修正, 这里保留一份
    # 独立映射以防将来回退; 两者现在一致).
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


# ---------------------------------------------------------------------------
# P21.6: Music Theory Agent Runtime Layer
# ---------------------------------------------------------------------------
import json
import uuid
from typing import Any

# P21.6: trace 落盘目录
AGENT_TRACES_DIR = CURRENT_DIR / "data" / "agent_traces"
_TRACE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


def _trace_path(trace_id: str) -> Path:
    if not _TRACE_ID_RE.fullmatch(trace_id):
        raise ValueError("invalid trace id")
    root = AGENT_TRACES_DIR.resolve()
    path = (root / f"{trace_id}.json").resolve()
    if path.parent != root:
        raise ValueError("invalid trace path")
    return path


def _save_trace(trace_id: str, payload: dict[str, Any]) -> bool:
    """落盘 trace JSON。返回 True=写成功, False=跳过（已存在/失败）。

    P21.6 行为:
    - 已存在 → 跳过（防重写）
    - IO 失败 → log 后跳过（不影响 endpoint 200 响应）
    """
    try:
        AGENT_TRACES_DIR.mkdir(parents=True, exist_ok=True)
        path = _trace_path(trace_id)
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
        path = _trace_path(trace_id)
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
    score: dict[str, Any] = Field(default_factory=dict)
    melody: list[dict[str, Any]] = Field(default_factory=list)
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
    if not _TRACE_ID_RE.fullmatch(trace_id):
        return {
            "traceId": None,
            "agentAvailable": True,
            "explanation": "",
            "trace": {"steps": [], "toolCallCount": 0, "style": style_id},
            "rulesUsed": [],
            "casesCited": [],
            "errors": ["traceId 只能包含字母、数字、下划线和连字符，且最长 128 字符。"],
        }

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
    if not _TRACE_ID_RE.fullmatch(trace_id):
        return {
            "traceId": trace_id,
            "found": False,
            "error": "traceId 格式无效",
        }
    data = _load_trace(trace_id)
    if data is None:
        return {
            "traceId": trace_id,
            "found": False,
            "error": "trace 不存在或 IO 失败",
        }
    return {"found": True, **data}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)
