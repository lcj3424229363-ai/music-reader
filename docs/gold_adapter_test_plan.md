# P20.3.7 — Gold Adapter & Benchmark Test Plan

**日期**: 2026-08-11
**目的**: 在 P20.3.7 Phase 1-4 调研 / 设计完成后, 列出实现阶段 (Phase 2-3 实施 + P20.7) 的测试计划

---

## 0. 测试分层

| 层 | 工具 | 目标 |
|---|---|---|
| **Unit** | `pytest` | 单一函数 / 类正确性 |
| **Integration** | `pytest` | 多模块协作 (adapter → EvalCase) |
| **Schema** | `pytest` + 自定义 validator | JSON 加载 / 字段约束 |
| **End-to-end** | `pytest` + 真实数据 | 8 case 端到端 (生成 → 验证 → 跑 benchmark) |
| **E2E LLM** | curl + LLM API | LLM 解释验证 (P19 经验) |

---

## 1. Unit Tests (P20.3.7 实施阶段)

### 1.1 external_annotation.py

```python
# tests/gold_adapter/test_external_annotation.py

def test_external_annotation_defaults():
    """所有字段默认空."""
    ann = ExternalAnnotation(piece_id="test", source_dataset="x", source_dataset_url="y", source_format="z", measure_range="mm.1-8")
    assert ann.score is None
    assert ann.notes == ""
    assert ann.evidence_chain == []

def test_external_annotation_required_fields():
    """必填字段缺失应抛错."""
    with pytest.raises(TypeError):
        ExternalAnnotation()  # 缺 piece_id
```

### 1.2 dcmlab_adapter.py

```python
# tests/gold_adapter/test_dcmlab_adapter.py

def test_dcmlab_load_mozart_k545():
    """核心: 用真实 DCMLab 数据加载 Mozart K545-1."""
    # 需先 git clone DCMLab/mozart_piano_sonatas 到 tests/fixtures/external/
    ann = load_dcmlab(
        piece_id="mozart_k545_m1",
        harmonies_tsv_path="tests/fixtures/external/DCMLab_mozart/harmonies/K545-1.harmonies.tsv",
        measures_tsv_path="tests/fixtures/external/DCMLab_mozart/measures/K545-1.measures.tsv",
    )
    assert ann.source_dataset == "DCMLab/mozart_piano_sonatas"
    assert ann.source_format == "dcml_tsv"
    assert ann.annotator == "human/Uli Kneisel"
    assert len(ann.measures) == 73

def test_dcmlab_load_beethoven_op13_m1():
    """核心: 用真实 DCMLab 数据加载 Beethoven Op.13 Mvt 1."""
    ann = load_dcmlab(...)
    assert ann.source_dataset == "DCMLab/beethoven_piano_sonatas"
    assert ann.annotator == "human/Lydia Carlisi + human/John Heilig"
    assert len(ann.measures) == 310

def test_dcmlab_missing_file_raises():
    """TSV 缺失应抛错, 不静默."""
    with pytest.raises(FileNotFoundError):
        load_dcmlab(piece_id="x", harmonies_tsv_path="nonexistent.tsv", measures_tsv_path="y")

def test_dcmlab_invalid_format_raises():
    """TSV 列缺失应抛 ValueError, 不静默."""
    bad_tsv = tmp_path / "bad.tsv"
    bad_tsv.write_text("wrong_col\twrong\n")
    with pytest.raises(ValueError, match="Missing required column"):
        load_dcmlab(piece_id="x", harmonies_tsv_path=str(bad_tsv), ...)

def test_dcmlab_mozart_m1_cadences():
    """m.4 HC + m.8 PAC 必须正确解析."""
    ann = load_dcmlab(...)
    m4 = next(m for m in ann.measures if m["measure"] == 4)
    assert m4["cadence"] == "HC"
    m8 = next(m for m in ann.measures if m["measure"] == 8)
    assert m8["cadence"] == "PAC"

def test_dcmlab_extracts_secondary_dominants():
    """V/V 等 secondary 标签必须保留 (DCML 风格)."""
    ann = load_dcmlab("beethoven_pathetique_m1", ...)
    # m.5 或 m.9 应该有 V/V (慢引子有 secondary)
    has_secondary = any("V/" in c["roman"] for m in ann.measures for c in m["chords"])
    assert has_secondary
```

### 1.3 humdrum_adapter.py

