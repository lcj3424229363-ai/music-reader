"""终止式检测（斯波索宾《和声学教程》下册关键章节）。

分类：
  PAC - 正格完全终止  V(7)→I，原位，强拍
  IAC - 正格不完全终止 V(7)→I，但转位或弱拍
  Plagal - 变格终止   IV→I，原位
  HC - 半终止         任意→V（原位）
  Deceptive - 阻碍终止 V(7)→VI

音乐分析中常见的位置：每个乐句（phrase）末尾，或作品终止处。
"""
from __future__ import annotations

from typing import Any, Optional


def _is_on_strong_beat(beat: float, time_signature: tuple[int, int] = (4, 4)) -> bool:
    """判断拍位是否为强拍。

    4/4 拍：第 1 拍强拍，第 3 拍次强拍。
    3/4 拍：仅第 1 拍强拍。
    6/8 拍：第 1 拍（复合拍子的强拍）。
    """
    if not beat or beat <= 0:
        return False
    num, den = time_signature
    # 把 beat 映射到小节内位置
    pos_in_measure = (beat - 1) % num
    if num == 4:
        return pos_in_measure in (0, 2)
    if num == 3:
        return pos_in_measure == 0
    if num == 2:
        return pos_in_measure == 0
    if num in (6, 9, 12):
        return pos_in_measure == 0
    return pos_in_measure == 0


def _is_root_position(roman_numeral) -> bool:
    """罗马数字是否原位: figure 不以 6/4/65/43/42 结尾。

    music21 的 .inversion() 是方法返回整数, 不便用; 改用 figure 字符串。
    """
    if roman_numeral is None:
        return False
    fig = (getattr(roman_numeral, "figure", "") or "").strip()
    if not fig:
        return False
    # 副属不影响
    main = fig.split("/")[0] if "/" in fig else fig
    while main and main[0] in "#b":
        main = main[1:]
    import re as _re
    m = _re.search(r"(\d+)$", main)
    if not m:
        return True  # 无末尾数字 -> 根位
    suffix = m.group(1)
    return suffix not in ("6", "64", "65", "43", "42")


def _is_dominant_function(roman_numeral) -> bool:
    from .functions import is_dominant
    return bool(is_dominant(roman_numeral))


def _is_tonic_function(roman_numeral) -> bool:
    from .functions import is_tonic
    return bool(is_tonic(roman_numeral))


def _is_subdominant_function(roman_numeral) -> bool:
    from .functions import is_subdominant
    return bool(is_subdominant(roman_numeral))


def _is_v_or_v7(roman_numeral) -> bool:
    """判断当前罗马数字是不是 V 或 V7（含 vii°、vii°7）"""
    if not roman_numeral:
        return False
    if getattr(roman_numeral, "secondary", False):
        # 副属不算 V
        return False
    degree = getattr(roman_numeral, "scaleDegree", None)
    quality = getattr(roman_numeral, "quality", "")
    if degree in (5, 7) and quality in ("major", "minor", "diminished", "half-diminished", "augmented"):
        # 5 = V, 7 = vii°
        # 5 大 = V (大调)
        # 5 小 = V (和声小调)
        # 7 减 = vii°
        # 7 半减 = viiø
        return True
    return False


def _is_i_or_i64(roman_numeral) -> bool:
    """判断当前罗马数字是不是 I (i) 或 I64（终止四六）"""
    if not roman_numeral:
        return False
    if getattr(roman_numeral, "secondary", False):
        return False
    degree = getattr(roman_numeral, "scaleDegree", None)
    figure = getattr(roman_numeral, "figure", "") or ""
    return degree == 1 and (figure in ("I", "i") or figure.startswith(("I6", "i6")))


def _is_iv_or_iv6(roman_numeral) -> bool:
    if not roman_numeral:
        return False
    if getattr(roman_numeral, "secondary", False):
        return False
    degree = getattr(roman_numeral, "scaleDegree", None)
    return degree == 4


def _is_vi_or_VI(roman_numeral) -> bool:
    if not roman_numeral:
        return False
    if getattr(roman_numeral, "secondary", False):
        return False
    degree = getattr(roman_numeral, "scaleDegree", None)
    return degree == 6


