# -*- coding: utf-8 -*-
"""
P7.5 — Sposobin ch31 调性关系类型 (PDF p216-219 / 课本 p208-211) 对照测试

为 P7.5 (ch34/35 转调) 铺路: 调性关系 helper (平行/关系/一级关系调/关系类型).

覆盖:
  - 平行调 (同主音大小调): C major ↔ c minor
  - 关系调 (同中音大小调): C major ↔ a minor
  - 一级关系调 (6 keys): G, F, D, B♭, a, c (上/下五度 + 上/下大二 + 关系 + 平行)
  - relationship_to(): same / parallel / relative / P5_up / P5_down / M2_up / M2_down / distant
  - is_close_related_to(): 一级关系判断

课本 ch31 调性关系类型 三种:
  1. 转调 (modulation) — 完整转调, 在新调结束 (有完满终止)
  2. 离调 (tonicization) — 短时间进入副调, 回主调 (P2 副属)
  3. 对置 (juxtaposition) — 直接切换, 不用过渡

课本 ch35 到一级关系调的转调: 最常见的 5-6 个 close-related keys.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from solver import Key


def N(name: str) -> Key:
    return Key.from_name(name)


def test_parallel() -> list[bool]:
    """平行调: 同主音大小调 (Sposobin ch31 §1.4)."""
    print('\n--- (B1) 平行调 (同主音大小调) ---')
    results = []
    # C major → c minor
    c = N('C')
    par = c.parallel()
    ok = par.tonic_pc == c.tonic_pc and par.mode == 'minor'
    flag = '[OK]  ' if ok else '[MISS]'
    print(f'  {flag} C major 平行 = {par.tonic_pc} {par.mode}  (expect c minor, same tonic)')
    results.append(ok)
    # a minor → A major
    a = N('a')
    par = a.parallel()
    ok = par.tonic_pc == a.tonic_pc and par.mode == 'major'
    flag = '[OK]  ' if ok else '[MISS]'
    print(f'  {flag} a minor 平行 = {par.tonic_pc} {par.mode}  (expect A major, same tonic)')
    results.append(ok)
    # F# major → f# minor
    fs = N('F#')
    par = fs.parallel()
    ok = par.tonic_pc == fs.tonic_pc and par.mode == 'minor'
    flag = '[OK]  ' if ok else '[MISS]'
    print(f'  {flag} F# major 平行 = {par.tonic_pc} {par.mode}  (expect f# minor, same tonic)')
    results.append(ok)
    return results


def test_relative() -> list[bool]:
    """关系调: 同中音大小调 (Sposobin ch31 §1.4)."""
    print('\n--- (B2) 关系调 (同中音大小调) ---')
    results = []
    # C major → a minor (a is 3 semitones below C)
    c = N('C')
    rel = c.relative()
    ok = rel.tonic_pc == 9 and rel.mode == 'minor'
    flag = '[OK]  ' if ok else '[MISS]'
    print(f'  {flag} C major 关系 = pc {rel.tonic_pc} {rel.mode}  (expect a minor = pc 9)')
    results.append(ok)
    # a minor → C major
    a = N('a')
    rel = a.relative()
    ok = rel.tonic_pc == 0 and rel.mode == 'major'
    flag = '[OK]  ' if ok else '[MISS]'
    print(f'  {flag} a minor 关系 = pc {rel.tonic_pc} {rel.mode}  (expect C major = pc 0)')
    results.append(ok)
    # e minor → G major
    e = N('e')
    rel = e.relative()
    ok = rel.tonic_pc == 7 and rel.mode == 'major'
    flag = '[OK]  ' if ok else '[MISS]'
    print(f'  {flag} e minor 关系 = pc {rel.tonic_pc} {rel.mode}  (expect G major = pc 7)')
    results.append(ok)
    return results


def test_close_related_keys() -> list[bool]:
    """一级关系调: Sposobin ch35 (6 keys)."""
    print('\n--- (B3) 一级关系调 (Sposobin ch35) ---')
    results = []
    # C major: 6 close-related keys
    c = N('C')
    cr = c.close_related_keys()
    expected = [
        (7, 'major'),    # G (上五度)
        (5, 'major'),    # F (下五度)
        (2, 'major'),    # D (大二度上)
        (10, 'major'),   # B♭ (大二度下)
        (9, 'minor'),    # a (关系小调)
        (0, 'minor'),    # c (平行小调)
    ]
    got = sorted([(k.tonic_pc, k.mode) for k in cr])
    expected_sorted = sorted(expected)
    ok = got == expected_sorted
    flag = '[OK]  ' if ok else '[MISS]'
    print(f'  {flag} C major close-related keys:')
    for (pc, mode) in got:
        print(f'    - pc {pc} {mode}')
    print(f'    expected: {expected_sorted}')
    results.append(ok)
    # a minor: 6 close-related keys
    a = N('a')
    cr = a.close_related_keys()
    expected = [
        (4, 'minor'),    # e (上五度)
        (2, 'minor'),    # d (下五度)
        (11, 'minor'),   # b (大二度上)
        (7, 'minor'),    # g (大二度下)
        (0, 'major'),    # C (关系大调)
        (9, 'major'),    # A (平行大调)
    ]
    got = sorted([(k.tonic_pc, k.mode) for k in cr])
    expected_sorted = sorted(expected)
    ok = got == expected_sorted
    flag = '[OK]  ' if ok else '[MISS]'
    print(f'  {flag} a minor close-related keys:')
    for (pc, mode) in got:
        print(f'    - pc {pc} {mode}')
    print(f'    expected: {expected_sorted}')
    results.append(ok)
    return results


def test_relationship_to() -> list[bool]:
    """relationship_to: 关系类型 (Sposobin ch31)."""
    print('\n--- (B4) relationship_to: 关系类型 ---')
    results = []
    c = N('C')
    cases = [
        ('C major',   'same'),
        ('a minor',   'relative'),
        ('c minor',   'parallel'),
        ('G major',   'P5_up'),
        ('F major',   'P5_down'),
        ('D major',   'M2_up'),
        ('Bb major',  'M2_down'),
        ('e minor',   'distant'),    # a minor (C major's relative) 的 V
        ('Eb major',  'distant'),    # bVI
        ('Db major',  'distant'),    # 大三度下
    ]
    for name, expected in cases:
        k = N(name)
        got = c.relationship_to(k)
        ok = got == expected
        flag = '[OK]  ' if ok else '[MISS]'
        print(f'  {flag} C major → {name:10s} = {got!r:14s}  (expected {expected!r})')
        results.append(ok)
    return results


def test_is_close_related() -> list[bool]:
    """is_close_related_to: 一级关系判断."""
    print('\n--- (B5) is_close_related_to: 一级关系判断 ---')
    results = []
    c = N('C')
    cases = [
        ('C major',   True),    # same
        ('G major',   True),    # 上五度
        ('F major',   True),    # 下五度
        ('D major',   True),    # 大二度上
        ('Bb major',  True),    # 大二度下
        ('a minor',   True),    # 关系
        ('c minor',   True),    # 平行
        ('e minor',   False),   # 上五度 minor (相对大调的关系小调)
        ('Eb major',  False),   # 大三度下
        ('Db major',  False),   # 大三度下 ♭II
        ('F# major',  False),   # 增四度
    ]
    for name, expected in cases:
        k = N(name)
        got = c.is_close_related_to(k)
        ok = got == expected
        flag = '[OK]  ' if ok else '[MISS]'
        print(f'  {flag} C major → {name:10s} is_close={got!r:6s}  (expected {expected!r})')
        results.append(ok)
    return results


def test_ch31_examples() -> list[bool]:
    """ch31 例 31-467 ~ 31-476 的关系类型识别.
    这是 P7.5 调性布局分析的基础."""
    print('\n--- (B6) ch31 例 31-467 ~ 31-476 关系类型识别 ---')
    results = []
    # 例 31-467: 肖邦玛祖卡 作品 7 之 3  f 小调 → c 小调
    # diff = (0-5) % 12 = 7 = 上五度 (c minor 是 f minor 的 P5_up)
    f = N('f'); c = N('c')
    rel = f.relationship_to(c)
    ok = rel == 'P5_up'
    flag = '[OK]  ' if ok else '[MISS]'
    print(f'  {flag} 例 31-467 肖邦玛祖卡 f→c = {rel!r}  (expected \'P5_up\')')
    results.append(ok)
    # 例 31-468: 韦伯 单簧管奏鸣曲 A 大调 → E 大调 (上五度)
    a = N('A'); e = N('E')
    rel = a.relationship_to(e)
    ok = rel == 'P5_up'
    flag = '[OK]  ' if ok else '[MISS]'
    print(f'  {flag} 例 31-468 韦伯 A→E = {rel!r}  (expected \'P5_up\')')
    results.append(ok)
    # 例 31-470: 舒曼 黄昏的星 A 大调 → F# 小调 (关系 — A 的关系小调是 F# minor)
    # Note: 用小写 'f#' 表示 F# minor
    fis_min = N('f#')
    rel = a.relationship_to(fis_min)
    ok = rel == 'relative'
    flag = '[OK]  ' if ok else '[MISS]'
    print(f'  {flag} 例 31-470 舒曼 A→#f = {rel!r}  (expected \'relative\')')
    results.append(ok)
    # 例 31-471: 贝多芬 53 C 大调 → F 大调 (下五度)
    C = N('C'); F = N('F')
    rel = C.relationship_to(F)
    ok = rel == 'P5_down'
    flag = '[OK]  ' if ok else '[MISS]'
    print(f'  {flag} 例 31-471 贝多芬 C→F = {rel!r}  (expected \'P5_down\')')
    results.append(ok)
    # 例 31-475: 舒伯特 E 大调 → e 小调 (平行)
    E = N('E')
    rel = E.relationship_to(N('e'))
    ok = rel == 'parallel'
    flag = '[OK]  ' if ok else '[MISS]'
    print(f'  {flag} 例 31-475 舒伯特 E→e = {rel!r}  (expected \'parallel\')')
    results.append(ok)
    # 例 31-473: 贝多芬 2 f 小调 → ♭A 大调
    # f minor 关系大调 = ♭A (3 semitones up) — 关系
    # f minor 大二度下 = E♭ (10 semitones up) — 不是 ♭A
    fm = N('f'); Ab = N('Ab')
    rel = fm.relationship_to(Ab)
    ok = rel == 'relative'
    flag = '[OK]  ' if ok else '[MISS]'
    print(f'  {flag} 例 31-473 贝多芬 f→♭A = {rel!r}  (expected \'relative\')')
    results.append(ok)
    return results


def main():
    print('#' * 70)
    print('# P7.5 — Sposobin ch31 调性关系类型 对照测试 (P7.5 铺路)')
    print('#' * 70)
    all_results: list[bool] = []
    for fn in [test_parallel, test_relative, test_close_related_keys,
               test_relationship_to, test_is_close_related,
               test_ch31_examples]:
        all_results.extend(fn())
    passed = sum(1 for r in all_results if r)
    total = len(all_results)
    print('\n' + '#' * 70)
    print(f'# 总结: {passed} / {total} 通过')
    print('#' * 70)
    return passed == total


if __name__ == '__main__':
    ok = main()
    sys.exit(0 if ok else 1)