```python
# tests/gold_adapter/test_humdrum_adapter.py

def test_humdrum_load_bach_wtc_prelude():
    """核心: Bach WTC Prelude 1 谱面正确加载 (无 Roman numeral)."""
    ann = load_humdrum_kern(
        piece_id="bach_wtc_prelude_bwv846",
        kern_file_path="tests/fixtures/external/humdrum_bach-wtc/kern/wtc1p01.krn",
    )
    assert ann.source_dataset == "humdrum-tools/bach-wtc"
    assert ann.source_format == "humdrum_kern"
    assert ann.annotator == "unknown"  # NO annotation
    assert ann.annotation_standard == "none"
    # 35 measures 大约
    assert 30 <= len(ann.measures) <= 40

def test_humdrum_no_roman_numerals():
    """Humdrum kern 没标 Roman numeral, 必须 None."""
    ann = load_humdrum_kern(...)
    for m in ann.measures:
        for c in m["chords"]:
            assert c["roman"] is None

def test_humdrum_load_mozart_k545():
    """Mozart K545 谱面正确加载 (craigsapp sonata08-1)."""
    ann = load_humdrum_kern(
        piece_id="mozart_k545_m1",
        kern_file_path="tests/fixtures/external/craigsapp_mozart/sonata08-1.krn",
    )
    assert 70 <= len(ann.measures) <= 80
    # music21 解析的 key
    assert ann.measures[0]["key"] == "C major"

def test_humdrum_load_chopin_prelude28_20():
    """Chopin Op.28 No.20."""
    ann = load_humdrum_kern(...)
    assert 20 <= len(ann.measures) <= 30
    assert ann.measures[0]["key"] == "c minor"
```

### 1.4 augmentednet_adapter.py

```python
# tests/gold_adapter/test_augmentednet_adapter.py

def test_augmentednet_csv_format():
    """AugmentedNet CSV 正确解析."""
    fake_csv = """onset,key,degree,quality,inversion,roman,RN
0.0,C,1,M,0,I,I
0.5,C,2,m,0,ii,ii
"""
    ann = load_augmentednet_csv_text("test", fake_csv)
    assert ann.source_format == "augmentednet_json"  # or augmentednet_csv
    assert ann.confidence < 0.6
    assert ann.annotator == "augmentednet_v1.0.0"

def test_augmentednet_inferred_marks_auto_generated():
    """AI 推断必须 mark review_status='auto_generated'."""
    ann = load_augmentednet_csv_text("test", "onset,key,degree,quality,inversion,roman,RN\n0,C,1,M,0,I,I")
    # 由 convert_to_mtre.py 强制:
    case = external_to_evalcase(ann)
    assert case.provenance.review_status == "auto_generated"
    assert case.needs_expert_review is True
```

### 1.5 convert_to_mtre.py

```python
# tests/gold_adapter/test_convert_to_mtre.py

def test_normalize_function_sposobin_v1():
    """Sposobin V1 function 归一化."""
    assert normalize_function_sposobin("I", "M") == "T"
    assert normalize_function_sposobin("I6", "M") == "T"
    assert normalize_function_sposobin("IV", "M") == "S"
    assert normalize_function_sposobin("V7", "M") == "D"
    assert normalize_function_sposobin("vi", "m") == "T"  # V1: vi 归 T
    assert normalize_function_sposobin("vii°7", "°") == "D"  # 导音归 D
    assert normalize_function_sposobin("V7/V", "M") == "D"  # secondary 归 D
    assert normalize_function_sposobin("ii", "m") == "T"  # V1: ii 是 pre-D, 归 T (保守)

def test_normalize_function_functional_classical():
    """functional_classical 允许 T-sub."""
    assert normalize_function("vi", "m", mtre_style="functional_classical") == "T-sub"
    assert normalize_function("V7/V", "M", mtre_style="functional_classical") == "D/V"  # secondary 标签

def test_external_to_evalcase_dcmlab_mozart():
    """端到端: DCMLab → MTRE."""
    ann = load_dcmlab("mozart_k545_m1", ...)
    case = external_to_evalcase(ann, mtre_style="sposobin")
    # 验证所有字段填全
    assert case.metadata.id == "mozart_k545_m1"
    assert case.analysis.key == "C major"
    assert case.provenance.acquired_status == "available"
    assert case.provenance.review_status == "expert_reviewed"
    # V1 纯 T/S/D
    for f in case.analysis.harmony.functional_analysis:
        assert f in ("T", "S", "D"), f"Got {f}"
```

