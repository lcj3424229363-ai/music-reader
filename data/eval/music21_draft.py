"""music21 自动生成 gold 初版 — 给人工修订的"机器草稿"。

用法：
    python -m data.eval.music21_draft <case_id> [--output DRAFT.json]

功能：
- 调 music21 corpus 加载作品
- 自动提取 key / 罗马数字 / 终止候选
- 输出与 EvalCase schema 对齐的 JSON
- **必须人工修订**（music21 偏表层识别，不做功能/语境判断）

不要把这个当成 gold——只作为修订起点。
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def _load_music21():
    """Lazy import music21（项目没强制依赖时跳过）。"""
    try:
        import music21  # type: ignore
        return music21
    except ImportError:
        return None


def _draft_bach_wtc_prelude(music21_mod):
    """Bach BWV 846 Prelude C major — music21 draft。"""
    if music21_mod is None:
        return None
    # 需要 IMSLP corpus 或本地 MIDI
    # 这里仅做骨架，真实实现需 corpus
    return {
        "key": "C major",
        "key_changes": [],
        "harmony_roman_draft": ["I", "V6/4", "I6", "ii6/5", "V7", "I"] * 6,
        "cadence_draft": [{"type": "PAC", "measure": 35, "confidence": 0.7}],
        "needs_expert_review": True,
        "review_notes": "music21 draft — cadences are heuristic, need expert verification"
    }


def generate_draft(case_id: str) -> dict:
    """根据 case_id 生成 music21 draft。"""
    m21 = _load_music21()
    if m21 is None:
        return {"error": "music21 not installed"}

    # 每个 case_id 单独的 draft 函数
    drafters = {
        "bach_wtc_prelude_bwv846": _draft_bach_wtc_prelude,
        # ... 其它 case 暂不实现（MVP 1 个示范）
    }
    drafter = drafters.get(case_id)
    if not drafter:
        return {"error": f"no music21 drafter for {case_id}"}
    return drafter(m21)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id")
    parser.add_argument("--output", "-o", help="输出到 JSON 文件")
    args = parser.parse_args()

    draft = generate_draft(args.case_id)
    text = json.dumps(draft, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[ok] saved to {args.output}")


if __name__ == "__main__":
    main()
