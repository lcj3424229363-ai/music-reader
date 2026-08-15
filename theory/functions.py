"""斯波索宾《和声学教程》体系下的功能分组。

核心功能：
  T (Tonic)     主功能    - 稳定，中心和归宿
  S (Subdominant) 下属功能 - 次稳定，倾向到 D
  D (Dominant)   属功能   - 不稳定，必须解决到 T

每个功能下细分：
  primary  原位主和弦（I/i）
  extension 延展（VI/vi, III/iii 在 T 组中）
  substitute 替代（♭III, ♭VI, ♭VII 等借用和弦）
  cadential 终止（K6/4 等）

七和弦 (V7, vii°7) 与副属 (V/x) 都属于 D 组。
"""
from __future__ import annotations

from typing import Optional


# 斯波索宾上册第 8 章「和弦的功能分类」
PRIMARY_FUNCTIONS = {"T", "S", "D"}


# 罗马数字的"基本功能"，以大调自然音体系为基础。
# 转位 (6, 6/4, 7 等) 不改变功能组，仅改变角色。
# 借用和弦（♭III, ♭VI, ♭VII）按其对应的功能组归类。
_BASE_FUNCTION_TABLE = {
    # ===== T 主功能 =====
    "I": "T", "i": "T",
    "III": "T", "iii": "T",        # 延展
    "VI": "T", "vi": "T",          # 延展
    "bIII": "T", "biii": "T",      # 借用（来自关系小调）
    "bVI": "T", "bvi": "T",        # 借用（TsVI，大调中来自小调）
    "bVII": "S", "bvii": "S",      # 借用（来自 Mixolydian），归 S 组
    # V/V/V 之类的副属也归 D 组（无论主调大小调）

    # ===== S 下属功能 =====
    "IV": "S", "iv": "S",
    "II": "S", "ii": "S",
    "bII": "S",                    # 拿波里
    "iiø43": "S",                  # 半减七（ii7 的自然音形式）

    # ===== D 属功能 =====
    "V": "D", "V7": "D",
    "vii": "D", "viiø43": "D",     # 减三 / 半减七，导七和弦
}


def _normalize_figure(figure: str) -> str:
    """去掉转位标记和数字下标，只保留基本罗马数字部分。

    例:
      "V6"     -> "V"
      "V64"    -> "V"
      "V7"     -> "V7"
      "viiø43" -> "viiø43"
      "V/V"    -> "V/V"  (副属是 V 解决到 V，自身仍是 D)
    """
    if not figure:
        return ""
    figure = figure.strip()
    # 不动副属（V/x, V7/x 等）
    if "/" in figure:
        return figure
    # 去掉末尾的数字和可能的 #/b 前缀
    # 但保留像 "V7" 这种尾部的 7
    return figure


def _figure_base(figure: str) -> str:
    """提取罗马数字的基本字符（去掉变音和转位）。

    例:
      "V64"     -> "V"
      "V7"      -> "V7" (保留属七标记)
      "#ivo6"   -> "#ivo"
      "V/V"     -> "V/V"
      "viiø43"  -> "viiø43"
    """
    if not figure:
        return ""
    figure = figure.strip()

    # 副属整体（V/x, V7/x, vii°7/x 等）—— 主属不变，归 D
    if "/" in figure:
        return figure

    # 分离前置变音（#, b, ##, bb）和核心罗马数字
    prefix = ""
    rest = figure
    while rest and rest[0] in "#b":
        prefix += rest[0]
        rest = rest[1:]
    # rest 应该是罗马数字 + 转位数字 + 可选 7
    # 找到罗马数字字符（I V 或 ii vi iii vii 之类）
    import re
    m = re.match(r"^(VII|VI|V|IV|I|vii|vi|v|iv|i|III|II)(\d*)$", rest)
    if not m:
        return figure
    roman_core = m.group(1).upper()
    return prefix + roman_core


def function_from_roman(roman_numeral) -> Optional[str]:
    """从 music21 RomanNumeral 对象导出主功能 (T/S/D)。

    斯波索宾体系：
      T = I, VI, III (大调)，i, VI, III (小调)
      S = IV, II (大调)，iv, ii° (小调)
      D = V, V7, vii°, vii°7, 一切副属 (V/x)
    """
    if roman_numeral is None:
        return None

    # 副属是 D 解决到 V，归 D 组
    # music21 没有 .secondary 字段, 用 figure 含 "/" + secondaryRomanNumeral 非空 判断
    figure_for_sec = getattr(roman_numeral, "figure", "") or ""
    if getattr(roman_numeral, "secondaryRomanNumeral", None) is not None and "/" in figure_for_sec:
        return "D"

    figure = getattr(roman_numeral, "figure", "") or ""
    base = _figure_base(figure)
    # 优先匹配精确形式（带七等）
    if base in _BASE_FUNCTION_TABLE:
        return _BASE_FUNCTION_TABLE[base]
    # 退一步去掉可能的 7
    plain = base.rstrip("7")
    if plain in _BASE_FUNCTION_TABLE:
        return _BASE_FUNCTION_TABLE[plain]
    return None


