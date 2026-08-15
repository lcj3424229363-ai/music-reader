"""副属和弦、临时主和弦、调式交替检测（斯波索宾《和声学教程》下册）。

核心概念：
  Secondary Dominant  副属  D/x = V/x，V 的属，解决到 x
  Tonicization       临时主  x 被当作临时主调（带自己的临时属）
  Modal Mixture      调式交替 从平行调/同主音调借用的和弦

music21 限制：默认 `roman.romanNumeralFromChord` 不会自动把含升音的 II/IV 标为副属，
所以本模块自实现主动检测（扫描可能的临时主调）。
"""
from __future__ import annotations

import re
from typing import Any, Optional

from music21 import chord, key, pitch, roman


# 借用的特征：罗马数字前有 b 前缀（不是 bb）
BORROWED_PREFIX_PATTERN = re.compile(r"^b([IV]+|[iv]+)$")


# 副属 / 副下属 等临时主，临时主必须是主调的关系调
# 关系大小调: 同主音大小调、平行大小调、上五下四
_PIVOT_TARGETS_SEMITONES = [
    -3,  # 降 III（大调 → 下中音 = 副属可去的临时主,小调）
    -2,  # 降 II（拿波里）
    +2,  # 上二度 (V/II)
    +3,  # 上三度 (V/III)
    +5,  # 上五度 (V/V) 最常见
    +7,  # 上七度 (V/VI 升五度也常见)
    -5,  # 下五度 (V/IV)
    -7,  # 下七度 (V/bVII)
]


def _is_v_quality_in_key(chord_obj: chord.Chord, k: key.Key) -> tuple[bool, str]:
    """判断 chord 在 key k 里是不是 V / V7 / vii° / vii°7。

    返回 (is_v, figure_str)
    """
    try:
        rn = roman.romanNumeralFromChord(chord_obj, k)
    except Exception:
        return False, ""
    fig = getattr(rn, "figure", "") or ""
    if not fig:
        return False, ""
    # 主调里的 vii°7 / V7 / V 都算
    if fig in ("V", "V7", "vii", "viio", "viio7", "viiø7", "VII7"):
        return True, fig
    # V 的转位也可以（虽然是 V 的转位，但本质是 V 解决到临时主）
    if fig in ("V6", "V64", "V7", "V65", "V43", "V42"):
        return True, fig
    return False, fig


def _has_altered_tone(chord_obj: chord.Chord, home_key: key.Key) -> bool:
    """和弦里是否含主调自然音体系之外的音。

    C 大调自然音: C D E F G A B (PC 0,2,4,5,7,9,11)
    a 小调自然音: A B C D E F G (PC 9,11,0,2,4,5,7)
    """
    if home_key is None or not chord_obj.pitches:
        return False
    mode = home_key.mode
    tonic_pc = home_key.tonic.pitchClass
    if mode == "minor":
        natural_pcs = set([(tonic_pc + x) % 12 for x in (0, 2, 3, 5, 7, 8, 10)])
    else:
        natural_pcs = set([(tonic_pc + x) % 12 for x in (0, 2, 4, 5, 7, 9, 11)])
    for p in chord_obj.pitches:
        if p.pitchClass not in natural_pcs:
            return True
    return False


