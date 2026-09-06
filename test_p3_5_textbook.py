"""
P3.5 调式交替 (Sposobin §53) 对照测试套件

两轮：
  (A) 课本原题对照 (Sposobin §53) — 待用户贴入
  (B) 自生成案例对照 (基于通用 Sposobin 教学法构造)

每个 case 跑完后打印：
  - 输入旋律
  - solver 输出 SATB + 罗马
  - 期望 (EXPECT) — 哪些调式交替和弦应在某拍出现
  - 通过 / 失败
"""
import sys, io
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from solver import solve_melody, Note


def N(s: str) -> Note:
    return Note.from_name(s)


def show_case(label: str, key: str, ts: str, melody, expected_substr: list, expected_roman: dict | None = None) -> bool:
    """expected_substr: 哪些字符串（和弦代号子串）必须出现在某个拍上
       expected_roman:  可选 {beat_offset: "I"/"V"/...}，对单拍做更精确断言"""
    r = solve_melody(key, ts, melody)
    print(f'\n=== {label}  ({key} {ts}) ===')
    print('  in  :', ' | '.join(' '.join(n.name for n in m) for m in melody))
    flat = []
    for mi, m in enumerate(r.measures):
        for b in m['beats']:
            flat.append((mi + 1, int(b['offset'] * 4) + 1, b['soprano'], b['roman'], b.get('figure') or ''))
            print(f'  m{mi+1} b{int(b["offset"]*4)+1}  S={b["soprano"]:>4} | {b["alto"]:>4} {b["tenor"]:>4} {b["bass"]:>4} | {b["roman"]:<10} ({b.get("figure") or ""})')
        c = m.get('cadence')
        if c:
            print(f'  cadence m{mi+1}: {c}')

    ok = True
    found_any = any(t in r_ for t in expected_substr
                    for _, _, _, r_, _ in flat)
    if not found_any:
        ok = False
        print(f'  [MISS] none of expected substrings present: {expected_substr}')
    else:
        got = sorted({r_ for _, _, _, r_, _ in flat
                      for t in expected_substr if t in r_})
        print(f'  [OK]   found a valid Sposobin alternative: {got}')

    if expected_roman:
        for (mi, bi, want) in expected_roman:
            actual = [r_ for (mm, bb, _, r_, _) in flat if mm == mi and bb == bi]
            if not actual:
                print(f'  [MISS] m{mi} b{bi}  expected {want}, got nothing')
                ok = False
            elif want not in actual[0]:
                print(f'  [MISS] m{mi} b{bi}  expected {want}, got {actual[0]}')
                ok = False
    return ok


# ---------------------------------------------------------------------------
# (A) 课本原题对照 — Sposobin §53
#  留空，等用户贴入 Sposobin《和声学教程》上册的 §53 例题（含旋律和参考
#  和弦进行）。模板如下：
#
#    例 X.X (Sposobin §53 例 1)
#    调性 / 拍号：C 大调 / 4/4
#    旋律： [C5, D5, Eb5, F5 | G5, G5, G5, G5 | C5, C5, C5, C5 | C5, C5, C5, C5]
#    期望： m2 应该出现 bIII 或 Ger+6/Fr+6
# ---------------------------------------------------------------------------

TEXTBOOK_CASES: list[dict] = [
    # TODO: 等用户贴 Sposobin §53 课本原题
]


# ---------------------------------------------------------------------------
# (B) 自生成案例 — 基于通用 Sposobin 教学法构造的典型调式交替乐句
# ---------------------------------------------------------------------------