def is_tonic(roman_numeral) -> bool:
    return function_from_roman(roman_numeral) == "T"


def is_subdominant(roman_numeral) -> bool:
    return function_from_roman(roman_numeral) == "S"


def is_dominant(roman_numeral) -> bool:
    return function_from_roman(roman_numeral) == "D"


# 斯波索宾和声学体系中的功能细化角色
ROLE_LABELS_ZH = {
    "primary": "原位",
    "extension": "延展",
    "substitute": "替代",
    "cadential": "终止",
    "passing": "经过",
    "neighbor": "辅助",
    "pedal": "持续",
    "secondary": "副属",
    "borrowed": "调式交替",
    "applied": "应用",
}


def function_label_zh(function: Optional[str], role: Optional[str] = None) -> str:
    """中文功能标签。

    function: T / S / D
    role:     primary / extension / substitute / cadential / passing / ...
    """
    base = {
        "T": "主功能",
        "S": "下属功能",
        "D": "属功能",
    }.get(function, "未识别")
    if not role:
        return base
    role_zh = ROLE_LABELS_ZH.get(role, role)
    return f"{base}·{role_zh}"


# 主要功能组的扩展（罗马数字 → 角色）
# 角色定义参考斯波索宾《和声学教程》各章描述
_ROLE_RULES = [
    # ----- T 主功能 -----
    {"function": "T", "role": "primary", "roman": "I", "degree": 1, "quality": "major"},
    {"function": "T", "role": "primary", "roman": "i", "degree": 1, "quality": "minor"},
    {"function": "T", "role": "extension", "roman": "VI", "degree": 6, "quality": "major"},
    {"function": "T", "role": "extension", "roman": "vi", "degree": 6, "quality": "minor"},
    {"function": "T", "role": "extension", "roman": "III", "degree": 3, "quality": "major"},
    {"function": "T", "role": "extension", "roman": "iii", "degree": 3, "quality": "minor"},
    # ----- S 下属功能 -----
    {"function": "S", "role": "primary", "roman": "IV", "degree": 4, "quality": "major"},
    {"function": "S", "role": "primary", "roman": "iv", "degree": 4, "quality": "minor"},
    {"function": "S", "role": "substitute", "roman": "II", "degree": 2, "quality": "major"},
    {"function": "S", "role": "substitute", "roman": "ii", "degree": 2, "quality": "minor"},
    {"function": "S", "role": "borrowed", "roman": "bII", "degree": 2, "quality": "major"},
    # ----- D 属功能 -----
    {"function": "D", "role": "primary", "roman": "V", "degree": 5, "quality": "major"},
    {"function": "D", "role": "primary", "roman": "V", "degree": 5, "quality": "minor"},  # 小调 V (和声小调)
    {"function": "D", "role": "primary", "roman": "vii", "degree": 7, "quality": "diminished"},
    {"function": "D", "role": "primary", "roman": "viiø43", "degree": 7, "quality": "half-diminished"},
]


def classify_chord_role(roman_numeral) -> dict:
    """为罗马数字打上"主功能 + 角色"标签。

    返回 {"function": "T"|"S"|"D", "role": "primary"|"extension"|...}
    """
    fn = function_from_roman(roman_numeral)
    if not fn:
        return {"function": None, "role": None}

    if getattr(roman_numeral, "secondary", False):
        return {"function": "D", "role": "applied"}

    figure = getattr(roman_numeral, "figure", "") or ""
    base = _figure_base(figure)
    # 借用
    if base.startswith("b") and "/" not in figure:
        # ♭III, ♭VI, ♭VII 是借用
        return {"function": fn, "role": "borrowed"}

    # 严格匹配 role
    for rule in _ROLE_RULES:
        if rule["roman"] != base:
            continue
        if rule.get("degree") and getattr(roman_numeral, "scaleDegree", None) != rule["degree"]:
            continue
        if rule.get("quality") and getattr(roman_numeral, "quality", None) != rule["quality"]:
            continue
        return {"function": rule["function"], "role": rule["role"]}

    # 兜底：按功能返回 primary
    return {"function": fn, "role": "primary"}
