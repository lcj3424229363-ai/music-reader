"""
P6 polish — 剩余终止式 (Sposobin §46, §58) 对照测试

两轮：
  (A) 课本原题对照 — 等用户贴入
  (B) 自生成案例对照 — 直接测 detect_cadence 函数 (更可靠)

覆盖：
  - Deceptive cadence (V → vi in major; V → VI in minor) Sposobin §46
  - Lydian cadence (II → I in major) Sposobin §58
"""
import sys, io
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from solver import (solve_melody, detect_cadence, Key, Chord, Voicing, Note)


def N(s: str) -> Note:
    return Note.from_name(s)


def test_detect_cadence(label: str, key_name: str,
                        prev: Chord, last: Chord, last_soprano: str,
                        expected: str | None) -> bool:
    """Direct unit test for detect_cadence."""
    key = Key.from_name(key_name)
    last_v = Voicing(soprano=Note.from_name(last_soprano),
                     alto=Note.from_name("C4"),
                     tenor=Note.from_name("E3"),
                     bass=Note.from_name("C3"))
    got = detect_cadence(prev, last, last_v, key)
    ok = (got == expected)
    flag = '[OK]  ' if ok else '[MISS]'
    print(f'  {flag} {label:<60} → {got!r:<15} (expected {expected!r})')
    return ok


# Script helper, not a parametrized pytest test case.
test_detect_cadence.__test__ = False


TEXTBOOK_CASES: list[dict] = [
    # TODO: 等用户贴 Sposobin §46 (deceptive) / §58 (Lydian) 课本原题
]


def main():
    print('#' * 70)
    print('# P6 polish 终止式 (直接测 detect_cadence 函数)')
    print('#' * 70)

    if not TEXTBOOK_CASES:
        print('\n--- (A) 课本原题对照：等待用户输入 ---')
    else:
        print('\n--- (A) 课本原题对照 ---')
        a_ok = 0
        for c in TEXTBOOK_CASES:
            if test_detect_cadence(c['label'], c['key'],
                                   c['prev'], c['last'], c['last_soprano'],
                                   c['expected']):
                a_ok += 1
        print(f'\n  课本原题: {a_ok}/{len(TEXTBOOK_CASES)} 通过')

    print('\n--- (B) 自生成案例对照 (直接测 detect_cadence) ---')
    cases = [
        # Deceptive in major: V (G major) → vi (Am)
        dict(label='P6 B-1: Deceptive C major V → vi',
             key='C',
             prev=Chord(degree=5, quality='maj', inversion='root', kind='triad'),
             last=Chord(degree=6, quality='min', inversion='root', kind='triad'),
             last_soprano='C5',  # tonic of C
             expected='deceptive'),
        # Deceptive in minor: V (E major) → VI (F major)
        dict(label='P6 B-2: Deceptive A minor V → VI',
             key='a harmonic',
             prev=Chord(degree=5, quality='maj', inversion='root', kind='triad'),
             last=Chord(degree=6, quality='maj', inversion='root', kind='triad'),
             last_soprano='A4',  # tonic of A
             expected='deceptive'),
        # Lydian: II (D major) → I (C major) in C major, soprano on tonic
        dict(label='P6 B-3: Lydian C major II → I (soprano tonic)',
             key='C',
             prev=Chord(degree=2, quality='maj', inversion='root', kind='triad'),
             last=Chord(degree=1, quality='maj', inversion='root', kind='triad'),
             last_soprano='C5',
             expected='lydian'),
        # Lydian with soprano not on tonic → falls through
        dict(label='P6 B-4: Lydian C major II → I (soprano NOT tonic)',
             key='C',
             prev=Chord(degree=2, quality='maj', inversion='root', kind='triad'),
             last=Chord(degree=1, quality='maj', inversion='root', kind='triad'),
             last_soprano='E5',
             expected=None),
        # V → I (PAC) — make sure existing still works
        dict(label='P6 B-5: PAC C major V → I (soprano tonic)',
             key='C',
             prev=Chord(degree=5, quality='maj', inversion='root', kind='triad'),
             last=Chord(degree=1, quality='maj', inversion='root', kind='triad'),
             last_soprano='C5',
             expected='PAC'),
        # IV → I (plagal) — make sure existing still works
        dict(label='P6 B-6: Plagal C major IV → I (soprano tonic)',
             key='C',
             prev=Chord(degree=4, quality='maj', inversion='root', kind='triad'),
             last=Chord(degree=1, quality='maj', inversion='root', kind='triad'),
             last_soprano='C5',
             expected='plagal'),
        # Half cadence — V at end
        dict(label='P6 B-7: HC C major → V (soprano any)',
             key='C',
             prev=Chord(degree=1, quality='maj', inversion='root', kind='triad'),
             last=Chord(degree=5, quality='maj', inversion='root', kind='triad'),
             last_soprano='G4',
             expected='HC'),
    ]
    b_ok = 0
    for c in cases:
        if test_detect_cadence(c['label'], c['key'], c['prev'], c['last'],
                               c['last_soprano'], c['expected']):
            b_ok += 1
    print(f'\n  自生成案例: {b_ok}/{len(cases)} 通过')


if __name__ == '__main__':
    main()