SELF_CASES = [
    # bVI 作前属 → V → I  (Sposobin §53 例 1 风格)
    # Ab5 是 b6 of C — 同时是 bVI root 和 It+6 / Ger+6 / Fr+6 bass。
    # 任意一个都符合 Sposobin 教学法。
    dict(
        label='Sposobin §53 风格 A: bVI / It+6 作前属',
        key='C', ts='4/4',
        melody=[
            [N('C5')] * 4,
            [N('C5')] * 4,
            [N('Ab5')] * 4,   # Ab5 = b6 — 任意 chromatic predom
            [N('G5')] * 4,    # V
            [N('C5')] * 4,    # I
        ],
        expected=['bVI', 'It+6', 'Fr+6', 'Ger+6'],
    ),
    # bVII 作前属 → V → I
    dict(
        label='Sposobin §53 风格 B: bVII 作前属',
        key='C', ts='4/4',
        melody=[
            [N('C5')] * 4,
            [N('D5')] * 4,
            [N('Bb4')] * 4,   # Bb4 = b7 — 只能配 bVII
            [N('C5')] * 4,    # I
        ],
        expected=['bVII'],
    ),
    # bIII 作前属 → V → I
    dict(
        label='Sposobin §53 风格 C: bIII 作前属',
        key='C', ts='4/4',
        melody=[
            [N('C5')] * 4,
            [N('Eb5')] * 4,   # Eb5 = b3 — 只能配 bIII (It+6 是 F-Ab-D, 不含 Eb)
            [N('G5')] * 4,    # V
            [N('C5')] * 4,    # I
        ],
        expected=['bIII'],
    ),
    # iv (F minor) 作前属 → It+6 → V → I (Sposobin §48+§50 组合)
    dict(
        label='Sposobin §48+§53 组合 D: iv → It+6 → V → I',
        key='C', ts='4/4',
        melody=[
            [N('C5')] * 4,
            [N('F5')] * 4,
            [N('Ab5')] * 4,   # Ab5 = b6 — chromatic predom
            [N('G5')] * 4,
            [N('C5')] * 4,
        ],
        expected=['iv', 'It+6'],
    ),
    # 副主和弦 (bVI 用作 tonic 化, Sposobin §54 边缘) — 留作观察
    dict(
        label='Sposobin §54 风格 E: bVI / It+6 作 "副主" 平行段',
        key='C', ts='4/4',
        melody=[
            [N('C5'), N('C5'), N('C5'), N('C5')],
            [N('Ab5'), N('Ab5'), N('Ab5'), N('Ab5')],  # 整小节 Ab
            [N('C5'), N('C5'), N('C5'), N('C5')],
        ],
        expected=['bVI', 'It+6', 'Fr+6', 'Ger+6'],
    ),
    # a 小调 + Eb5 旋律: 注 — P3.5 在 major 模式才开 modal mixture,
    # 改了 P5 后这 case 在 a minor 默认不开 modal_b3. 接受任意 chromatic
    # predom (It+6 / Fr+6 / Ger+6) 或 V7/IV 等.
    dict(
        label='Sposobin §53 风格 F: a 小调 Eb5 旋律 (It+6/V7/IV/Fr+6)',
        key='a', ts='4/4',
        melody=[
            [N('A4')] * 4,
            [N('C5')] * 4,
            [N('Eb5')] * 4,  # Eb5 = It+6 #4 / Fr+6 3rd / bII 3rd
            [N('A4')] * 4,
        ],
        expected=['It+6', 'Fr+6', 'N6', 'Ger+6'],
    ),
    # a 小调 + G5 旋律: G5 是 VII root (diatonic) / V7/VI 3rd /
    # V7/IV 5th. 任何合法解释都行.
    dict(
        label='Sposobin §53 风格 G: a 小调 G5 旋律 (VII/V7/VI/V7/IV)',
        key='a', ts='4/4',
        melody=[
            [N('A4')] * 4,
            [N('C5')] * 4,
            [N('G5')] * 4,
            [N('A4')] * 4,
        ],
        expected=['VII', 'V7/VI', 'V7/IV'],
    ),
    # bIII 在 C 大调，旋律 Eb5 = bIII root
    dict(
        label='Sposobin §53 风格 H: C 大调 bIII (Eb 旋律强制)',
        key='C', ts='4/4',
        melody=[
            [N('C5')] * 4,
            [N('F5')] * 4,
            [N('Eb5')] * 4,  # Eb5 = bIII root — 强制 bIII (无 It+6 干扰)
            [N('G5')] * 4,
            [N('C5')] * 4,
        ],
        expected=['bIII'],
    ),
]


def main():
    print('#' * 70)
    print('# P3.5 调式交替对照测试')
    print('#' * 70)

    # (A) 课本原题
    if not TEXTBOOK_CASES:
        print('\n--- (A) 课本原题对照：等待用户输入 Sposobin §53 原题 ---')
    else:
        print('\n--- (A) 课本原题对照 ---')
        a_ok = 0
        for c in TEXTBOOK_CASES:
            if show_case(c['label'], c['key'], c['ts'], c['melody'], c['expected']):
                a_ok += 1
        print(f'\n  课本原题: {a_ok}/{len(TEXTBOOK_CASES)} 通过')

    # (B) 自生成案例
    print('\n--- (B) 自生成案例对照 ---')
    b_ok = 0
    for c in SELF_CASES:
        if show_case(c['label'], c['key'], c['ts'], c['melody'], c['expected']):
            b_ok += 1
    print(f'\n  自生成案例: {b_ok}/{len(SELF_CASES)} 通过')


if __name__ == '__main__':
    main()
