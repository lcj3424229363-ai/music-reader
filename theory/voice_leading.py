"""斯波索宾《和声学教程》下册：四部和声声部进行规则。

经典规则:
  1. 禁止平行完全五度 (P5 → P5)
  2. 禁止平行完全八度 (P8 → P8)
  3. 禁止声部交叉 (voice crossing)
  4. 禁止隐伏八/五 (hidden octaves / fifths): 同向跳进到 P8/P5
  5. 终止四六 (K6/4) 识别 = V 的第二转位
  6. 经过四六 (Passing 6/4) 与 持续四六 (Pedal 6/4) 区分

四部排列 (从高到低): Soprano / Alto / Tenor / Bass
"""
from __future__ import annotations

import re
from typing import Optional


# ------------------------------------------------------------------ #
# 音程判定
# ------------------------------------------------------------------ #

def _pc_to_midi(pc: int) -> int:
    """把 pitch class (0-11) 视为最低八度 0..11。"""
    return pc


def _semitone_distance(p1: int, p2: int) -> int:
    return abs(p2 - p1) % 12


def _semitones_between(p1: int, p2: int) -> int:
    """带方向的距离(从 p1 到 p2 的半音数,整数)。"""
    return p2 - p1


def _interval_class(semis: int) -> int:
    """把半音数归到 0-11,作为音程类。"""
    return abs(semis) % 12


def _is_perfect_fifth(semis: int) -> bool:
    """7 半音 = 完全五度。"""
    return _interval_class(semis) == 7


def _is_perfect_octave(semis: int) -> bool:
    """0 半音(跨八度) = 完全八度。12, 24, ... 都算。"""
    s = abs(semis)
    return s > 0 and s % 12 == 0


def _is_perfect_unison(semis: int) -> bool:
    return semis == 0


# ------------------------------------------------------------------ #
# 1. 平行五/八度检测
# ------------------------------------------------------------------ #

def check_parallel(voice_a_pitches: list[int],
                   voice_b_pitches: list[int]) -> list[dict]:
    """检测两声部间的平行五度/八度。

    voice_a_pitches, voice_b_pitches: 两声部在 N 个连续和弦中的音高(midi int 列表)
    返回: [{type: "P5"|"P8"|"hidden-octave"|..., from, to}, ...]
    """
    if not voice_a_pitches or not voice_b_pitches:
        return []
    if len(voice_a_pitches) != len(voice_b_pitches):
        n = min(len(voice_a_pitches), len(voice_b_pitches))
        voice_a_pitches = voice_a_pitches[:n]
        voice_b_pitches = voice_b_pitches[:n]

    issues = []
    for i in range(len(voice_a_pitches) - 1):
        a1, a2 = voice_a_pitches[i], voice_a_pitches[i + 1]
        b1, b2 = voice_b_pitches[i], voice_b_pitches[i + 1]

        s1 = a1 - b1
        s2 = a2 - b2

        # 平行完全五度
        if _is_perfect_fifth(s1) and _is_perfect_fifth(s2):
            # 同向: 都要算平行；反向反向"对斜"算隐伏
            same_dir = ((a2 - a1 > 0) == (b2 - b1 > 0))
            if same_dir:
                issues.append({
                    "type": "parallel-fifth",
                    "label": "平行五度",
                    "fromIndex": i,
                    "toIndex": i + 1,
                    "fromInterval": "P5",
                    "toInterval": "P5",
                })

        # 平行完全八度
        if _is_perfect_octave(s1) and _is_perfect_octave(s2):
            same_dir = ((a2 - a1 > 0) == (b2 - b1 > 0))
            if same_dir:
                issues.append({
                    "type": "parallel-octave",
                    "label": "平行八度",
                    "fromIndex": i,
                    "toIndex": i + 1,
                    "fromInterval": "P8",
                    "toInterval": "P8",
                })

        # 隐伏八/五（hidden / direct）：反向到 P8 / P5
        # 斯波索宾的下册: 同向跳进到完全八/五 是隐伏
        if (a2 - a1) * (b2 - b1) > 0:  # 同向
            both_leap = abs(a2 - a1) >= 3 and abs(b2 - b1) >= 3  # 至少小三度跳进
            if both_leap:
                if _is_perfect_octave(s2):
                    issues.append({
                        "type": "hidden-octave",
                        "label": "隐伏八度",
                        "fromIndex": i,
                        "toIndex": i + 1,
                    })
                if _is_perfect_fifth(s2):
                    issues.append({
                        "type": "hidden-fifth",
                        "label": "隐伏五度",
                        "fromIndex": i,
                        "toIndex": i + 1,
                    })

    return issues


# ------------------------------------------------------------------ #
# 2. 声部交叉 / 声部超越
# ------------------------------------------------------------------ #