---

## 2. Schema Tests (P20.3.7 实施阶段)

### 2.1 增强版 Provenance 验证

```python
# tests/test_p20_3_7_provenance_v2.py

def test_validate_provenance_availability_consistency():
    """acquired_status=available 必须有 source_score."""
    p = Provenance(acquired_status="available", source_score="")
    issues = validate_provenance(p)
    assert any("ERROR" in i for i in issues)

def test_validate_provenance_annotator_format():
    """review_status 决定 annotator 前缀."""
    # auto_generated 必须 ai/augmentednet/music21-auto
    p = Provenance(review_status="auto_generated", annotator="human/x")
    issues = validate_provenance(p)
    assert any("ERROR" in i for i in issues)

    p = Provenance(review_status="human_annotated", annotator="human/Uli Kneisel")
    issues = validate_provenance(p)
    assert not any("ERROR" in i for i in issues)

def test_validate_provenance_license_warning():
    """available 但没 license → 警告 (不阻断)."""
    p = Provenance(acquired_status="available", source_score="x", license="")
    issues = validate_provenance(p)
    assert any("WARN" in i for i in issues)

def test_load_old_gold_compat():
    """旧 gold JSON 加载不应破坏 (字段缺失用 default)."""
    old_json = {"metadata": {"id": "x", "composer": "y", "title": "z"}, "analysis": {"key": "C major", "harmony": {"roman_progression": [], "functional_analysis": []}, "cadences": []}, "provenance": {"source_score": "", "confidence": 0.5}}
    case = EvalCase.from_dict(old_json)
    # 旧 confidence 字段应自动迁移到 annotation_confidence
    assert case.provenance.annotation_confidence == 0.5
```

### 2.2 deprecated 字段

```python
def test_deprecated_field():
    """deprecated case 应被 find_fully_reviewed() 排除."""
    case = EvalCase(...)
    case.deprecated = True
    case.provenance.acquired_status = "available"
    case.provenance.review_status = "expert_reviewed"
    # deprecated case 仍能加载, 但不进 fully reviewed 列表
    # 实现见 find_fully_reviewed()
```

---

## 3. Integration Tests (P20.3.7 实施阶段)

```python
# tests/gold_adapter/test_integration.py

@pytest.mark.integration
def test_full_pipeline_dcmlab_mozart(tmp_path):
    """完整流程: DCMLab TSV → ExternalAnnotation → EvalCase → JSON → 加载回来."""
    # 1. 加载 DCMLab
    ann = load_dcmlab("mozart_k545_m1", ...)

    # 2. 转 EvalCase
    case = external_to_evalcase(ann, mtre_style="sposobin")

    # 3. 序列化到 JSON
    json_path = tmp_path / "mozart_k545_m1.json"
    with open(json_path, "w") as f:
        json.dump(case.to_dict(), f, ensure_ascii=False, indent=2)

    # 4. 从 JSON 加载回来
    case2 = EvalCase.from_json_file(str(json_path))

    # 5. 验证一致
    assert case2.metadata.id == case.metadata.id
    assert case2.analysis.key == case.analysis.key
    assert case2.provenance.source_dataset == case.provenance.source_dataset
    assert len(case2.analysis.harmony.roman_progression) == len(case.analysis.harmony.roman_progression)

@pytest.mark.integration
def test_full_pipeline_humdrum_augmentednet(tmp_path):
    """完整流程: Humdrum kern + AugmentedNet (mock) → EvalCase."""
    # 1. 加载 Humdrum
    humdrum_ann = load_humdrum_kern("bach_wtc_prelude_bwv846", "wtc1p01.krn")
    assert humdrum_ann.measure_count == 35

    # 2. mock AugmentedNet 输出 (因为我们不会真跑 ML 模型)
    augmented_csv = "onset,key,degree,quality,inversion,roman,RN\n" + \
                    "0,C,1,M,0,I,I\n" * 35 + \
                    "..."  # 真实 AugmentedNet 输出
    augmented_ann = load_augmentednet_csv_text("bach_wtc_prelude_bwv846", augmented_csv)

    # 3. 合并: 谱面 from Humdrum + 标注 from AugmentedNet (人工合并, mock)
    merged_ann = merge_annotations(humdrum_ann, augmented_ann)
    # 4. 转 EvalCase
    case = external_to_evalcase(merged_ann, mtre_style="sposobin")
    # 5. 验证
    assert case.provenance.source_score_format == "kern"
    assert case.provenance.source_annotation_format == "augmentednet_csv"
    assert case.provenance.review_status == "auto_generated"
    assert case.needs_expert_review is True
```

