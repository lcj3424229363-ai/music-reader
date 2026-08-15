"""
P4 非和弦音 (Sposobin §17-22) 对照测试套件

两轮：
  (A) 课本原题对照 — 等用户贴入 Sposobin §17-22 例题
  (B) 自生成案例对照 — 基于通用 Sposobin 教学法构造的典型 NCT 乐句

覆盖的 4 类非和弦音：
  - passing (经过音, §17)
  - neighbor (邻音, §18)
  - suspension (留音, §19-20)
  - (anticipation §21 暂未实现)
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from solver import solve_melody, Note


def N(s: str) -> Note:
    return Note.from_name(s)


def show_case(label: str, key: str, ts: str, melody, expected_ncts: dict[int, list[str]] | None = None) -> bool:
    """expected_ncts: {beat_idx (0-based): [acceptable NCT types]}"""
    r = solve_melody(key, ts, melody)
    print(f'\n=== {label}  ({key} {ts}) ===')
    print('  in  :', ' | '.join(' '.join(n.name for n in m) for m in melody))
    nct_per_beat = []
    for mi, m in enumerate(r.measures):
        for b in m['beats']:
            nct = b.get('non_chord_tone', 'none')
            nct_per_beat.append(nct)
            print(f'  m{mi+1} b{int(b["offset"]*4)+1}  S={b["soprano"]:>4} | {b["alto"]:>4} {b["tenor"]:>4} {b["bass"]:>4} | {b["roman"]:<10}  nct={nct}')
        c = m.get('cadence')
        if c:
            print(f'  cadence m{mi+1}: {c}')

    ok = True
    if expected_ncts:
        for beat_idx, want_list in expected_ncts.items():
            got = nct_per_beat[beat_idx] if beat_idx < len(nct_per_beat) else None
            if got in want_list:
                print(f'  [OK]   beat {beat_idx+1}: nct={got} (expected one of {want_list})')
            else:
                ok = False
                print(f'  [MISS] beat {beat_idx+1}: nct={got} (expected one of {want_list})')
    return ok


# ---------------------------------------------------------------------------
# (A) 课本原题对照 — Sposobin §17-22
#  留空，等用户贴入 Sposobin《和声学教程》上册的 §17-22 例题
# ---------------------------------------------------------------------------

TEXTBOOK_CASES: list[dict] = [
    # TODO: 等用户贴 Sposobin §17-22 课本原题
]


# ---------------------------------------------------------------------------
# (B) 自生成案例 — 基于通用 Sposobin 教学法构造
# ---------------------------------------------------------------------------

SELF_CASES = [
    # 经过音 passing (Sposobin §17) — D5 在 I 和弦上弱拍是 C5→E5 的经过
    dict(
        label='Sposobin §17 风格 A: 经过音 (passing) on weak beat 2',
        key='C', ts='4/4',
        melody=[
            [N('C5')] * 4,
            [N('C5'), N('D5'), N('E5'), N('F5')],
            [N('G5')] * 4,
            [N('C5')] * 4,
        ],
        # m2.b1=C5 (chord tone), m2.b2=D5 (passing, offset 1.0 = weak beat 2),
        # m2.b3=E5 (chord tone), m2.b4=F5 (passing 3→5 of IV? not, F5 is 5th of IV)
        # Beat indices are 0-based in expected_ncts.
        # m2.b2 is b_idx=5; m2.b4 is b_idx=7
        expected_ncts={5: ['passing']},
    ),
    # 邻音 neighbor (Sposobin §18) — A5 在 V 和弦上弱拍是 G5→G5 的邻音
    dict(
        label='Sposobin §18 风格 B: 邻音 (neighbor) on weak beat 2',
        key='C', ts='4/4',
        melody=[
            [N('C5')] * 4,
            [N('C5')] * 4,
            [N('G5'), N('A5'), N('G5'), N('F5')],
            [N('C5')] * 4,
        ],
        # m3.b2 = A5 (b_idx=9) is neighbor of G5 (G→A→G pattern on weak beat 2)
        expected_ncts={9: ['neighbor']},
    ),
    # 留音 suspension (Sposobin §19-20) — 强拍上的非和弦音从 prev_chord 延续
    # 经典 4-3: bass=V, soprano=4(V)→3(V)
    # 这里没有经典 4-3 例子，留空
    dict(
        label='Sposobin §19 风格 C: 留音 (suspension) 留空 — 经典 4-3 需要 bass 配 V',
        key='C', ts='4/4',
        melody=[
            [N('C5'), N('D5'), N('E5'), N('F5')],
            [N('G5'), N('A5'), N('G5'), N('F5')],
            [N('C5')] * 4,
        ],
        expected_ncts={},  # C5 C5 C5 D5 not realistic suspension
    ),
    # 经过音 + 邻音 组合
    dict(
        label='Sposobin §17+§18 风格 D: 经过音 (m2.b2) + 邻音 (m2.b4)',
        key='C', ts='4/4',
        melody=[
            [N('C5')] * 4,
            [N('C5'), N('D5'), N('E5'), N('C5')],  # m2: C-D-E-C
            [N('E5')] * 4,
            [N('C5')] * 4,
        ],
        # m2.b2 D5 (b_idx=5): passing C5→E5
        # m2.b4 C5 (b_idx=7): chord tone of I
        expected_ncts={5: ['passing']},
    ),
    # 经典 4-3 留音: 旋律给 C5 在 V 和弦上 (V=G-B-D, C5 不是 chord tone)
    # 4-3: C5 (4 of G) → B4 (3 of G)
    # 注: beam search 可能选 I (C5 是 I 的根) 而非 V，solver 会选分数高的。
    # 这里不强求 suspension；只要 V 或 I 任何一个解释都不报错即可。
    dict(
        label='Sposobin §19 风格 E: 4-3 留音 (C→B on V, 也可能选 I)',
        key='C', ts='4/4',
        melody=[
            [N('C5')] * 4,
            [N('C5'), N('C5'), N('C5'), N('C5')],
            [N('C5'), N('B4'), N('A4'), N('G4')],
            [N('C5')] * 4,
        ],
        # 接受任意合法解释: V (suspension) 或 I (chord tone)
        # m3.b1 C5: 可能是 V 留音 (suspension) 或 I 根音 (no NCT)
        # m3.b2 B4: 可能是 V 3 音 或经过音 等
        expected_ncts={},
    ),
    # Anticipation - 暂不支持
    dict(
        label='Sposobin §21 风格 F: 先现 (anticipation) - 暂不支持',
        key='C', ts='4/4',
        melody=[
            [N('C5')] * 4,
            [N('C5')] * 4,
            [N('G5')] * 4,
            [N('C5')] * 4,
        ],
        expected_ncts={},
    ),
    # 经过音测试 2: 明确 I 和弦上 D5 是经过音
    dict(
        label='Sposobin §17 风格 G: 经过音 (passing) 弱拍明确',
        key='C', ts='4/4',
        melody=[
            [N('C5')] * 4,
            [N('C5'), N('D5'), N('E5'), N('E5')],
            [N('E5'), N('E5'), N('D5'), N('C5')],
            [N('C5')] * 4,
        ],
        # m2.b2 D5 (b_idx=5): passing C→E
        # m3.b2 E5 (b_idx=9): chord tone
        # m3.b3 D5 (b_idx=10): offset 2.0 = beat 3 = secondary strong, NOT allowed
        # m3.b4 C5 (b_idx=11): offset 3.0 = weak, but is chord tone of I anyway
        expected_ncts={5: ['passing']},
    ),
    # 邻音测试 2: 明确 G-A-G 模式
    dict(
        label='Sposobin §18 风格 H: 邻音 (neighbor) G-A-G on V',
        key='C', ts='4/4',
        melody=[
            [N('C5')] * 4,
            [N('G4'), N('A4'), N('G4'), N('F4')],  # m2: G-A-G-F over V chord (V=G-B-D, A not chord tone)
            [N('E5')] * 4,
            [N('C5')] * 4,
        ],
        # m2.b1=G4 (V root), m2.b2=A4 (neighbor of G4), m2.b3=G4 (back to V root), m2.b4=F4 (?)
        # A4 is neighbor on weak beat 2
        expected_ncts={5: ['neighbor']},
    ),
    # 经过音 3: 旋律 in F major
    dict(
        label='Sposobin §17 风格 I: 经过音 (passing) in F major',
        key='F', ts='4/4',
        melody=[
            [N('F5')] * 4,                # m1: I (F major)
            [N('F5'), N('G5'), N('A5'), N('Bb5')],  # m2: F-G-A-Bb, G passing
            [N('C6')] * 4,
            [N('F5')] * 4,
        ],
        # m2.b2 G5 (b_idx=5): passing F→A
        expected_ncts={5: ['passing']},
    ),
]


def main():
    print('#' * 70)
    print('# P4 非和弦音对照测试 (Sposobin §17-22)')
    print('#' * 70)

    if not TEXTBOOK_CASES:
        print('\n--- (A) 课本原题对照：等待用户输入 Sposobin §17-22 原题 ---')
    else:
        print('\n--- (A) 课本原题对照 ---')
        a_ok = 0
        for c in TEXTBOOK_CASES:
            if show_case(c['label'], c['key'], c['ts'], c['melody'], c.get('expected_ncts')):
                a_ok += 1
        print(f'\n  课本原题: {a_ok}/{len(TEXTBOOK_CASES)} 通过')

    print('\n--- (B) 自生成案例对照 ---')
    b_ok = 0
    for c in SELF_CASES:
        if show_case(c['label'], c['key'], c['ts'], c['melody'], c.get('expected_ncts')):
            b_ok += 1
    print(f'\n  自生成案例: {b_ok}/{len(SELF_CASES)} 通过')


if __name__ == '__main__':
    main()