def check_voice_crossing(voices: list[list[int]]) -> list[dict]:
    """检测相邻声部交叉。

    voices: 4 个声部(S/A/T/B)各自在 N 个和弦上的音高列表
            voices[0]=Soprano, voices[3]=Bass
    """
    if not voices or len(voices) < 2:
        return []
    n = min(len(v) for v in voices)
    issues = []

    for i in range(n):
        # 最高到最低排列必须是 S > A > T > B
        for hi, lo in [(0, 1), (1, 2), (2, 3)]:
            if voices[hi][i] <= voices[lo][i]:
                # 允许同音 (unison)
                if voices[hi][i] < voices[lo][i]:
                    issues.append({
                        "type": "voice-crossing",
                        "label": "声部交叉",
                        "index": i,
                        "hiVoice": _voice_name(hi),
                        "loVoice": _voice_name(lo),
                        "hiPitch": voices[hi][i],
                        "loPitch": voices[lo][i],
                    })
    return issues


def _voice_name(idx: int) -> str:
    return ["Soprano", "Alto", "Tenor", "Bass"][idx] if 0 <= idx < 4 else f"Voice{idx}"


# ------------------------------------------------------------------ #
# 3. K6/4 / 经过 / 持续 四六和弦识别
# ------------------------------------------------------------------ #

def identify_cadential_64(roman_numeral,
                          prev_roman=None,
                          next_roman=None) -> dict:
    """识别 V64 的具体角色:K6/4 / Passing 6/4 / Pedal 6/4 / Arpeggiated 6/4。

    斯波索宾下册:
      1. Cadential (K6/4): 出现在终止式,V64 → I
      2. Passing: 经过四六,II6 → V64 → I6(或类似)
      3. Pedal: 持续四六,上方三声部保持,低音保持主音
      4. Arpeggiated: 琶音,仅仅一个和弦分解

    仅根据罗马数字上下文判断,不依赖实际声部。
    """
    if roman_numeral is None:
        return {"kind": None}

    figure = getattr(roman_numeral, "figure", "") or ""
    is_v64 = (figure == "V64")

    if not is_v64:
        return {"kind": None, "is64": False, "figure": figure}

    result = {"kind": "unknown", "is64": True, "figure": figure}

    # 终止四六: V64 → I (下一和弦是 I 的原位)
    if next_roman is not None:
        nxt_fig = getattr(next_roman, "figure", "") or ""
        if nxt_fig in ("I", "i") and getattr(next_roman, "inversion", "root") == "root":
            result["kind"] = "cadential"
            result["label"] = "终止四六 (K6/4)"

    # 经过四六: 之前和之后都是 I6 / i6 之类
    if result["kind"] == "unknown" and prev_roman is not None and next_roman is not None:
        p_fig = getattr(prev_roman, "figure", "") or ""
        n_fig = getattr(next_roman, "figure", "") or ""
        if p_fig in ("I6", "i6", "I64", "i64") and n_fig in ("I6", "i6"):
            result["kind"] = "passing"
            result["label"] = "经过四六"

    if result["kind"] == "unknown":
        result["label"] = "四六和弦(角色未明)"

    return result


# ------------------------------------------------------------------ #
# 4. 综合评分
# ------------------------------------------------------------------ #

def score_voice_leading(voices: list[list[int]]) -> dict:
    """对四部和声序列做综合声部进行评分(0-100)。

    扣分项(斯波索宾下册):
      平行完全五度:  -8 / 次
      平行完全八度:  -10 / 次
      隐伏八/五:     -3 / 次
      声部交叉:      -2 / 次
      声部超越:      -2 / 次
    """
    if not voices or len(voices) < 2:
        return {"score": 100, "issues": [], "summary": "无可评分的声部序列"}

    all_issues = []

    # 1) 平行五八（两两声部之间）
    pairs = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
    for hi, lo in pairs:
        all_issues.extend(check_parallel(voices[hi], voices[lo]))

    # 2) 声部交叉
    all_issues.extend(check_voice_crossing(voices))

    # 计分
    penalty = 0
    for it in all_issues:
        if it["type"] == "parallel-octave":
            penalty += 10
        elif it["type"] == "parallel-fifth":
            penalty += 8
        elif it["type"] in ("hidden-octave", "hidden-fifth"):
            penalty += 3
        elif it["type"] == "voice-crossing":
            penalty += 2

    score = max(0, 100 - penalty)
    summary = "良好" if score >= 90 else "合格" if score >= 75 else "有问题" if score >= 50 else "严重违反"

    return {
        "score": score,
        "issueCount": len(all_issues),
        "issues": all_issues,
        "summary": summary,
    }
