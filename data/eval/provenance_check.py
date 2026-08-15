"""P20.3.7 Step 1.5 — 精确 catalogue 编号搜 + 实际 parse 验证。

P20.3.7 Step 1 用通用关键词搜过宽了 (e.g. "beethoven" 26 hits 大部分是其他作品)。

正确做法:
1. 用具体 catalogue number 搜 (BWV 846 / K.545 / Op.13 / Hob.XVI:52 等)
2. 找到 MetadataEntry 后, 用 corpus.parse() 实际加载
3. 提取 m1-N 小节, 确认是 piano sonata 钢琴奏鸣曲 (不是合唱/管弦乐)
4. 报告 "可用 / 需 IMSLP / 不可用"

输出数据直接喂给 gold JSON 的 provenance 字段。
"""
from __future__ import annotations

import music21
import json
import os
import traceback


# 8 个 case 的具体 catalogue 编号 + IMSLP 入口
CASES = [
    {
        "id": "bach_wtc_prelude_bwv846",
        "catalogue": "BWV 846",
        "imslp_url": "https://imslp.org/wiki/Das_Wohltemperierte_Klavier_I,_BWV_846-869_(Bach,_Johann_Sebastian)",
        "music21_search": ["bwv846"],  # 直接搜 catalog id
        "expect_keys": ["C major", "Prelude"],
    },
    {
        "id": "bach_wtc_fugue_bwv846",
        "catalogue": "BWV 846",
        "imslp_url": "https://imslp.org/wiki/Das_Wohltemperierte_Klavier_I,_BWV_846-869_(Bach,_Johann_Sebastian)",
        "music21_search": ["bwv846"],
        "expect_keys": ["C major", "Fugue"],
    },
    {
        "id": "mozart_k545_m1",
        "catalogue": "K. 545",
        "imslp_url": "https://imslp.org/wiki/Piano_Sonata_No.16_in_C_major,_K.545_(Mozart,_Wolfgang_Amadeus)",
        "music21_search": ["k545"],
        "expect_keys": ["C major", "Sonata", "Allegro"],
    },
    {
        "id": "beethoven_pathetique_m1",
        "catalogue": "Op. 13",
        "imslp_url": "https://imslp.org/wiki/Piano_Sonata_No.8_in_C_minor,_Op.13_%22Path%C3%A9tique%22_(Beethoven,_Ludwig_van)",
        "music21_search": ["opus13", "pathetique", "sonata8"],
        "expect_keys": ["c minor", "Grave", "Sonata"],
    },
    {
        "id": "haydn_hobxvi52_m1",
        "catalogue": "Hob. XVI:52",
        "imslp_url": "https://imslp.org/wiki/Piano_Sonata_No.62_in_E-flat_major,_Hob.XVI/52_(Haydn,_Joseph)",
        "music21_search": ["hob", "xvi52"],
        "expect_keys": ["Eb major", "Sonata"],
    },
    {
        "id": "chopin_op9_no2",
        "catalogue": "Op. 9 No. 2",
        "imslp_url": "https://imslp.org/wiki/Nocturnes,_Op.9_(Chopin,_Fr%C3%A9d%C3%A9ric)",
        "music21_search": ["op9", "nocturne"],
        "expect_keys": ["Eb major", "Nocturne"],
    },
    {
        "id": "chopin_op28_no20",
        "catalogue": "Op. 28 No. 20",
        "imslp_url": "https://imslp.org/wiki/Preludes,_Op.28_(Chopin,_Fr%C3%A9d%C3%A9ric)",
        "music21_search": ["op28", "prelude"],
        "expect_keys": ["c minor", "Prelude"],
    },
    {
        "id": "schubert_op90_no3",
        "catalogue": "Op. 90 No. 3",
        "imslp_url": "https://imslp.org/wiki/4_Impromptus,_D.899_(Schubert,_Franz)",
        "music21_search": ["op90", "impromptu", "d899"],
        "expect_keys": ["Gb major", "Impromptu"],  # D.899 No.3 是 Gb major, 不是 Eb
    },
]


