"""reader_to_editor.py — 把 /read-score 输出转成 editor entry 格式.

输入: reader.read_score(target) 返回的 dict:
  {
    "summary": {"analyzedKey": {"label": "A minor"}, "timeSignature": "4/4", ...},
    "parts": [
      {
        "name": "Piano",
        "measures": [
          {
            "events": [
              {"type": "note", "offset": 0.0, "duration": 1.0, "pitch": "E5", "pitchClass": 4},
              {"type": "note", "offset": 1.0, "duration": 1.0, "pitch": "F5", "pitchClass": 5},
              {"type": "note", "offset": 0.0, "duration": 1.0, "pitch": "A4", "pitchClass": 9},
              ...
            ]
          }
        ]
      },
      ...
    ]
  }

输出: editor entry 格式 (跟 docs/ENTRY_SCHEMA.md §2 一致):
  {
    "key": "A minor",
    "timeSignature": "4/4",
    "melodyMeasures": [[entry, entry, ...], ...],   # 1 voice (soprano 候选)
    "bassMeasures":   [[entry, entry, ...], ...],   # 1 voice (bass 候选)
  }

可以喂给 /solve-melody (P2.7+ 集成), 跟前端 app.js collectScoreMeasuresForAnswer
产生的 payload shape 完全一致.

Voice separation 策略:
  - 把 events 按 (offset, duration) 聚合成 "音簇" (chord) 和 "单音" (single note)
  - 同一 offset 内的多个 note = 同一拍发声的多 voice
  - 拆 voice: 最高音 → melody, 最低音 → bass (中音 drop, 后续可扩展)
  - 跨 offset 保持 voice 稳定 (不会出现 melody 突然跑到低音区)

这个策略是 Sposobin 教科书经典 SATB 写法 (旋律 + 持续低音伴奏) 的反推:
  - 旋律声部: 全局最高音
  - 低音声部: 全局最低音
  - 中间: 留空 (VexFlow 渲染时只显示 melody + bass, 用户后续可填 alto/tenor)
"""
from __future__ import annotations
from collections import defaultdict
from typing import Any

from score_ir import analyze_editor_projection, score_ir_to_reader_parts, validate_score_ir


def _pitch_to_pc_oct(pitch_name: str) -> tuple[int, int]:
    """E5 -> (4, 5).  F#4 -> (6, 4).  Bb3 -> (10, 3).

    跟 v1.6 solver Note.from_name 一致: pc 是 0..11 (C=0), oct 是 scientific octave.
    """
    if not pitch_name:
        return -1, -1
    # step (letter)
    letter = pitch_name[0].upper()
    step_to_pc = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    if letter not in step_to_pc:
        return -1, -1
    pc = step_to_pc[letter]
    # accidental
    idx = 1
    if idx < len(pitch_name) and pitch_name[idx] in ("#", "b"):
        pc += 1 if pitch_name[idx] == "#" else -1
        idx += 1
    # octave
    try:
        oct_ = int(pitch_name[idx:])
    except (ValueError, IndexError):
        return pc, -1
    return pc % 12, oct_


def _events_to_step_oct_acc(pitch: str) -> tuple[str, str, int]:
    """E5 -> ('E', '', 5).  F#4 -> ('F', '#', 4).  Bb3 -> ('B', 'b', 3).

    P22.5 supervise v3 (2026-08-17): music21 uses ASCII '-' for flat
    (e.g. 'D-5' = Db5) instead of the typographic 'b' that musicXML uses.
    Without the '-' branch, 'D-5' parses as step='D' + octave=int('-5')=-5,
    which then trips solver's range check ("D-5 is out of soprano range
    [A3..D6]").  Verified reproduction: ch23-06_F major m1 (XML has
    D5 + Db5 quarter notes in voice 1; the Db5 round-tripped to octave=-5).
    """
    if not pitch:
        return ("C", "", 4)
    step = pitch[0].upper()
    acc = ""
    idx = 1
    if idx < len(pitch) and pitch[idx] in ("#", "b", "-"):
        acc = "b" if pitch[idx] == "-" else pitch[idx]
        idx += 1
    try:
        oct_ = int(pitch[idx:])
    except (ValueError, IndexError):
        oct_ = 4
    return (step, acc, oct_)