---

## 4. End-to-End Tests (P20.7 阶段)

```python
# tests/test_benchmark_v1.py

@pytest.mark.e2e
def test_benchmark_runs_on_5_cases():
    """P20.7 benchmark 跑 5 case (2 黄金 + 3 银)."""
    # 1. 加载所有 gold (除 deprecated)
    cases = find_fully_reviewed()  # 2 cases initially
    # + AugmentedNet 处理后 3 more
    assert len(cases) == 5

    # 2. 模拟 Agent 输出 (mock 5 个 case)
    agent_results = [
        AgentResult(case_id="mozart_k545_m1", predicted_romans=["I", "V7", ...], predicted_cadences=[...]),
        # ...
    ]

    # 3. 跑 benchmark
    report = run_benchmark(agent_results, mtre_style="sposobin")

    # 4. 验证报告
    assert "mozart_k545_m1" in report.case_results
    assert "beethoven_pathetique_m1" in report.case_results
    assert "bach_wtc_prelude_bwv846" in report.case_results
    assert "chopin_op28_no20" in report.case_results
    # 黄金级 vs 银级分别统计
    assert report.gold_accuracy > report.silver_accuracy - 0.1  # 黄金级应不差于银级

@pytest.mark.e2e
def test_benchmark_rejects_deprecated_cases():
    """deprecated case (3 个) 不进 benchmark."""
    cases = find_fully_reviewed()
    ids = [c.metadata.id for c in cases]
    assert "haydn_hobxvi52_m1" not in ids
    assert "chopin_op9_no2" not in ids
    assert "schubert_op90_no3" not in ids
    assert "bach_wtc_fugue_bwv846" not in ids
```

---

## 5. E2E LLM Tests (P19 经验, P20.7 阶段)

```python
# tests/test_benchmark_llm_e2e.py

@pytest.mark.llm_e2e
@pytest.mark.skipif(not os.getenv("DEEPSEEK_API_KEY"), reason="No API key")
def test_llm_explains_mozart_k545_in_chinese():
    """LLM 用中文解释 Mozart K545-1, 必须提到 DCMLab 标注."""
    case = get_gold("mozart_k545_m1")  # DCMLab 替换后
    response = call_llm_explain(case, language="zh")
    # LLM 必须能解释
    assert response.status_code == 200
    # 解释中应提到关键 chord / cadence
    assert "PAC" in response.text or "终止" in response.text
    assert "C major" in response.text or "C 大调" in response.text
```

---

## 6. Test Fixtures Setup

### 6.1 必要的 fixture

```
tests/fixtures/
├── external/
│   ├── DCMLab_mozart/                  # git clone DCMLab/mozart_piano_sonatas
│   │   ├── harmonies/K545-1.harmonies.tsv
│   │   ├── measures/K545-1.measures.tsv
│   │   └── MS3/K545-1.mscx
│   ├── DCMLab_beethoven/               # git clone DCMLab/beethoven_piano_sonatas
│   │   ├── harmonies/08-1.harmonies.tsv
│   │   ├── measures/08-1.measures.tsv
│   │   └── MS3/08-1.mscx
│   ├── humdrum_bach-wtc/               # git clone humdrum-tools/bach-wtc
│   │   └── kern/wtc1p01.krn
│   ├── humdrum_bach-wtc/               # git clone humdrum-tools/bach-wtc
│   │   └── kern/wtc1f01.krn
│   ├── craigsapp_mozart/               # git clone craigsapp/mozart-piano-sonatas
│   │   └── kern/sonata08-1.krn
│   ├── craigsapp_chopin-preludes/      # git clone craigsapp/chopin-preludes
│   │   └── kern/prelude28-20.krn
│   └── augmentednet_mock/              # mock CSV, 不跑真模型
│       └── wtc1p01_annotated.csv
└── scripts/
    └── setup_fixtures.sh               # git clone 脚本
```

### 6.2 setup_fixtures.sh