def detect_secondary(roman_numeral, original_chord: chord.Chord = None,
                     home_key: key.Key = None) -> Optional[dict]:
    """识别副属和弦（强化版：music21 默认不主动标副属时，自己扫临时主）。

    两种入口:
      1. roman_numeral 已经是 V/x 形式（用 roman.RomanNumeral("V/V", key) 构造）
      2. original_chord + home_key: 自己扫所有可能的临时主
    """
    # 入口 1: 直接看 RomanNumeral 是不是 secondary
    if roman_numeral is not None:
        sec_rn = getattr(roman_numeral, "secondaryRomanNumeral", None)
        figure = getattr(roman_numeral, "figure", "") or ""
        if sec_rn is not None and "/" in figure:
            parts = figure.split("/")
            if len(parts) == 2:
                return {
                    "isSecondary": True,
                    "figure": figure,
                    "dominant": parts[0],
                    "target": parts[1],
                    "targetDegree": getattr(sec_rn, "scaleDegree", None),
                    "detection": "music21-roman",
                }
        # 入口 1b: figure 含 # 或 b 且主调自然音里没有 → 可能是副属
        if home_key is not None and original_chord is not None:
            return _scan_for_secondary(original_chord, home_key, roman_numeral)

    # 入口 2: 没给 RomanNumeral, 主动扫
    if original_chord is not None and home_key is not None:
        return _scan_for_secondary(original_chord, home_key, None)

    return None


def _scan_for_secondary(chord_obj: chord.Chord, home_key: key.Key,
                        fallback_rn) -> Optional[dict]:
    """扫所有可能的临时主调,看 chord 是不是其中一个的 V/V7/vii°7。

    关键过滤: 必须是**变化音和弦**(含主调自然音之外的音) 才算副属,
    否则 C-E-G 这种 I 会被误判为 V/IV。
    """
    if not chord_obj.pitches:
        return None

    if not _has_altered_tone(chord_obj, home_key):
        return None  # 自然音和弦不算副属

    home_tonic_pc = home_key.tonic.pitchClass
    home_mode = home_key.mode  # major / minor

    for delta in _PIVOT_TARGETS_SEMITONES:
        # 临时主 = 当前主音 + delta 半音
        target_tonic_pc = (home_tonic_pc + delta) % 12
        target_tonic_name = pitch.Pitch(target_tonic_pc).name
        try:
            for mode in ("major", "minor"):
                try:
                    target_key = key.Key(target_tonic_name, mode)
                except Exception:
                    continue
                is_v, fig_in_target = _is_v_quality_in_key(chord_obj, target_key)
                if is_v:
                    # 找到了! 临时主 = target_key
                    # 算临时主在主调中的音级 (罗马数字)
                    target_rn = _build_roman_for_target(target_tonic_pc, home_tonic_pc, home_mode, mode)
                    # 反算临时主的 degree
                    target_degree = _target_degree_in_home(target_tonic_pc, home_tonic_pc, home_mode)
                    # 副属的 figure: V/target
                    sec_fig = f"{fig_in_target}/{target_rn}" if target_rn else f"{fig_in_target}/?"
                    return {
                        "isSecondary": True,
                        "figure": sec_fig,
                        "dominant": fig_in_target,
                        "target": target_rn or "?",
                        "targetDegree": target_degree,
                        "targetKey": f"{target_tonic_name} {mode}",
                        "detection": "scanned",
                    }
        except Exception:
            continue

    return None


def _target_degree_in_home(target_pc: int, home_pc: int, home_mode: str) -> Optional[int]:
    """临时主音在主调里的音级 (1-7)。"""
    if home_mode == "minor":
        # 小调按自然小调音阶
        scale = [0, 2, 3, 5, 7, 8, 10]  # 自然小调相对 C 的音程
    else:
        scale = [0, 2, 4, 5, 7, 9, 11]  # 大调
    home_aligned = (target_pc - home_pc) % 12
    for i, s in enumerate(scale):
        if s == home_aligned:
            return i + 1
    return None


def _build_roman_for_target(target_pc: int, home_pc: int, home_mode: str, target_mode: str) -> Optional[str]:
    """把临时主音转回主调中的罗马数字。"""
    deg = _target_degree_in_home(target_pc, home_pc, home_mode)
    if deg is None:
        return None
    base = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII"}[deg]
    # 升降号
    delta = (target_pc - home_pc) % 12
    if home_mode == "minor":
        scale = [0, 2, 3, 5, 7, 8, 10]
    else:
        scale = [0, 2, 4, 5, 7, 9, 11]
    home_aligned = delta
    natural = scale[deg - 1]
    diff = (home_aligned - natural) % 12
    if diff == 1 or diff == 2:
        base = "#" + base
    elif diff == 10 or diff == 11:
        base = "b" + base
    # 大小写
    if target_mode == "minor":
        base = base.lower()
    return base