def _duration_quarter_to_code(duration: float) -> tuple[str, int, int]:
    """quarter-fraction -> (VexFlow code, dotted count, units).

    Examples:
      1.0  -> ("4", 0, 8)    # quarter
      0.5  -> ("8", 0, 4)    # eighth
      2.0  -> ("2", 0, 16)   # half
      4.0  -> ("1", 0, 32)   # whole
      1.5  -> ("4", 1, 12)   # dotted quarter
      0.75 -> ("8", 1, 6)    # dotted eighth
      3.0  -> ("2", 1, 24)   # dotted half (3 quarter) — P2.7.1 加
    """
    if duration >= 4.0:
        return "1", 0, 32
    if duration >= 3.0:
        return "2", 1, 24   # dotted half = 3 quarter
    if duration >= 2.0:
        return "2", 0, 16
    if duration >= 1.0:
        if duration >= 1.5:
            return "4", 1, 12
        return "4", 0, 8
    if duration >= 0.5:
        if duration >= 0.75:
            return "8", 1, 6
        return "8", 0, 4
    if duration >= 0.25:
        if duration >= 0.375:
            return "16", 1, 3
        return "16", 0, 2
    return "32", 0, 1


def _measure_capacity_ql(time_signature: dict | None) -> float:
    """小节总时值 (单位: quarter). 2/4 → 2, 4/4 → 4, 3/4 → 3, 6/8 → 3.

    time_signature: dict like {"ratio": "2/4", "barDurationQuarterLength": 2.0}
    """
    if not time_signature:
        return 2.0  # default 2/4
    num_den = time_signature.get("ratio") if isinstance(time_signature, dict) else None
    if not num_den or "/" not in num_den:
        # fallback: 用 barDurationQuarterLength
        bd = time_signature.get("barDurationQuarterLength", 2.0) if isinstance(time_signature, dict) else 2.0
        return float(bd)
    try:
        num, den = num_den.split("/")
        return float(num) * (4.0 / float(den))
    except (ValueError, ZeroDivisionError):
        return 2.0


def _make_entry(pitch: str | None, voice: str, duration_ql: float = 1.0) -> dict:
    """Construct one editor entry from a pitch string + quarter-length duration.

    voice: "soprano" | "alto" | "tenor" | "bass" (跟 ENTRY_SCHEMA §3 映射)
    duration_ql: 时值 in quarter fractions.
                 1.0=quarter, 2.0=half, 0.5=eighth, 4.0=whole, 1.5=dotted quarter, 0.75=dotted eighth
                 默认 1.0 (向后兼容老 caller, 但实际使用都从 XML 读真实 dur).
    """
    dur_code, dotted, units = _duration_quarter_to_code(duration_ql)
    if pitch is None:
        return {
            "kind": "rest",
            "voice": voice,
            "duration": dur_code,
            "dotted": dotted,
            "units": units,
        }
    step, acc, oct_ = _events_to_step_oct_acc(pitch)
    display = f"{step}{acc}{oct_}"
    return {
        "kind": "note",
        "voice": voice,
        "pitches": [{"step": step, "octave": oct_, "accidental": acc, "display": display}],
        "duration": dur_code,
        "dotted": dotted,
        "units": units,
    }


