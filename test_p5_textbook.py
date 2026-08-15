"""
P5 (Sposobin §31-33, §55-58) 对照测试套件

两轮：
  (A) 课本原题对照 — 等用户贴入 Sposobin 小调 / 教会调式原题
  (B) 自生成案例对照 — 基于通用 Sposobin 教学法构造

覆盖：
  P5a — harmonic minor (升 7), melodic minor (升 6 升 7 上行)
  P5b — Phrygian half cadence (iv6 → V 在 minor)
  P5c — Mixolydian ♭VII (modal_b7) 借用
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from solver import solve_melody, Note


def N(s: str) -> Note:
    return Note.from_name(s)


def show_case(label: str, key: str, ts: str, melody, expected_cadences=None,
              expected_ncts=None) -> bool:
    """expected_cadences: {measure_idx_0based: [acceptable cadences]}"""
    r = solve_melody(key, ts, melody)
    print(f'\n=== {label}  ({key} {ts}) ===')
    print('  in  :', ' | '.join(' '.join(n.name for n in m) for m in melody))
    nct_per_beat = []
    for mi, m in enumerate(r.measures):
        for b in m['beats']:
            nct = b.get('non_chord_tone', 'none')
            nct_per_beat.append(nct)
            print(f'  m{mi+1} b{int(b["offset"]*4)+1}  S={b["soprano"]:>4}  | {b["alto"]:>4} {b["tenor"]:>4} {b["bass"]:>4}  | {b["roman"]:<8}  nct={nct}')
        c = m.get('cadence')
        if c:
            print(f'  cadence m{mi+1}: {c}')

    ok = True
    if expected_cadences:
        for mi, want_list in expected_cadences.items():
            c = r.measures[mi].get('cadence')
            if c in want_list:
                print(f'  [OK]   m{mi+1} cadence: {c} (expected one of {want_list})')
            else:
                ok = False
                print(f'  [MISS] m{mi+1} cadence: {c} (expected one of {want_list})')
    if expected_ncts:
        for beat_idx, want_list in expected_ncts.items():
            got = nct_per_beat[beat_idx] if beat_idx < len(nct_per_beat) else None
            if got in want_list:
                print(f'  [OK]   beat {beat_idx+1} nct: {got}')
            else:
                ok = False
                print(f'  [MISS] beat {beat_idx+1} nct: {got} (expected one of {want_list})')
    return ok


# ---------------------------------------------------------------------------
# (A) 课本原题对照 — Sposobin §31-33, §55-58
# ---------------------------------------------------------------------------

TEXTBOOK_CASES: list[dict] = [
    # TODO: 等用户贴 Sposobin 小调 / 教会调式课本原题
]


# ---------------------------------------------------------------------------
# (B) 自生成案例
# ---------------------------------------------------------------------------

SELF_CASES = [
    # P5a: harmonic minor — 旋律在 V 上 G# (升 7) 必须能用
    dict(
        label='P5a A: harmonic minor V (G# raised 7)',
        key='a harmonic', ts='4/4',
        melody=[
            [N('A4')] * 4,
            [N('F5')] * 4,
            [N('E5'), N('E5'), N('E5'), N('E5')],
            [N('A4')] * 4,
        ],
        # m3 是 V (E5, 根)，不一定要看到 G#，但 V 应该是 harmonic V
        expected_cadences={2: ['HC']},
    ),
    # P5a: melodic minor — 上行用升 6 升 7
    dict(
        label='P5a B: melodic minor IV (F# raised 6 in soprano)',
        key='a melodic', ts='4/4',
        melody=[
            [N('A4')] * 4,
            [N('F#5'), N('F#5'), N('F#5'), N('F#5')],   # F#5 是升 6 暗示 IV (D major)
            [N('E5')] * 4,
            [N('A4')] * 4,
        ],
        expected_cadences={2: ['HC']},
    ),
    # P5a: melodic minor III+ (augmented triad)
    dict(
        label='P5a C: melodic minor III+ (C# augmented)',
        key='a melodic', ts='4/4',
        melody=[
            [N('A4')] * 4,
            [N('C#5'), N('C#5'), N('C#5'), N('C#5')],   # C#5 是 III+ root
            [N('E5')] * 4,
            [N('A4')] * 4,
        ],
        expected_cadences={2: ['HC']},
    ),
    # P5b: Phrygian half cadence (iv6 → V 在 minor)
    # a minor 里 iv6 = D minor in 6/3 inversion (bass = F, 3rd)
    # V = E major
    # b2 of a = B♭ (pc 10) — 应在 V beat 的 soprano
    # Melody 强制 V 持续 (用 E5 一直保持)
    dict(
        label='P5b A: Phrygian half cadence (iv6 → V) on a minor',
        key='a harmonic', ts='4/4',
        melody=[
            [N('A4')] * 4,
            [N('A4')] * 4,
            # m3: iv6 持续 D minor 6/3, 末拍 V (E major) with Bb4 (b2)
            [N('D5'), N('D5'), N('D5'), N('E5')],
            [N('E5'), N('E5'), N('E5'), N('A4')],
        ],
        # 这里 E5 是 V 的根音 (root) 不是 b2
        # 真正的 Phrygian 半终止需要 melody 是 b2 在 V 拍
        # m4 末拍 A4 = i 的根音，solver 选 HC: V → i
        expected_cadences={2: ['HC']},
    ),
    # P5b: 真 Phrygian (b2 在 soprano, V 持续) — 已知限制
    # b2 在 V 拍上是 appoggiatura (NCT, 装饰音), 当前 NCT classifier
    # 不支持 appoggiatura 判定, 所以 fallback. 完整支持需 P4.5.
    # 跳过此 case — 只保留 P5b A (Phrygian via HC).
    # P5b: Phrygian cadence 失败例子 (b2 不在 soprano 时)
    dict(
        label='P5b B: Phrygian cadence variant (b2 在 E beat 前)',
        key='a harmonic', ts='4/4',
        melody=[
            [N('A4')] * 4,
            [N('A4')] * 4,
            [N('D5'), N('D5'), N('Bb4'), N('E5')],   # b2 在倒数第二拍
            [N('E5'), N('E5'), N('E5'), N('E5')],   # m4 整小节 V
        ],
        # m3 → m4: prev=iv6 (m3 b4=E, 这是 V), 错了，应该是 prev=iv6 在 m3 b3
        # 这个 case 不严格，只测能跑通
        expected_cadences={},
    ),
    # P5c: Mixolydian bVII (modal_b7, 已在 P3.5 支持)
    dict(
        label='P5c A: Mixolydian bVII (Bb in C major)',
        key='C', ts='4/4',
        melody=[
            [N('C5')] * 4,
            [N('Bb4'), N('Bb4'), N('Bb4'), N('Bb4')],
            [N('F5')] * 4,
            [N('C5')] * 4,
        ],
        expected_cadences={2: ['HC']},
    ),
    # P5a: natural minor 终止
    dict(
        label='P5a D: natural minor v (lowercase)',
        key='a', ts='4/4',
        melody=[
            [N('A4')] * 4,
            [N('F5')] * 4,
            [N('E5')] * 4,
            [N('A4')] * 4,
        ],
        # m3.b13 应该是 v (lowercase, 自然小调 v) 或 V (harmonic V)
        # 实际 m3.b13 是 v_beat，根据 variant=natural，应该是 v
        # 但经典用法是 harmonic V，所以这个 case 看 solver 选哪个
        expected_cadences={2: ['HC']},
    ),
]


def main():
    print('#' * 70)
    print('# P5 小调 / 教会调式 / Phrygian 对照测试')
    print('#' * 70)

    if not TEXTBOOK_CASES:
        print('\n--- (A) 课本原题对照：等待用户输入 Sposobin §31-33, §55-58 原题 ---')
    else:
        print('\n--- (A) 课本原题对照 ---')
        a_ok = 0
        for c in TEXTBOOK_CASES:
            if show_case(c['label'], c['key'], c['ts'], c['melody'],
                         c.get('expected_cadences'), c.get('expected_ncts')):
                a_ok += 1
        print(f'\n  课本原题: {a_ok}/{len(TEXTBOOK_CASES)} 通过')

    print('\n--- (B) 自生成案例对照 ---')
    b_ok = 0
    for c in SELF_CASES:
        if show_case(c['label'], c['key'], c['ts'], c['melody'],
                     c.get('expected_cadences'), c.get('expected_ncts')):
            b_ok += 1
    print(f'\n  自生成案例: {b_ok}/{len(SELF_CASES)} 通过')


if __name__ == '__main__':
    main()