```bash
#!/bin/bash
# P20.3.7 fixture setup — 把外部数据 clone 到 tests/fixtures/external/
# 注意: DCMLab CC BY-NC-SA 4.0, 使用前确认
set -e

FIXTURES=tests/fixtures/external
mkdir -p $FIXTURES

# DCMLab Mozart (含 K545-1)
git clone --depth 1 https://github.com/DCMLab/mozart_piano_sonatas.git $FIXTURES/DCMLab_mozart

# DCMLab Beethoven (含 Op.13 Mvt 1 = 08-1)
git clone --depth 1 https://github.com/DCMLab/beethoven_piano_sonatas.git $FIXTURES/DCMLab_beethoven

# Humdrum Bach WTC
git clone --depth 1 https://github.com/humdrum-tools/bach-wtc.git $FIXTURES/humdrum_bach-wtc

# craigsapp Mozart piano sonatas
git clone --depth 1 https://github.com/craigsapp/mozart-piano-sonatas.git $FIXTURES/craigsapp_mozart

# craigsapp Chopin preludes
git clone --depth 1 https://github.com/craigsapp/chopin-preludes.git $FIXTURES/craigsapp_chopin-preludes

echo "✅ All fixtures ready"
ls -la $FIXTURES
```

**注意**: setup_fixtures.sh 不在 CI 中跑 (因 DCMLab license + 网络), 只在本地或 docker 中跑。

### 6.3 conftest.py

```python
# tests/gold_adapter/conftest.py

import pytest
import os

@pytest.fixture(scope="session")
def dcmlab_mozart_path():
    return "tests/fixtures/external/DCMLab_mozart"

@pytest.fixture(scope="session")
def dcmlab_beethoven_path():
    return "tests/fixtures/external/DCMLab_beethoven"

@pytest.fixture(scope="session")
def humdrum_bach_wtc_path():
    return "tests/fixtures/external/humdrum_bach-wtc"

@pytest.fixture
def skip_if_no_fixtures():
    """如果 fixtures 不存在, skip 测试."""
    fixtures_dir = "tests/fixtures/external"
    if not os.path.isdir(fixtures_dir):
        pytest.skip(f"Fixtures not found at {fixtures_dir}. Run tests/fixtures/scripts/setup_fixtures.sh")
```

---

## 7. CI 集成

### 7.1 GitHub Actions / 本地 CI

```yaml
# .github/workflows/test_p20_3_7.yml
name: P20.3.7 Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      # 跳过 fixture setup (license 问题)
      - name: Run unit + integration tests
        run: |
          pytest tests/test_p20_3_eval.py \
                 tests/test_p20_3_7_provenance.py \
                 tests/gold_adapter/ \
                 -m "not e2e and not llm_e2e" -v
      # E2E 只在手动触发时跑
      - name: Run e2e tests (manual only)
        if: github.event_name == 'workflow_dispatch'
        run: |
          bash tests/fixtures/scripts/setup_fixtures.sh
          pytest tests/test_benchmark_v1.py tests/test_benchmark_llm_e2e.py -v
```

### 7.2 本地运行命令

```bash
# 一次性 fixture setup
bash tests/fixtures/scripts/setup_fixtures.sh

# 跑所有 P20.3.7 测试 (慢)
cd music-reader
python -X utf8 -m pytest tests/test_p20_1_style_profiles.py \
                       tests/test_p20_2_agent.py \
                       tests/test_p20_3_eval.py \
                       tests/test_p20_3_7_provenance.py \
                       tests/gold_adapter/ \
                       tests/test_benchmark_v1.py \
                       -v

# 跑 P20.3.7 新测试
python -X utf8 -m pytest tests/test_p20_3_7_provenance.py tests/gold_adapter/ -v
```

---

## 8. Acceptance Criteria (验收标准)

按 Phase 1-4 调研 / 设计 + Phase 5 测试, P20.3.7 实施的验收标准:

### 8.1 必需 (must have)