def find_in_corpus(term: str) -> list[music21.metadata.bundles.MetadataEntry]:
    """用具体 catalogue id 搜, 返回 MetadataEntry 列表 (不排序)."""
    try:
        return list(music21.corpus.search(term))
    except Exception:
        return []


def try_parse(path: str) -> dict:
    """实际 parse 一个 corpus path, 返回 {ok, n_measures, n_parts, key, title, error}."""
    try:
        score = music21.corpus.parse(path)
        n_measures = 0
        n_parts = 0
        key = ""
        title = ""
        try:
            n_measures = len(score.parts[0].getElementsByClass("Measure"))
            n_parts = len(score.parts)
            if score.parts[0].getElementsByClass("Key"):
                key = str(score.parts[0].getElementsByClass("Key")[0])
            title = score.metadata.title if score.metadata else ""
        except Exception:
            pass
        return {
            "ok": True,
            "path": path,
            "n_measures": n_measures,
            "n_parts": n_parts,
            "key": key,
            "title": title or "",
        }
    except Exception as e:
        return {"ok": False, "path": path, "error": str(e)[:200]}


def check_case(case: dict) -> dict:
    """对每个 case 试所有 search term, 第一个能 parse 的标 available."""
    result = {
        "id": case["id"],
        "catalogue": case["catalogue"],
        "imslp_url": case["imslp_url"],
        "expect_keys": case["expect_keys"],
        "candidates": [],
        "available": None,
        "status": "unknown",
    }
    for term in case["music21_search"]:
        hits = find_in_corpus(term)
        for h in hits:
            path = str(h)
            # 跳过大文件合唱作品
            if any(skip in path.lower() for skip in ["chorale", "cantata", "motet", "passion", "mass_"]):
                continue
            parse_result = try_parse(path)
            if parse_result.get("ok"):
                result["candidates"].append({"term": term, **parse_result})
                if result["available"] is None and parse_result.get("n_measures", 0) >= 4:
                    # 第一个能 parse 且有 ≥4 小节的 = best
                    result["available"] = {
                        "term": term,
                        **parse_result,
                    }

    # 决定 status
    if result["available"] is not None:
        result["status"] = "music21_available"
    elif result["candidates"]:
        result["status"] = "music21_partial"
    else:
        result["status"] = "needs_imslp"

    return result


def main():
    print("=" * 70)
    print("P20.3.7 Step 1.5 — 精确 catalogue 编号搜 + 实际 parse 验证")
    print("=" * 70)
    print(f"music21 version: {music21.__version__}")
    print()

    all_results = []
    for case in CASES:
        print(f"\n{'='*70}")
        print(f"  {case['id']}  ({case['catalogue']})")
        print(f"{'='*70}")
        r = check_case(case)
        all_results.append(r)
        print(f"  status: {r['status']}")
        if r["available"]:
            a = r["available"]
            print(f"  best: term='{a['term']}', path={a['path'][:60]}")
            print(f"    measures={a['n_measures']}, parts={a['n_parts']}, key={a['key']!r}, title={a['title']!r}")
        print(f"  candidates ({len(r['candidates'])}):")
        for c in r["candidates"][:3]:
            print(f"    • {c['path'][:60]} (m={c['n_measures']}, p={c['n_parts']}, key={c['key']!r})")

    # 汇总
    print("\n" + "=" * 70)
    print("汇总 (按 status 分类)")
    print("=" * 70)
    by_status = {}
    for r in all_results:
        by_status.setdefault(r["status"], []).append(r["id"])
    for s, ids in by_status.items():
        print(f"\n{s} ({len(ids)}/8):")
        for cid in ids:
            print(f"  - {cid}")

    # 写报告
    report_path = os.path.join(
        os.path.dirname(__file__), "provenance_check_report.json"
    )
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "music21_version": music21.__version__,
                "cases": all_results,
                "by_status": by_status,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\n详细报告写入: {report_path}")
    return all_results


if __name__ == "__main__":
    main()