def _split_chord_to_voices(events_at_offset: list[dict]) -> tuple[str | None, float | None, str | None, float | None]:
    """Given all note events at the same offset, return (top_pitch, top_dur_ql, bot_pitch, bot_dur_ql).

    events_at_offset: list of {"type": "note", "pitch": "E5", "duration": 1.0, ...}
    Returns: ("E5", 1.0, "C3", 1.0) or ("E5", 1.0, None, None) if single note,
             or (None, None, None, None) if all rest/empty.

    Sort key: pc + oct*12 (C0=0, C4=48, A4=57, C5=60).  Higher value = higher pitch.
    P2.7.1: also returns duration_ql (quarter fractions) for each voice so
    _collect_per_part_voice_notes can detect gaps and emit rests.
    """
    notes = []
    for e in events_at_offset:
        if e.get("type") == "note":
            pitches = [e.get("pitch")]
        elif e.get("type") == "chord":
            pitches = e.get("pitches") or []
        else:
            continue
        dur_ql = float(e.get("duration", 1.0) or 1.0)
        for pitch in pitches:
            if not pitch:
                continue
            pc, oct_ = _pitch_to_pc_oct(pitch)
            if pc < 0 or oct_ < 0:
                continue
            notes.append((pc + oct_ * 12, pitch, dur_ql))
    if not notes:
        return (None, None, None, None)
    # P22.5 supervise v2 (2026-08-17): MUST sort only by pc+oct*12, NOT whole tuple.
    # Old code did `notes.sort()` which silently included `dur_ql` as third
    # sort key — when two notes share pitch (e.g. quarter + 16th at the same
    # offset), the 16th (dur=0.332) would land *after* the quarter (dur=1.0)
    # in ascending order, so `notes[-1]` picked the 16th dur as `top_dur`.
    # Caller then used `top_dur` as `beat_dur` to advance cursor, which was
    # too short → next offset 16ths (off=0.332, 0.664, 1.0) were silently
    # dropped because they fell at or before the under-advanced cursor.
    # Verified reproduction: ch23-06_F major m1 (XML 10 events) lost 5 to
    # `_collect_per_part_voice_notes`, surfacing as BAD_DURATION in
    # /solve-melody.
    notes.sort(key=lambda n: n[0])  # ascending by pc+oct*12 only
    top_dur = notes[-1][2]
    top = notes[-1][1]
    if len(notes) > 1:
        bot = notes[0][1]
        bot_dur = notes[0][2]
    else:
        bot = None
        bot_dur = None
    return (top, top_dur, bot, bot_dur)


def _events_to_voice_entries(
    events: list[dict],
    capacity_ql: float,
) -> list[tuple[str | None, float]]:
    """Convert one voice's events (already filtered by voice id, assumed
    in offset order or unsorted — we re-sort) into (pitch, dur_ql) tuples.

    Pitch is None for a rest.  Rest is auto-inserted at the start, between
    gaps, and to fill the tail of the measure.

    P22.5 supervise v2 (2026-08-17): per-voice linearisation.  Replaces
    the chord-top/bot model that wrongly merged a piano SATB main-melody
    half note with its 16th-note grace ornaments (ch23-06_F major m1
    was losing 5 of 8 events because the chord model short-circuited on
    the shortest duration at each offset).
    """
    entries: list[tuple[str | None, float]] = []
    cursor_ql = 0.0
    sorted_events = sorted(
        events,
        key=lambda e: (float(e.get("offset", 0.0) or 0.0), -float(e.get("duration", 0.0) or 0.0)),
    )
    for e in sorted_events:
        # Grace notes do not consume solver time. ScoreIR retains them and the
        # projection diagnostics disclose that the teaching editor omits them.
        if e.get("grace"):
            continue
        off = float(e.get("offset", 0.0) or 0.0)
        if e.get("type") == "rest":
            dur = float(e.get("duration", 1.0) or 1.0)
            if off > cursor_ql:
                entries.append((None, off - cursor_ql))
            # rest 自身不产生 entry, 只 advance cursor
                cursor_ql = off
            rest_end = off + dur
            if rest_end > cursor_ql:
                entries.append((None, rest_end - cursor_ql))
                cursor_ql = rest_end
            continue
        if e.get("type") == "note":
            pitch = e.get("pitch")
            if not pitch:
                continue
        elif e.get("type") == "chord":
            # chord inside one voice: take top-most pitch as the voice's note
            pitches = e.get("pitches") or []
            if not pitches:
                continue
            pitch = max(pitches, key=_pitch_sort_key)
        else:
            continue
        dur = float(e.get("duration", 1.0) or 1.0)
        if off > cursor_ql:
            entries.append((None, off - cursor_ql))
        entries.append((pitch, dur))
        cursor_ql = max(cursor_ql, off + dur)
    if cursor_ql < capacity_ql:
        entries.append((None, capacity_ql - cursor_ql))
    return entries


def _pitch_sort_key(pitch: str) -> int:
    """Sort key for pitch strings like 'C4', 'F#3', 'B-2' → (pc, oct*12).
    Mirrors _pitch_to_pc_oct so chords inside a voice pick the highest
    pitch deterministically.
    """
    pc, oct_ = _pitch_to_pc_oct(pitch)
    if pc < 0 or oct_ < 0:
        return -1
    return oct_ * 12 + pc


def _voice_sort_key(voice_id: str) -> tuple[int, int | str]:
    if voice_id == "_no_voice":
        return (2, voice_id)
    try:
        return (0, int(voice_id))
    except (TypeError, ValueError):
        return (1, str(voice_id))


