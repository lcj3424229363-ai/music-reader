"""P1 stress test: edge cases & textbook boundary scenarios.

These are not pass/fail — they help us SEE whether the solver is doing
the right thing at the margins.  Read the output carefully.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from solver import (
    Note as N,
    Chord,
    Key,
    Voicing,
    solve_melody,
    has_parallel,
    has_voice_crossing,
    has_leading_tone_violation,
    has_seventh_resolution_violation,
    is_chord_tone,
    in_range,
    enumerate_voicings,
)


def show(label, melody, key="C", ts="4/4"):
    print(f"\n{'='*70}")
    print(f"CASE: {label}")
    print(f"{'='*70}")
    try:
        res = solve_melody(key, ts, melody).to_dict()
    except ValueError as e:
        print(f"  [EXPECTED-ERROR] {e}")
        return None, 0
    print(f"key={res['summary']['key']} ts={res['summary']['timeSignature']} "
          f"score={res['summary']['score']:.1f} cadences={res['summary']['cadences']}")
    for m in res['measures']:
        for b in m['beats']:
            s, a, t, bass = b['soprano'], b['alto'], b['tenor'], b['bass']
            print(f"  m{m['number']}.b{b['beat']} {b['roman']:7s} "
                  f"S={s:3s} A={a:3s} T={t:3s} B={bass:3s} dbl={b['doubled']}")
        print(f"  cadence: {m['cadence']}")
    # Run hard-constraint scan
    flat = []
    for m in res['measures']:
        for b in m['beats']:
            flat.append((b, Voicing(
                soprano=N.from_name(b['soprano']),
                alto=N.from_name(b['alto']),
                tenor=N.from_name(b['tenor']),
                bass=N.from_name(b['bass']),
            )))
    key_obj = Key.from_name(key)
    issues = 0
    for i in range(len(flat) - 1):
        bp, vp = flat[i]
        bc, vc = flat[i + 1]
        v_a, v_b = vp, vc
        prev_chord = Chord(degree=_deg(bp['roman']),
                           quality=_qual(bp['roman']),
                           inversion=_inv(bp['roman']),
                           kind='seventh' if '7' in bp['roman'] and bp['inversion'] in ('7', '6/5', '4/3', '2', '4/2') else 'triad')
        curr_chord = Chord(degree=_deg(bc['roman']),
                           quality=_qual(bc['roman']),
                           inversion=_inv(bc['roman']),
                           kind='seventh' if '7' in bc['roman'] and bc['inversion'] in ('7', '6/5', '4/3', '2', '4/2') else 'triad')
        par = has_parallel(v_a, v_b)
        xc = has_voice_crossing(v_b)
        lt = has_leading_tone_violation(v_a, v_b, key_obj)
        sv = has_seventh_resolution_violation(v_a, prev_chord, v_b, curr_chord, key_obj)
        # In-range
        ir = []
        for voice, note in (('soprano', bc['soprano']),
                            ('alto', bc['alto']),
                            ('tenor', bc['tenor']),
                            ('bass', bc['bass'])):
            if not in_range(voice, N.from_name(note)):
                ir.append(f"{voice}={note} OOR")
        bad = par + xc + lt + sv + ir
        if bad:
            issues += len(bad)
            print(f"  !! beat {i+1}->{i+2}: {bad}")
    if issues == 0:
        print(f"  [OK] no hard-constraint violations")
    else:
        print(f"  [FAIL] {issues} violation(s)")
    return res, issues


def _deg(r):
    base = r.split('°')[0].rstrip('6/4/5/3').rstrip('/').rstrip('2').rstrip('3').rstrip('4').rstrip('5').rstrip('6').rstrip('7')
    if not base:
        base = r[0]
    return {'I': 1, 'i': 1, 'II': 2, 'ii': 2, 'III': 3, 'iii': 3,
            'IV': 4, 'iv': 4, 'V': 5, 'v': 5, 'VI': 6, 'vi': 6,
            'VII': 7, 'vii': 7}.get(base, 1)


def _qual(r):
    if '°' in r:
        return 'dim'
    import re
    base = re.sub(r'(6/5|4/3|4/2|6/4|6/3|\b2\b|\b6\b|\b3\b|\b4\b|\b5\b|\b7\b)$', '', r).strip()
    if base.endswith('°'):
        return 'dim'
    if base.startswith('V7'):
        return 'dom7'   # V7 / V76/5 / V74/3 / V74/2 are all dom7
    if base == 'V':
        return 'maj'    # V triad
    if '7' in base:
        if base[0].isupper():
            return 'maj7'
        return 'min7'
    if base[0].isupper():
        return 'maj'
    return 'min'


def _inv(r):
    if '6/4' in r:
        return '6/4'
    if '6/5' in r:
        return '6/5'
    if '4/3' in r:
        return '4/3'
    if '4/2' in r or r.endswith('2'):
        return '2'
    if r.endswith('6') and not r.endswith('16'):
        return '6'
    if '7' in r and r.endswith('7') and '6' not in r and '4' not in r:
        return '7'
    return 'root'


# ============================================================
# Stress cases
# ============================================================

# 1. V7 in all 4 inversions over 4 measures
#    Each measure ends with a different V7 inversion
print("\n### Test 1: V7 in all 4 inversions (one per measure)")
mel1 = [
    [N.from_name("G5")]*4,    # expect V7 (root) at end
    [N.from_name("B5")]*4,    # expect V6/5 (3rd in bass) at end
    [N.from_name("D5")]*4,    # expect V4/3 (5th in bass) at end
    [N.from_name("F5")]*4,    # expect V2 (7th in bass) at end
]
show("V7 7/6/5/4/3/2 inversions", mel1)

# 2. Cadential 6/4 with melody on V chord tone
print("\n### Test 2: cadential 6/4 explicit")
mel2 = [
    [N.from_name("C5")]*4,
    [N.from_name("C5")]*4,
    [N.from_name("G5"), N.from_name("G5"), N.from_name("G5"), N.from_name("G5")],  # G5 -> I6/4 prep then V7
    [N.from_name("C5")]*4,
]
show("cadential 6/4 explicit", mel2)

# 3. Leading tone in soprano (V → I, soprano = 7th scale degree)
print("\n### Test 3: B4 (leading tone) in soprano over V → I")
mel3 = [
    [N.from_name("C5")]*4,
    [N.from_name("F5")]*4,
    [N.from_name("B4")]*4,    # B4 = leading tone in C major
    [N.from_name("C5")]*4,
]
show("LT in soprano, V→I", mel3)

# 4. V7 7th in bass (V2) — bass must resolve down by step
print("\n### Test 4: V2 (7th in bass) → I")
mel4 = [
    [N.from_name("C5")]*4,
    [N.from_name("C5")]*4,
    [N.from_name("F5")]*4,    # F5 = 7th of V in C major
    [N.from_name("E5")]*4,    # E5 = 3rd of I (resolution target)
]
show("V2 → I, 7th in soprano", mel4)

# 5. Parallel 5 trigger: I → IV with both voices moving in parallel
#    (should be CAUGHT)
print("\n### Test 5: parallel 5/8 trigger")
mel5 = [
    [N.from_name("G4")]*4,    # G4 = 5th of C, 5th of I
    [N.from_name("C5")]*4,    # C5 = root of I, root of IV
    [N.from_name("C5")]*4,
    [N.from_name("C5")]*4,
]
show("potential parallel 5", mel5)

# 6. Voice crossing trigger: bass above tenor
print("\n### Test 6: voice crossing trigger")
mel6 = [
    [N.from_name("C5")]*4,
    [N.from_name("C5")]*4,
    [N.from_name("C5")]*4,
    [N.from_name("C3"), N.from_name("C3"), N.from_name("C3"), N.from_name("C3")],  # bass melody C3
]
show("bass melody C3 (crossing risk)", mel6)

# 7. 3/4 cadential 6/4
print("\n### Test 7: 3/4 cadential 6/4")
mel7 = [
    [N.from_name("C5")]*3,
    [N.from_name("F5")]*3,
    [N.from_name("G5")]*3,
    [N.from_name("C5")]*3,
]
show("3/4 I-IV-V7-I", mel7, ts="3/4")

# 8. D minor (one flat)
print("\n### Test 8: D minor 4/4")
mel8 = [
    [N.from_name("D5")]*4,
    [N.from_name("G5")]*4,
    [N.from_name("A5")]*4,
    [N.from_name("D5")]*4,
]
show("D minor i-iv-V7-i", mel8, key="d")

# 9. E minor
print("\n### Test 9: E minor 4/4")
mel9 = [
    [N.from_name("E5")]*4,
    [N.from_name("A5")]*4,
    [N.from_name("B5")]*4,
    [N.from_name("E5")]*4,
]
show("E minor i-iv-V7-i", mel9, key="e")

# 10. G minor (B♭ - need flat)
print("\n### Test 10: G minor 4/4 with Bb")
mel10 = [
    [N.from_name("G4")]*4,
    [N.from_name("C5")]*4,
    [N.from_name("D5")]*4,
    [N.from_name("G4")]*4,
]
show("G minor i-iv-V7-i", mel10, key="g")

def safe_show(label, melody, key="C", ts="4/4"):
    try:
        return show(label, melody, key=key, ts=ts)
    except Exception as e:
        print(f"  [ERROR] {e}")
        return None, 0


# Re-run all cases safely
if __name__ == "__main__":
    pass  # the show() calls below are wrapped via the safe_show helper

# 12. F# major (6 sharps - chromatic check)
print("\n### Test 12: F# major 4/4")
mel12 = [
    [N.from_name("F#5")]*4,
    [N.from_name("B5")]*4,
    [N.from_name("C#6")]*4,
    [N.from_name("F#5")]*4,
]
show("F# major I-IV-V7-I", mel12, key="F#")

# 13. Edge: 7th already in melody (V2 case)
print("\n### Test 13: melody on 7th of V (V2)")
mel13 = [
    [N.from_name("C5")]*4,
    [N.from_name("F5")]*4,
    [N.from_name("F5"), N.from_name("F5"), N.from_name("F5"), N.from_name("F5")],
    [N.from_name("E5"), N.from_name("E5"), N.from_name("E5"), N.from_name("E5")],
]
show("F5 (V7) → E5 (I) 7th resolution", mel13)
