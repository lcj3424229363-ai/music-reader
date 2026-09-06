# -*- coding: utf-8 -*-
"""
P7.5.1 — Key context per measure (骨架测试)

验证:
  1. 不传 key_changes → 行为跟 P0-P7 完全一致 (向后兼容)
  2. 传 key_changes → 后续 measure 用新 key, 池子/voicing/cadence 都跟新 key 走
  3. summary.keyPerMeasure 字段正确反映每小节 local key
  4. 转调边界的 cadence 用新调 key 检测
"""
import sys, io
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from solver import (
    solve_melody, Note, Key, KeyChange,
)


def N(name: str) -> Note:
    return Note.from_name(name)


# ---------------------------------------------------------------------------
# (T1) 默认行为向后兼容: 不传 key_changes, 等同 P0-P7
# ---------------------------------------------------------------------------
def test_no_key_changes() -> bool:
    """4 小节 C 大调 I-IV-V-I, 不传 key_changes → 应该走 C major 整段."""
    print('\n--- (T1) 不传 key_changes (向后兼容) ---')
    melody = [
        # m1: C5 D5 E5 C5  → 期望 I 收束
        [N("C5"), N("D5"), N("E5"), N("C5")],
        # m2: F5 F5 F5 F5
        [N("F5"), N("F5"), N("F5"), N("F5")],
        # m3: G5 G5 G5 G5  → 期望 V
        [N("G5"), N("G5"), N("G5"), N("G5")],
        # m4: C5 C5 C5 C5  → 期望 I (PAC)
        [N("C5"), N("C5"), N("C5"), N("C5")],
    ]
    r = solve_melody("C", "4/4", melody)
    kpm = r.summary["keyPerMeasure"]
    cad = r.summary["cadences"]
    print(f'  keyPerMeasure = {kpm}')
    print(f'  cadences      = {cad}')
    ok_kpm = all(k == "C major" for k in kpm)
    ok_cad = cad[-1] in ("PAC", "lydian")  # 跟现有 P0 测试一致
    print(f'  keyPerMeasure all "C major"?  {ok_kpm}')
    print(f'  final cadence in PAC/lydian?  {ok_cad}  ({cad[-1]})')
    return ok_kpm and ok_cad


# ---------------------------------------------------------------------------
# (T2) C → G (上五度转调) 骨架能跑通
# ---------------------------------------------------------------------------
def test_C_to_G() -> bool:
    """4 小节: m1-m2 C 大调, m3-m4 G 大调 (上五度最常见转调).

    P7.5.1 骨架只测: key_per_measure 切换 + solver 不炸.
    跨边界 voicing 的合理性 (共同和弦 pivot) 留给 P7.5.2.
    """
    print('\n--- (T2) C → G (上五度转调) ---')
    melody = [
        [N("C5"), N("D5"), N("E5"), N("F5")],   # m1 C major: 1 2 3 4
        [N("G4"), N("G4"), N("G4"), N("G4")],   # m2 C major: 5
        [N("A4"), N("A4"), N("A4"), N("A4")],   # m3 G major: 1
        [N("B4"), N("B4"), N("B4"), N("B4")],   # m4 G major: 2
    ]
    r = solve_melody("C", "4/4", melody, key_changes=[(2, "G")])
    kpm = r.summary["keyPerMeasure"]
    cad = r.summary["cadences"]
    print(f'  keyPerMeasure = {kpm}')
    print(f'  cadences      = {cad}')
    ok_kpm = kpm == ["C major", "C major", "G major", "G major"]
    print(f'  keyPerMeasure split C/G?  {ok_kpm}')
    ok_run = r is not None and len(r.measures) == 4  # 不炸 + 输出完整
    return ok_kpm and ok_run


# ---------------------------------------------------------------------------
# (T3) C → a (关系调) 骨架能跑通
# ---------------------------------------------------------------------------
def test_C_to_a() -> bool:
    """4 小节: m1-m2 C 大调, m3-m4 a 小调 (关系调转调).
    注意: Key.tonic_name 返回大写, 所以 "A minor" (不是 "a minor").
    """
    print('\n--- (T3) C → a (关系调转调) ---')
    melody = [
        [N("C5"), N("D5"), N("E5"), N("F5")],   # m1 C major: 1 2 3 4
        [N("G4"), N("G4"), N("G4"), N("G4")],   # m2 C major: 5
        [N("A4"), N("A4"), N("A4"), N("A4")],   # m3 a minor: 1
        [N("B4"), N("B4"), N("B4"), N("B4")],   # m4 a minor: 2
    ]
    r = solve_melody("C", "4/4", melody, key_changes=[KeyChange(2, "a")])
    kpm = r.summary["keyPerMeasure"]
    cad = r.summary["cadences"]
    print(f'  keyPerMeasure = {kpm}')
    print(f'  cadences      = {cad}')
    ok_kpm = kpm == ["C major", "C major", "A minor", "A minor"]
    print(f'  keyPerMeasure split C/A-minor?  {ok_kpm}')
    ok_run = r is not None and len(r.measures) == 4
    return ok_kpm and ok_run


# ---------------------------------------------------------------------------
# (T4) C → F (下五度转调)
# ---------------------------------------------------------------------------
def test_C_to_F() -> bool:
    """4 小节: m1-m2 C 大调, m3-m4 F 大调 (下五度转调)."""
    print('\n--- (T4) C → F (下五度转调) ---')
    melody = [
        [N("C5"), N("D5"), N("E5"), N("F5")],
        [N("G4"), N("G4"), N("G4"), N("G4")],
        [N("F4"), N("F4"), N("F4"), N("F4")],   # F major: 1
        [N("G4"), N("G4"), N("G4"), N("G4")],   # F major: 2
    ]
    r = solve_melody("C", "4/4", melody, key_changes=[(2, "F")])
    kpm = r.summary["keyPerMeasure"]
    print(f'  keyPerMeasure = {kpm}')
    ok_kpm = kpm == ["C major", "C major", "F major", "F major"]
    print(f'  keyPerMeasure split C/F?  {ok_kpm}')
    ok_run = r is not None and len(r.measures) == 4
    return ok_kpm and ok_run


# ---------------------------------------------------------------------------
# (T5) KeyChange 构造错误检查
# ---------------------------------------------------------------------------
def test_keychange_validation() -> bool:
    print('\n--- (T5) KeyChange 校验 ---')
    results = []
    try:
        KeyChange(-1, "G")
        print('  [FAIL] KeyChange(-1, ...) should have raised')
        results.append(False)
    except ValueError as e:
        print(f'  [OK]   KeyChange(-1) rejected: {e}')
        results.append(True)
    try:
        KeyChange(2, "")
        print('  [FAIL] KeyChange(2, "") should have raised')
        results.append(False)
    except ValueError as e:
        print(f'  [OK]   KeyChange(2, "") rejected: {e}')
        results.append(True)
    try:
        KeyChange(0, "G")  # should work
        print('  [OK]   KeyChange(0, "G") accepted')
        results.append(True)
    except Exception as e:
        print(f'  [FAIL] KeyChange(0, "G") unexpectedly raised: {e}')
        results.append(False)
    return all(results)


if __name__ == "__main__":
    results = {
        "T1": test_no_key_changes(),
        "T2": test_C_to_G(),
        "T3": test_C_to_a(),
        "T4": test_C_to_F(),
        "T5": test_keychange_validation(),
    }
    print('\n######################################################################')
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for k, v in results.items():
        print(f'  {k}: {"PASS" if v else "FAIL"}')
    print(f'# 总结: {passed} / {total} 通过')
    print('######################################################################')
    sys.exit(0 if passed == total else 1)