def _has_voice_field(part: dict) -> bool:
    """True if any event in this part has a non-None `voice` field."""
    for m in part.get("measures", []):
        for e in m.get("events", []):
            if e.get("voice") is not None:
                return True
    return False


def _measure_voice_count(part: dict, measure_index: int) -> int:
    measures = part.get("measures", []) or []
    if measure_index >= len(measures):
        return 0
    return len({
        str(event.get("voice") or "_no_voice")
        for event in measures[measure_index].get("events", []) or []
    })


def _part_max_voice_count(part: dict) -> int:
    return max(
        (_measure_voice_count(part, index) for index, _ in enumerate(part.get("measures", []) or [])),
        default=0,
    )


def _collect_per_part_voice_notes_v1(
    part: dict,
) -> tuple[list[list[tuple[str | None, float]]], list[list[tuple[str | None, float]]]]:
    """LEGACY: chord-top/bot model.  Kept as a fallback for tests / hand-crafted
    payloads that don't carry a `voice` field.  See `_collect_per_part_voice_notes_v2`
    for the SATB-correct per-voice path.
    """
    top_per_m: list[list[tuple[str | None, float]]] = []
    bot_per_m: list[list[tuple[str | None, float]]] = []
    for m in part.get("measures", []):
        # group events by offset
        by_off: dict[float, list[dict]] = defaultdict(list)
        for e in m.get("events", []):
            by_off[e.get("offset", 0.0)].append(e)

        capacity_ql = _measure_capacity_ql(m.get("timeSignature"))

        top_entries: list[tuple[str | None, float]] = []
        bot_entries: list[tuple[str | None, float]] = []
        cursor_ql = 0.0  # 累计已经走过的时值 (quarter)
        for off in sorted(by_off.keys()):
            top, top_dur, bot, bot_dur = _split_chord_to_voices(by_off[off])
            # gap before this offset?
            if off > cursor_ql:
                gap_ql = float(off) - cursor_ql
                top_entries.append((None, gap_ql))
                bot_entries.append((None, gap_ql))
            # 拍点上: top (S/T) + bot (A/B)
            # P22.5 supervise v2 (2026-08-17): beat_dur 必须用 max(top_dur, bot_dur)
            # 当同 offset 多 voice dur 不同时 (如 quarter + 16th),
            # 用 top_dur 单独推 cursor 会漏掉 bot 那个长 dur 的延续部分.
            # 用 max 保证 cursor 至少覆盖到最长 note 的尾部.
            candidates = [d for d in (top_dur, bot_dur) if d is not None]
            beat_dur = max(candidates) if candidates else 1.0
            if top:
                top_entries.append((top, beat_dur))
            if bot:
                bot_entries.append((bot, beat_dur))
            elif top:
                # 单 voice part: bot 不存在, 不补 (top 已有)
                pass
            else:
                # 都没有音, 但 _split_chord_to_voices 返 (None, None, None, None)
                # 此时 cursor 不应推进
                pass
            cursor_ql = max(cursor_ql, float(off) + beat_dur)

        # 末尾补 rest 填满小节
        if cursor_ql < capacity_ql:
            gap_ql = capacity_ql - cursor_ql
            top_entries.append((None, gap_ql))
            bot_entries.append((None, gap_ql))

        top_per_m.append(top_entries)
        bot_per_m.append(bot_entries)
    return top_per_m, bot_per_m