def detect_borrowed(roman_numeral) -> Optional[dict]:
    """识别借用和弦（modal mixture / 同主音/关系大小调交替）。

    music21 用 b 前缀标记降低音级：♭III → bIII，♭VII → bVII。
    """
    if not roman_numeral:
        return None
    figure = getattr(roman_numeral, "figure", "") or ""
    # 副属里出现 b 不算借用（例 bVI/V 仍属副属内部）
    if "/" in figure:
        return None
    m = BORROWED_PREFIX_PATTERN.match(figure)
    if not m:
        return None
    base = m.group(1)
    return {
        "isBorrowed": True,
        "figure": figure,
        "baseFigure": base,
        "degree": getattr(roman_numeral, "scaleDegree", None),
    }


def enrich_roman(roman_numeral, key) -> dict:
    """为单个罗马数字补充斯波索宾式的解读字段。

    返回 dict 包含 figure, function, role, isSecondary, isBorrowed 等。
    """
    from .functions import function_from_roman, classify_chord_role

    figure = getattr(roman_numeral, "figure", "?") or "?"
    fn = function_from_roman(roman_numeral)
    role_info = classify_chord_role(roman_numeral)
    secondary = detect_secondary(roman_numeral)
    borrowed = detect_borrowed(roman_numeral)
    inversion = getattr(roman_numeral, "inversion", "root") or "root"
    return {
        "figure": figure,
        "function": fn,
        "role": role_info.get("role"),
        "scaleDegree": getattr(roman_numeral, "scaleDegree", None),
        "quality": getattr(roman_numeral, "quality", None),
        "inversion": inversion,
        "isSecondary": bool(secondary),
        "secondaryOf": secondary.get("target") if secondary else None,
        "isBorrowed": bool(borrowed),
        "key": key.tonic.name + (" major" if key.mode == "major" else " minor"),
    }


def find_tonicizations(roman_sequence: list[dict]) -> list[dict]:
    """从罗马数字序列里识别"离调"段落：副属 → 临时主。

    模式: V/x → x，然后回到主调
    """
    events = []
    for i in range(len(roman_sequence) - 1):
        prev = roman_sequence[i]
        curr = roman_sequence[i + 1]
        prev_rn = prev.get("roman")
        curr_rn = curr.get("roman")
        if not prev_rn or not curr_rn:
            continue
        sec = detect_secondary(prev_rn)
        if not sec:
            continue
        # 检查 curr 是不是 sec.target 对应的临时主
        # 例如 V/II → ii（大调）or iio（小调）
        # 这里简化为：curr 是主和弦的临时主（即 curr.scaleDegree = sec.target 的音级）
        # 实际上 V/x 应该解决到 x，x 可能是 ii, IV, vi 等
        target_degree = _degree_from_roman(sec["target"])
        if target_degree and curr_rn.scaleDegree == target_degree:
            events.append({
                "type": "tonicization",
                "measure": curr.get("measure"),
                "beat": curr.get("beat"),
                "dominant": sec["figure"],
                "target": sec["target"],
                "targetRoot": curr_rn.figure,
            })
    return events


def _degree_from_roman(roman_str: str) -> Optional[int]:
    """从罗马数字字符串解析音级 (1-7)。"""
    if not roman_str:
        return None
    s = roman_str.strip()
    # 去掉变音
    while s and s[0] in "#b":
        s = s[1:]
    m = re.match(r"^(VII|VI|V|IV|I|vii|vi|v|iv|i|III|II)$", s)
    if not m:
        return None
    base = m.group(1).upper()
    return {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}.get(base)