def detect_cadences(roman_sequence: list[dict]) -> list[dict]:
    """对连续的罗马数字序列检测终止式。

    roman_sequence: [{"roman": RomanNumeral, "beat": 1.0, "measure": 1}, ...]
    返回: [{"type": "PAC"|"IAC"|"Plagal"|"HC"|"Deceptive", "measure": ..., "beat": ..., "from": ..., "to": ...}]
    """
    cadences = []
    for i in range(len(roman_sequence) - 1):
        prev = roman_sequence[i]
        curr = roman_sequence[i + 1]
        prev_rn = prev.get("roman")
        curr_rn = curr.get("roman")
        if not prev_rn or not curr_rn:
            continue
        cadence = _classify_pair(prev_rn, curr_rn, prev.get("beat", 1.0), curr.get("beat", 1.0))
        if cadence:
            cadences.append({
                **cadence,
                "measure": curr.get("measure"),
                "beat": curr.get("beat"),
            })
    return cadences


def _classify_pair(prev_rn, curr_rn, prev_beat, curr_beat) -> Optional[dict]:
    """判断一对相邻和弦是否是终止式。

    优先匹配规则（按斯波索宾权重）：
    1. V → I (原位) → PAC
    2. V → I (非原位) → IAC
    3. V → VI → Deceptive
    4. IV → I → Plagal
    5. X → V (原位) → HC
    """
    # Deceptive 优先于 IAC（如果 V→VI，不管 V 的转位）
    if _is_v_or_v7(prev_rn) and _is_vi_or_VI(curr_rn):
        return {
            "type": "Deceptive",
            "label": "阻碍终止",
            "from": _rroman(prev_rn),
            "to": _rroman(curr_rn),
            "fromFunction": "D",
            "toFunction": "T",
            "quality": "deceptive",
        }

    # 真正的 V → I 终止式
    if _is_v_or_v7(prev_rn) and _is_i_or_i64(curr_rn):
        if _is_root_position(prev_rn) and _is_root_position(curr_rn) and _is_on_strong_beat(curr_beat):
            return {
                "type": "PAC",
                "label": "正格完全终止",
                "from": _rroman(prev_rn),
                "to": _rroman(curr_rn),
                "fromFunction": "D",
                "toFunction": "T",
                "quality": "perfect",
            }
        return {
            "type": "IAC",
            "label": "正格不完全终止",
            "from": _rroman(prev_rn),
            "to": _rroman(curr_rn),
            "fromFunction": "D",
            "toFunction": "T",
            "quality": "imperfect",
            "reason": _iac_reason(prev_rn, curr_rn, curr_beat),
        }

    # 变格终止
    if _is_iv_or_iv6(prev_rn) and _is_i_or_i64(curr_rn):
        if _is_root_position(prev_rn) and _is_root_position(curr_rn) and _is_on_strong_beat(curr_beat):
            return {
                "type": "Plagal",
                "label": "变格终止",
                "from": _rroman(prev_rn),
                "to": _rroman(curr_rn),
                "fromFunction": "S",
                "toFunction": "T",
                "quality": "perfect",
            }
        return {
            "type": "Plagal",
            "label": "变格终止（不完全）",
            "from": _rroman(prev_rn),
            "to": _rroman(curr_rn),
            "fromFunction": "S",
            "toFunction": "T",
            "quality": "imperfect",
        }

    # 半终止：任意 → V 原位
    if _is_v_or_v7(curr_rn) and _is_root_position(curr_rn) and _is_on_strong_beat(curr_beat):
        return {
            "type": "HC",
            "label": "半终止",
            "from": _rroman(prev_rn),
            "to": _rroman(curr_rn),
            "fromFunction": _safe_function(prev_rn),
            "toFunction": "D",
            "quality": "half",
        }

    return None


def _rroman(roman_numeral) -> str:
    return getattr(roman_numeral, "figure", "?") or "?"


def _safe_function(roman_numeral) -> Optional[str]:
    from .functions import function_from_roman
    return function_from_roman(roman_numeral)


def _iac_reason(prev_rn, curr_rn, beat) -> str:
    reasons = []
    if not _is_root_position(prev_rn):
        reasons.append(f"属和弦 { _rroman(prev_rn)} 是转位")
    if not _is_root_position(curr_rn):
        reasons.append(f"主和弦 { _rroman(curr_rn)} 是转位")
    if not _is_on_strong_beat(beat):
        reasons.append(f"主和弦落在弱拍 ({beat})")
    if not reasons:
        reasons.append("V 或 I 不完全满足正格条件")
    return "、".join(reasons)