def _collect_per_part_voice_notes_v2(
    part: dict,
) -> tuple[list[list[tuple[str | None, float]]], list[list[tuple[str | None, float]]]]:
    """P22.5 supervise v2 (2026-08-17): per-voice split for piano SATB.

    Returns (top_entries, bot_entries) per measure, where:
      - top = events from the lowest-numbered voice in this part
              (e.g. voice '1' = the primary / upper-line voice in a piano
              SATB treble staff)
      - bot = events from the second-lowest voice in this part
              (e.g. voice '2' = the secondary / lower-line voice)

    This replaces the chord-top/bot model that incorrectly merged a
    half-note main melody with 16th-note ornaments at the same offset
    (ch23-06_F major m1 went from 3 entries to 8).  See
    tests/_supervise_reader_bug.md for the full root-cause writeup.
    """
    top_per_m: list[list[tuple[str | None, float]]] = []
    bot_per_m: list[list[tuple[str | None, float]]] = []
    all_voice_ids = {
        str(event.get("voice"))
        for measure in part.get("measures", []) or []
        for event in measure.get("events", []) or []
        if event.get("voice") is not None
    }
    has_unvoiced = any(
        event.get("voice") is None
        for measure in part.get("measures", []) or []
        for event in measure.get("events", []) or []
    )
    if has_unvoiced:
        all_voice_ids.add("_no_voice")
    stable_voice_ids = sorted(all_voice_ids, key=_voice_sort_key)
    top_voice = stable_voice_ids[0] if stable_voice_ids else None
    bot_voice = stable_voice_ids[1] if len(stable_voice_ids) > 1 else None
    for m in part.get("measures", []):
        capacity_ql = _measure_capacity_ql(m.get("timeSignature"))

        by_voice: dict[str, list[dict]] = defaultdict(list)
        for e in m.get("events", []):
            v = e.get("voice")
            # events without voice id go to a sentinel bucket so they're
            # not lost (still surfaced through top)
            by_voice[str(v) if v is not None else "_no_voice"].append(e)

        top_events = by_voice.get(top_voice, []) if top_voice else []
        bot_events = by_voice.get(bot_voice, []) if bot_voice else []

        top_per_m.append(_events_to_voice_entries(top_events, capacity_ql))
        bot_per_m.append(_events_to_voice_entries(bot_events, capacity_ql))
    return top_per_m, bot_per_m


def _collect_per_part_voice_notes(
    part: dict,
) -> tuple[list[list[tuple[str | None, float]]], list[list[tuple[str | None, float]]]]:
    """Dispatch entry-point: per-voice split when events have `voice` field,
    legacy chord-top/bot otherwise.
    """
    distinct_voices = {
        str(event.get("voice"))
        for measure in part.get("measures", []) or []
        for event in measure.get("events", []) or []
        if event.get("voice") is not None
    }
    has_multitone_chord = any(
        event.get("type") == "chord" and len(event.get("pitches") or []) > 1
        for measure in part.get("measures", []) or []
        for event in measure.get("events", []) or []
    )
    if _has_voice_field(part) and not (len(distinct_voices) <= 1 and has_multitone_chord):
        return _collect_per_part_voice_notes_v2(part)
    return _collect_per_part_voice_notes_v1(part)


_ROLE_ORDER = ("soprano", "alto", "tenor", "bass")


def _stream_pitch_midis(measures: list[list[tuple[str | None, float]]]) -> list[int]:
    values = []
    for measure in measures:
        for pitch, _duration in measure:
            if pitch is None:
                continue
            pc, octave = _pitch_to_pc_oct(pitch)
            if pc >= 0 and octave >= 0:
                values.append(pc + octave * 12)
    return values


def _stream_has_pitches(measures: list[list[tuple[str | None, float]]]) -> bool:
    return bool(_stream_pitch_midis(measures))


def _stream_median_midi(measures: list[list[tuple[str | None, float]]]) -> float:
    values = sorted(_stream_pitch_midis(measures))
    if not values:
        return float("-inf")
    middle = len(values) // 2
    if len(values) % 2:
        return float(values[middle])
    return (values[middle - 1] + values[middle]) / 2.0


def _part_role_hint(part: dict) -> str | None:
    text = f"{part.get('name', '')} {part.get('id', '')}".lower()
    aliases = {
        "soprano": ("soprano", "sop", "女高音"),
        "alto": ("alto", "contralto", "女低音"),
        "tenor": ("tenor", "男高音"),
        "bass": ("bass", "basso", "男低音"),
    }
    for role, names in aliases.items():
        if any(name in text for name in names):
            return role
    return None


def _single_part_role(part: dict, measures: list[list[tuple[str | None, float]]]) -> tuple[str | None, str, str]:
    hinted = _part_role_hint(part)
    if hinted:
        return hinted, "high", "part-label"
    first_measure = next((m for m in part.get("measures", []) or [] if m.get("clef")), None)
    active_clef = (first_measure or {}).get("clef") or {}
    sign = str(active_clef.get("sign") or "").upper()
    line = active_clef.get("line")
    if sign == "G":
        return "soprano", "high", "treble-clef"
    if sign == "F":
        return "bass", "high", "bass-clef"
    if sign == "C" and line == 3:
        return "alto", "high", "alto-clef"
    if sign == "C" and line == 4:
        return "tenor", "high", "tenor-clef"

    median = _stream_median_midi(measures)
    if median == float("-inf"):
        return None, "low", "no-pitched-events"
    if median >= 60:
        return "soprano", "low", "pitch-range"
    if median <= 48:
        return "bass", "low", "pitch-range"
    return None, "low", "overlapping-inner-voice-range"


