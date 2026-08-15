"""P20.3.7 Step 3 — 给 8 个 gold JSON 批量加 provenance 字段 (mark TODO 状态)。

不修改其他字段 (analysis_framework / roman_progression 等), 只追加:
- provenance.source_url: 沿用 metadata.source_url
- provenance.measure_range: 从 metadata.excerpt 解析
- provenance.acquired_status: "needs_imslp" (P20.3.7 Step 1 结论)
- provenance.review_status: "raw" (没人工校过)
- 其他字段 (source_score, annotator, confidence, evidence_chain) 留空

为什么是 "needs_imslp":
- music21 corpus 对这 8 个 case 一个都覆盖 (Bach 只有 BWV 8-89, Beethoven 全是弦乐四重奏)
- 全部需要从 IMSLP 获取 MusicXML
- 拿到谱面 + 人工标注才能改 status 为 "available" + "human_annotated"
"""
from __future__ import annotations

import json
import os
import re

GOLD_DIR = os.path.join(os.path.dirname(__file__), "gold")


def parse_measure_range(excerpt: str) -> str:
    """从 metadata.excerpt 提取 measure_range. 例 'mm.1-8 (1st theme)' → 'mm.1-8'."""
    m = re.match(r"mm\.\d+(?:-\d+)?", excerpt)
    return m.group(0) if m else ""


def make_provenance(metadata: dict) -> dict:
    """根据 metadata 生成 provenance 字段。"""
    return {
        "source_score": "",  # TODO: 下载到 MusicXML 后填
        "source_url": metadata.get("source_url", ""),  # 沿用 IMSLP URL
        "source_format": "",  # TODO: "musicxml" / "kern" / "pdf"
        "measure_range": parse_measure_range(metadata.get("excerpt", "")),
        "annotator": "",  # TODO: "human/<name>" or "ai/<model>"
        "annotate_date": "",  # ISO 8601
        "confidence": 0.0,  # 标记者自信度 (0=无, 1=专家审定)
        "evidence_chain": [],  # TODO: ["music21 corpus", "IMSLP", "Riemenschneider"]
        "acquired_status": "needs_imslp",  # P20.3.7 Step 1 结论
        "review_status": "raw",  # 没人校过
        "notes": "P20.3.7 — 当前无谱面, gold 是占位文本. 需获取 MusicXML + 人工标注后才能进入 benchmark.",
    }


def main():
    files = sorted(f for f in os.listdir(GOLD_DIR) if f.endswith(".json"))
    print(f"Found {len(files)} gold files")
    print()
    n_updated = 0
    n_skipped = 0
    for name in files:
        path = os.path.join(GOLD_DIR, name)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "provenance" in data and data["provenance"].get("acquired_status") != "needs_imslp":
            print(f"  SKIP {name} — 已有 provenance 且 status != needs_imslp")
            n_skipped += 1
            continue
        if "provenance" in data and data["provenance"].get("acquired_status") == "needs_imslp":
            # 已经是 TODO 状态,跳过
            print(f"  SKIP {name} — 已有 TODO provenance")
            n_skipped += 1
            continue
        # 加 provenance
        data["provenance"] = make_provenance(data["metadata"])
        # 写回
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        n_updated += 1
        mr = data["provenance"]["measure_range"]
        print(f"  + {name:40s} → provenance (mr={mr!r}, status=needs_imslp)")
    print()
    print(f"Updated: {n_updated}, Skipped: {n_skipped}")


if __name__ == "__main__":
    main()