- [ ] P0: Phase 0 架构报告 (本文档 §1) 描述清楚
- [ ] P1: Phase 1 调研报告 (`gold_dataset_research.md`) 完成, 5 个数据源 + 8 case 状态表
- [ ] P2: Gold Adapter 设计 (`gold_adapter_design.md`) 完成, 4 个 adapter + 统一中间格式
- [ ] P3: Schema Provenance 增强 (`schema_provenance_enhancement.md`) 完成
- [ ] P4: Benchmark Recommendation (`benchmark_recommendation.md`) 完成, 8 case 分级
- [ ] P5: 测试计划 (本文档) 完成
- [ ] **P5 acceptance**: Test fixtures 准备 (git clone 4 个 repo)
- [ ] **P5 acceptance**: `pytest tests/gold_adapter/ -v` 全过 (含 unit + integration)
- [ ] **P5 acceptance**: `pytest tests/test_p20_3_7_provenance.py -v` 全过
- [ ] **P5 acceptance**: 现有 19 + 160 测试不破坏 (P20.1+P20.2+P20.3+P20.3.7)

### 8.2 推荐 (nice to have)

- [ ] Mozart K545-1 gold JSON 用 DCMLab 数据替换
- [ ] Beethoven Op.13 gold JSON 用 DCMLab 数据替换
- [ ] 3 case (Haydn, Chopin Op.9, Schubert) mark deprecated
- [ ] Schubert key 修 (Eb → Gb)
- [ ] E2E benchmark 跑 5 case

### 8.3 不要 (out of scope)

- ❌ 不实现 P20.7 Benchmark Runner (P20.3.7 不写, 留 P20.7)
- ❌ 不改 gold JSON 音乐内容 (V1 完整 gold 待 P20.7 重写时一并改)
- ❌ 不修复 P20.3.5 提出的音乐内容冲突 (Bach V6/4 vs K6/4 等)
- ❌ 不写新的 V2 gold (jazz/modal) — V2 不在 P20.3.7 范围

---

## 9. 时间表 (整体)

| Phase | 任务 | 估时 |
|---|---|---|
| **Phase 0** | 架构检查报告 | 已完成 |
| **Phase 1** | 数据源调研 | 已完成 |
| **Phase 2** | Gold Adapter 设计 | 已完成 |
| **Phase 3** | Schema Provenance 增强 | 已完成 |
| **Phase 4** | Benchmark Recommendation | 已完成 |
| **Phase 5** | 测试计划 | 已完成 |
| **P20.3.7 实施** | external_annotation.py + schema 增强 | 4h |
| | dcmlab_adapter.py + 5 测试 | 6h |
| | humdrum_adapter.py + 3 测试 | 3h |
| | augmentednet_adapter.py + 2 测试 | 4h |
| | imslp_adapter.py + 1 测试 | 2h |
| | convert_to_mtre.py + Sposobin V1 归一化 | 4h |
| | Mozart K545-1 + Beethoven Op.13 gold 重写 | 4h |
| | 3 case deprecated 标记 | 1h |
| | schema 测试 (P20.3.7 v2) | 2h |
| | 端到端集成测试 | 3h |
| **P20.7** | Benchmark Runner | 8h |
| **总计** | | **~43h (5.5 工作日)** |

---

## 10. 风险与缓解

| 风险 | 缓解 |
|---|---|
| DCMLab 数据被 license 限制 (CC BY-NC-SA) | 在 README 标 license, MTRE 商业版只能用 Humdrum + AugmentedNet + 人工 |
| AugmentedNet 推断准确度低 (47.9% RN) | 必须人工校, mark `auto_generated`, 不进 V1 gold |
| Humdrum kern 解析失败 (music21 兼容性) | 用 music21 主流 API, 失败时 fallback 用 verovio |
| Schubert key 错误修后 benchmark 行为变化 | 是事实修正, 必须做 |
| Fixture 数据大 (>100MB) | 不进 git, 写 setup script, CI 用 shallow clone --depth 1 |
| 测试慢 (pytest 跑 5 分钟+) | 分离 unit (快) vs e2e (慢), 慢测试用 -m e2e 标记 |

---

## 11. 总结

P20.3.7 实施阶段的测试计划:
- **Unit tests**: 5+ 个文件, ~30 个测试 (external_annotation / dcmlab / humdrum / augmentednet / imslp / convert)
- **Integration tests**: 2 个端到端 (DCMLab + Humdrum+AUG)
- **Schema tests**: 4 个 Provenance 验证
- **E2E tests**: 1 个 benchmark, 1 个 LLM e2e
- **总计**: ~40 个测试

**关键验收**:
- 现有 160 个测试不破坏
- 新 40+ 个测试全过
- Fixture setup script 文档化
- 5/8 case 实际可跑 benchmark (2 黄金 + 3 银, 1 暂缓, 3 移除)