def _entries_for_role(
    measures: list[list[tuple[str | None, float]]], role: str
) -> list[list[dict]]:
    return [[_make_entry(pitch, role, duration) for pitch, duration in measure] for measure in measures]


def _assess_key(parts: list[dict], analyzed: dict) -> dict[str, Any]:
    first_key = None
    if parts and parts[0].get("measures"):
        first_key = parts[0]["measures"][0].get("keySignature") or None
    analyzed_label = analyzed.get("label")
    correlation = float(analyzed.get("correlation") or 0.0)
    declared_label = first_key.get("declaredLabel") if first_key else None
    canonical_export = bool(parts and parts[0].get("name") == "Manual Score")
    if declared_label and (canonical_export or analyzed_label == declared_label):
        return {
            "key": declared_label,
            "confidence": "high",
            "source": "explicit-key",
            "correlation": correlation,
            "candidates": [declared_label],
        }
    candidates = []
    if first_key:
        candidates = [
            value for value in (first_key.get("majorName"), first_key.get("minorName"))
            if value
        ]
    if declared_label and analyzed_label in candidates and analyzed_label != declared_label:
        confidence = "medium" if correlation >= 0.75 else "low"
        source = "explicit-mode-conflict"
    elif candidates and analyzed_label in candidates:
        confidence = "medium" if correlation >= 0.75 else "low"
        source = "key-signature-plus-analysis"
    elif candidates:
        confidence = "low"
        source = "key-signature-conflict"
    else:
        confidence = "medium" if correlation >= 0.8 else "low"
        source = "pitch-analysis-only"
    return {
        "key": analyzed_label or (candidates[0] if candidates else None),
        "confidence": confidence,
        "source": source,
        "correlation": correlation,
        "candidates": candidates,
    }


