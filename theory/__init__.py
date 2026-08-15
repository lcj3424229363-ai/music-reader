"""斯波索宾《和声学教程》体系下的乐理分析模块。

参考：
- 里姆斯基-科萨科夫《和声学实用教程》传统斯波索宾体系
- 斯波索宾《和声学教程》（上、下册）
- 音乐分析的功能和声学方法（Schenkerian Functional Harmony）
"""

from .functions import (
    PRIMARY_FUNCTIONS,
    function_from_roman,
    function_label_zh,
    is_dominant,
    is_tonic,
    is_subdominant,
)
from .roman_analyzer import (
    analyze_score,
    analyze_chord_in_key,
    detect_modulation,
)
from .cadence import detect_cadences
from .secondary import detect_secondary, detect_borrowed
from .voice_leading import (
    check_parallel,
    check_voice_crossing,
    identify_cadential_64,
    score_voice_leading,
)

__all__ = [
    "PRIMARY_FUNCTIONS",
    "function_from_roman",
    "function_label_zh",
    "is_dominant",
    "is_tonic",
    "is_subdominant",
    "analyze_score",
    "analyze_chord_in_key",
    "detect_modulation",
    "detect_cadences",
    "detect_secondary",
    "detect_borrowed",
    "check_parallel",
    "check_voice_crossing",
    "identify_cadential_64",
    "score_voice_leading",
]
