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
        if e.get("type") != "note":
            continue
        pitch = e.get("pitch", "")
        if not pitch:
            continue
        pc, oct_ = _pitch_to_pc_oct(pitch)
        if pc < 0 or oct_ < 0:
            continue
        dur_ql = e.get("duration", 1.0) or 1.0
        notes.append((pc + oct_ * 12, pitch, float(dur_ql)))
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


def _pitch_sort_key(pitch: str) -> tuple[int, int]:
    """Sort key for pitch strings like 'C4', 'F#3', 'B-2' → (pc, oct*12).
    Mirrors _pitch_to_pc_oct so chords inside a voice pick the highest
    pitch deterministically.
    """
    pc, oct_ = _pitch_to_pc_oct(pitch)
    if pc < 0 or oct_ < 0:
        return (0, -1)
    return (pc, oct_ * 12)


def _has_voice_field(part: dict) -> bool:
    """True if any event in this part has a non-None `voice` field."""
    for m in part.get("measures", []):
        for e in m.get("events", []):
            if e.get("voice") is not None:
                return True
    return False


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
    for m in part.get("measures", []):
        capacity_ql = _measure_capacity_ql(m.get("timeSignature"))

        by_voice: dict[str, list[dict]] = defaultdict(list)
        for e in m.get("events", []):
            v = e.get("voice")
            # events without voice id go to a sentinel bucket so they're
            # not lost (still surfaced through top)
            by_voice[v if v is not None else "_no_voice"].append(e)

        voice_ids_sorted = sorted(
            by_voice.keys(),
            key=lambda v: (v == "_no_voice", v),
        )
        top_voice = voice_ids_sorted[0] if voice_ids_sorted else None
        bot_voice = voice_ids_sorted[1] if len(voice_ids_sorted) > 1 else None

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
    if _has_voice_field(part):
        return _collect_per_part_voice_notes_v2(part)
    return _collect_per_part_voice_notes_v1(part)


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
    parts = payload.get("parts", [])
    declared_key = None
    if parts and parts[0].get("measures"):
        first_key = parts[0]["measures"][0].get("keySignature") or {}
        declared_key = first_key.get("declaredLabel")
    analyzed_key = analyzed.get("label")
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

    if n_parts == 0:
        pass  # 全空
    elif n_parts == 1:
        # 单 part: 没法拆 alto/tenor, 只 S + B
        top_per, bot_per = _collect_per_part_voice_notes(parts[0])
        soprano_measures = [[_make_entry(p, "soprano", d) for p, d in m] for m in top_per]
        bass_measures    = [[_make_entry(p, "bass",    d) for p, d in m] for m in bot_per]
    else:
        # 2+ parts: part[0] 拆 S + A, part[-1] 拆 T + B
        s_per, a_per = _collect_per_part_voice_notes(parts[0])
        t_per, b_per = _collect_per_part_voice_notes(parts[-1])
        soprano_measures = [[_make_entry(p, "soprano", d) for p, d in m] for m in s_per]
        alto_measures    = [[_make_entry(p, "alto",    d) for p, d in m] for m in a_per]
        tenor_measures   = [[_make_entry(p, "tenor",   d) for p, d in m] for m in t_per]
        bass_measures    = [[_make_entry(p, "bass",    d) for p, d in m] for m in b_per]

    warnings = list(payload.get("warnings", []) or [])

    return {
        "key": key,
        "timeSignature": ts,
        "sopranoMeasures": soprano_measures,
        "altoMeasures":    alto_measures,
        "tenorMeasures":   tenor_measures,
        "bassMeasures":    bass_measures,
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