def reader_payload_to_editor(payload: dict) -> dict:
    """Convert /read-score payload → editor entry 格式 (喂 /solve-melody).

    Args:
      payload: reader.read_score() return value (see reader.py)

    Returns:
      {
        "key": "A minor",              # from summary.analyzedKey.label
        "timeSignature": "4/4",        # from summary
        "sopranoMeasures": [...],      # S = treble voice 1
        "altoMeasures":    [...],      # A = treble voice 2
        "tenorMeasures":   [...],      # T = bass voice 1
        "bassMeasures":    [...],      # B = bass voice 2
        "melodyMeasures":  [...],      # alias = sopranoMeasures (backward compat)
        "source": {...},
        "warnings": [...],
      }

    P2.7.1 fix: 之前只返 melody + bass, 把 alto + tenor 丢了.
    现在按 SATB 4 voice 拆:
      - 1 part: 只能拆 S + B (单 part 没法知道 alto/tenor 在哪)
      - 2 parts (典型 SATB piano score, treble + bass 大谱表):
          part[0]  (treble staff) → S=top, A=bot
          part[-1] (bass staff)   → T=top, B=bot
      - 3+ parts: first=treble (S+A), last=bass (T+B), middle drop
    """
    summary = payload.get("summary", {}) or {}
    analyzed = summary.get("analyzedKey", {}) or {}
    score_ir = payload.get("scoreIr")
    if isinstance(score_ir, dict):
        parts = score_ir_to_reader_parts(score_ir)
        score_ir_validation = validate_score_ir(score_ir)
        projection = analyze_editor_projection(score_ir)
    else:
        parts = payload.get("parts", [])
        score_ir_validation = None
        projection = None
    declared_key = None
    if parts and parts[0].get("measures"):
        first_key = parts[0]["measures"][0].get("keySignature") or {}
        declared_key = first_key.get("declaredLabel")
    analyzed_key = analyzed.get("label")
    key_assessment = _assess_key(parts, analyzed)
    is_frontend_export = bool(parts and parts[0].get("name") == "Manual Score")
    if declared_key and (is_frontend_export or not analyzed_key):
        key = declared_key
    else:
        key = analyzed_key or declared_key or "C major"

    # P2.7.1 fix: time signature 从 parts[0].measures[0].timeSignature 取,
    # 不要从 summary.timeSignature fallback "4/4" — reader.py 不填这个字段,
    # 之前 ch4-01 真实 2/4 被默认成 4/4, 八分音符/十六分音符都错位.
    # 注意: reader.py 存的是 dict {"ratio": "2/4", "barDurationQuarterLength": 2.0}
    n_parts = len(parts)
    ts = None
    if n_parts and parts[0].get("measures"):
        first_m = parts[0]["measures"][0]
        ts_raw = first_m.get("timeSignature")
        if isinstance(ts_raw, dict):
            ts = ts_raw.get("ratio")
        elif isinstance(ts_raw, str):
            ts = ts_raw
    if not ts:
        ts = summary.get("timeSignature") or "4/4"

    soprano_measures: list[list[dict]] = []
    alto_measures:    list[list[dict]] = []
    tenor_measures:   list[list[dict]] = []
    bass_measures:    list[list[dict]] = []
    unassigned_voices: list[dict[str, Any]] = []
    voice_assignment: dict[str, Any] = {
        "version": "satb-assignment-v1",
        "method": "none",
        "confidence": "low",
        "roles": [],
        "issues": [],
    }

    if n_parts == 0:
        pass  # 全空
    elif n_parts == 1:
        # 单 part: 没法拆 alto/tenor, 只 S + B
        top_per, bot_per = _collect_per_part_voice_notes(parts[0])
        if _stream_has_pitches(bot_per):
            soprano_measures = _entries_for_role(top_per, "soprano")
            bass_measures = _entries_for_role(bot_per, "bass")
            voice_assignment.update({
                "method": "single-part-extremes",
                "confidence": "medium",
                "roles": [
                    {"role": "soprano", "partIndex": 1, "source": "upper-stream"},
                    {"role": "bass", "partIndex": 1, "source": "lower-stream"},
                ],
                "issues": ["A single part with multiple streams cannot prove inner SATB identity."],
            })
        else:
            role, confidence, evidence = _single_part_role(parts[0], top_per)
            if role == "soprano":
                soprano_measures = _entries_for_role(top_per, role)
            elif role == "alto":
                alto_measures = _entries_for_role(top_per, role)
            elif role == "tenor":
                tenor_measures = _entries_for_role(top_per, role)
            elif role == "bass":
                bass_measures = _entries_for_role(top_per, role)
            else:
                unassigned_voices.append({
                    "partIndex": 1,
                    "reason": evidence,
                    "measures": _entries_for_role(top_per, "unassigned"),
                })
            voice_assignment.update({
                "method": "single-stream-classification",
                "confidence": confidence,
                "roles": ([{"role": role, "partIndex": 1, "source": evidence}] if role else []),
                "issues": ([] if role else ["The single stream lies in an overlapping SATB range."]),
            })
    elif n_parts == 4 and all(_part_max_voice_count(part) <= 1 for part in parts):
        # Choral MusicXML commonly stores S/A/T/B as four independent parts.
        role_sources = []
        for part in parts:
            primary, _secondary = _collect_per_part_voice_notes(part)
            role_sources.append(primary)
        assigned: dict[str, int] = {}
        labelled_parts: set[int] = set()
        for part_index, part in enumerate(parts):
            hint = _part_role_hint(part)
            if hint and hint not in assigned:
                assigned[hint] = part_index
                labelled_parts.add(part_index)
        remaining_parts = sorted(
            (index for index in range(4) if index not in labelled_parts),
            key=lambda index: _stream_median_midi(role_sources[index]),
            reverse=True,
        )
        remaining_roles = [role for role in _ROLE_ORDER if role not in assigned]
        for role, part_index in zip(remaining_roles, remaining_parts):
            assigned[role] = part_index

        soprano_measures = _entries_for_role(role_sources[assigned["soprano"]], "soprano")
        alto_measures = _entries_for_role(role_sources[assigned["alto"]], "alto")
        tenor_measures = _entries_for_role(role_sources[assigned["tenor"]], "tenor")
        bass_measures = _entries_for_role(role_sources[assigned["bass"]], "bass")
        voice_assignment.update({
            "method": "labels-and-pitch-order",
            "confidence": "high" if len(labelled_parts) == 4 else "medium",
            "roles": [
                {
                    "role": role,
                    "partIndex": assigned[role] + 1,
                    "partId": parts[assigned[role]].get("id"),
                    "medianMidi": _stream_median_midi(role_sources[assigned[role]]),
                    "source": "part-label" if assigned[role] in labelled_parts else "pitch-order",
                }
                for role in _ROLE_ORDER
            ],
            "issues": ([] if len(labelled_parts) == 4 else ["Unlabelled parts were ordered by median pitch."]),
        })
    else:
        # 2+ parts: part[0] 拆 S + A, part[-1] 拆 T + B
        s_per, a_per = _collect_per_part_voice_notes(parts[0])
        bass_part = parts[-1]
        t_per, b_per = _collect_per_part_voice_notes(bass_part)
        soprano_measures = [[_make_entry(p, "soprano", d) for p, d in m] for m in s_per]
        alto_measures    = [[_make_entry(p, "alto",    d) for p, d in m] for m in a_per]
        for measure_index, (top_measure, bottom_measure) in enumerate(zip(t_per, b_per)):
            # A lone line on the lower staff is the bass anchor. If a second
            # voice appears, the upper/lower pair maps to tenor/bass.
            if not _stream_has_pitches([bottom_measure]):
                tenor_source, bass_source = bottom_measure, top_measure
            else:
                tenor_source, bass_source = top_measure, bottom_measure
            tenor_measures.append([_make_entry(p, "tenor", d) for p, d in tenor_source])
            bass_measures.append([_make_entry(p, "bass", d) for p, d in bass_source])
        voice_assignment.update({
            "method": "upper-lower-staff-pairs",
            "confidence": "medium",
            "roles": [
                {"role": "soprano", "partIndex": 1, "source": "upper-staff-primary"},
                {"role": "alto", "partIndex": 1, "source": "upper-staff-secondary"},
                {"role": "tenor", "partIndex": n_parts, "source": "lower-staff-primary"},
                {"role": "bass", "partIndex": n_parts, "source": "lower-staff-secondary-or-only"},
            ],
            "issues": ([] if n_parts == 2 else ["Middle parts are not represented by the teaching editor."]),
        })

    warnings = list(payload.get("warnings", []) or [])

    result = {
        "key": key,
        "keyAssessment": key_assessment,
        "timeSignature": ts,
        "sopranoMeasures": soprano_measures,
        "altoMeasures":    alto_measures,
        "tenorMeasures":   tenor_measures,
        "bassMeasures":    bass_measures,
        "voiceAssignment": voice_assignment,
        "unassignedVoices": unassigned_voices,
        # Backward compat alias (老 client / 测试还在用 melodyMeasures)
        "melodyMeasures":  soprano_measures,
        "source": {
            "engine": "reader-to-editor",
            "version": "P2.7.1",
            "inputFile": summary.get("inputFile", "(unknown)"),
            "nParts": n_parts,
        },
        "warnings": warnings,
    }
    if isinstance(score_ir, dict):
        result["scoreIr"] = score_ir
        result["scoreIrValidation"] = score_ir_validation
        result["editorProjection"] = projection
    return result


