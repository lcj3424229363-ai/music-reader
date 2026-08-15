# -*- coding: utf-8 -*-
"""
solver_cli.py — 纯文本 4-part harmony solver

手动输入旋律 → 自动配四部和声 (P0-P7.7 全部).

输入格式 (midi 音名 + 节奏, 用 || 分小节):
  C5 E5 G5 E5 || F5 F5 F5 F5 || G5 G5 G5 G5 || C5 C5 C5 C5

  - 音名: C4 C#4 Db4 D4 ... (大小写都行, #/b 升降号都支持)
  - 节奏: 默认每拍 1 个音 (一拍=quarter).  加 '2' = half note (2 拍)
          加 '4.' = dotted quarter (1.5 拍), 加 '8' = eighth (0.5 拍)
          例如: C5/2 E5/4. G5/8 A5/4
  - || 分小节, 必须每小节时值 = 拍号拍数 (4/4 = 4 拍)
  - 拍号: -t 4/4 (默认) / 3/4 / 6/8

输出: 4 部 SATB + 罗马数字 + cadence + 终止式 + 警告.

例:
  python solver_cli.py -k Eb -t 4/4 "Eb5. Bb4 || Eb5 G5 F5 Eb5 || ..."
"""
import argparse
import sys
import re

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from solver import Note, solve_melody, Chord, Key


DURATION_MAP = {
    '': 1.0,    # 默认 quarter = 1 拍
    '4': 1.0,   # quarter
    '4.': 1.5,  # dotted quarter
    '2': 2.0,   # half
    '2.': 3.0,  # dotted half
    '1': 4.0,   # whole
    '8': 0.5,   # eighth
    '8.': 0.75, # dotted eighth
    '16': 0.25, # sixteenth
}


def parse_token(tok: str) -> tuple[Note, float]:
    """Parse a token like 'C5' or 'Eb5/2.' or 'F#4/4.' into (Note, duration_in_beats)."""
    tok = tok.strip()
    if not tok:
        raise ValueError("empty token")
    # Split note name from duration suffix
    if '/' in tok:
        name, dur_str = tok.split('/', 1)
        dur_str = dur_str.strip()
    else:
        name = tok
        dur_str = ''
    if dur_str not in DURATION_MAP:
        raise ValueError(f"unknown duration {dur_str!r} in {tok!r}; valid: {sorted(DURATION_MAP.keys())}")
    dur = DURATION_MAP[dur_str]
    try:
        n = Note.from_name(name)
    except Exception as e:
        raise ValueError(f"bad note name {name!r}: {e}")
    return n, dur


def parse_measure(measure_str: str, capacity: float) -> list[tuple[Note, float]]:
    """Parse a single measure like 'Eb5. Bb4' or 'Eb5/2. Bb4/4' into a list of (Note, dur)."""
    if not measure_str.strip():
        raise ValueError("empty measure")
    toks = re.split(r'\s+', measure_str.strip())
    parsed = [parse_token(t) for t in toks if t]
    total = sum(d for _, d in parsed)
    # Round to nearest 0.25 to tolerate 6/8 vs 2/4 etc.
    if abs(total - capacity) > 0.01:
        raise ValueError(
            f"measure time-value {total} doesn't fit capacity {capacity}; "
            f"got tokens: {[t for t in toks]}"
        )
    return parsed


def parse_melody(input_str: str, beats_per_measure: int, beat_unit: float) -> list[list[Note]]:
    """Parse 'm1 || m2 || ...' into [[Note, ...] for m1, [Note, ...] for m2, ...].
    
    Each measure's notes are flattened to per-beat Note list (one Note per beat).
    A note with duration > 1 beat is repeated across its beats (so the
    melody's per-beat slot stays full).
    """
    capacity = beats_per_measure * beat_unit
    measure_strs = [m.strip() for m in input_str.split('||')]
    if not measure_strs or not measure_strs[0]:
        raise ValueError("empty melody")
    result: list[list[Note]] = []
    for i, m_str in enumerate(measure_strs, 1):
        if not m_str:
            raise ValueError(f"empty measure {i}")
        notes_durs = parse_measure(m_str, capacity)
        per_beat: list[Note] = []
        for n, d in notes_durs:
            # Repeat the note for d beats
            n_repeats = round(d / beat_unit)
            if abs(n_repeats * beat_unit - d) > 0.01:
                raise ValueError(f"note {n.name} duration {d} not a multiple of beat_unit {beat_unit}")
            per_beat.extend([n] * n_repeats)
        if len(per_beat) != beats_per_measure:
            raise ValueError(
                f"measure {i} produced {len(per_beat)} beats, expected {beats_per_measure}"
            )
        result.append(per_beat)
    return result


def format_result(r) -> str:
    """Pretty-print the SolveResult."""
    lines = []
    lines.append('=' * 70)
    lines.append(f"Key: {r.summary['key']}  Time: {r.summary['timeSignature']}  Measures: {r.summary['measureCount']}")
    lines.append(f"Cadences: {' → '.join(c or '·' for c in r.summary['cadences'])}")
    lines.append(f"Score: {r.summary['score']:.1f}  Qualify: {r.summary['qualify']}")
    lines.append('=' * 70)
    for m in r.measures:
        lines.append('')
        lines.append(f"--- Measure {m['number']}  (cadence: {m['cadence'] or '·'}) ---")
        for b in m['beats']:
            mark = ''
            if b['multi_voice_suspension'] != 'none':
                mark = f"  ← {b['multi_voice_suspension']} susp"
            nct = b['non_chord_tone']
            nct_str = f" [{nct}]" if nct and nct != 'none' else ''
            lines.append(
                f"  b{b['beat']}: S={b['soprano']:>4} A={b['alto']:>4} "
                f"T={b['tenor']:>4} B={b['bass']:>4}  "
                f"rom={b['roman']:>6} fig={b['figure']:>4} inv={b['inversion']:>4} "
                f"func={b['function']:>4} dbl={b['doubled']:>5}{nct_str}{mark}"
            )
    if r.warnings:
        lines.append('')
        lines.append('--- Warnings ---')
        for w in r.warnings:
            lines.append(f"  ⚠ {w}")
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(description="4-part harmony solver — text CLI")
    ap.add_argument('-k', '--key', default='C', help='调性: C, a, F#, Bb, eb 等')
    ap.add_argument('-t', '--time', default='4/4', help='拍号: 4/4, 3/4, 6/8 (默认 4/4)')
    ap.add_argument('melody', help='旋律 (用 || 分小节): "C5 E5 G5 E5 || F5 F5 F5 F5 || ..."')
    args = ap.parse_args()

    # 拍号
    try:
        num, den = args.time.split('/')
        beats_per_measure = int(num)
        beat_unit = 4.0 / int(den)  # quarter = 1 拍 (其他按比例)
    except Exception as e:
        print(f"bad time signature {args.time!r}: {e}", file=sys.stderr)
        sys.exit(2)

    # 解析 melody
    try:
        melody = parse_melody(args.melody, beats_per_measure, beat_unit)
    except ValueError as e:
        print(f"melody parse error: {e}", file=sys.stderr)
        sys.exit(2)

    # 跑 solver
    try:
        r = solve_melody(args.key, args.time, melody)
    except Exception as e:
        print(f"solver error: {e}", file=sys.stderr)
        sys.exit(1)

    print(format_result(r))


if __name__ == '__main__':
    main()