if __name__ == "__main__":
    # smoke test against an actual ch4-01 XML
    import json
    import urllib.request
    import urllib.parse
    import mimetypes
    from pathlib import Path

    URL = "http://127.0.0.1:8770/read-score"
    XML = Path(r"C:\Users\Administrator\Documents\try\eval-data\extracted\hamony dataset\ch4\original\ch4-01_a minor.xml")

    boundary = "----TestBoundary12345"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{XML.name}"\r\n'
        f"Content-Type: {mimetypes.guess_type(XML.name)[0]}\r\n"
        f"\r\n"
    ).encode("utf-8") + XML.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(URL, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read())

    out = reader_payload_to_editor(payload)
    print(f"key = {out['key']}")
    print(f"timeSignature = {out['timeSignature']}")
    print(f"melodyMeasures: {len(out['melodyMeasures'])} measures")
    for mi, m in enumerate(out["melodyMeasures"]):
        s = " | ".join((e["pitches"][0]["display"] if e["kind"] == "note" else "rest") for e in m)
        print(f"  m{mi+1}: {s}")
    print(f"bassMeasures: {len(out['bassMeasures'])} measures")
    for mi, m in enumerate(out["bassMeasures"]):
        s = " | ".join((e["pitches"][0]["display"] if e["kind"] == "note" else "rest") for e in m)
        print(f"  m{mi+1}: {s}")
