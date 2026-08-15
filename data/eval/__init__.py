"""P20.3-A 评价数据集 — Gold Benchmark。

设计哲学：
- Evaluation Driven Development：先测后做
- JSON 是 source of truth（手写、人工审校）
- Python dataclass 是程序读取层
- 音乐理论非唯一答案 → alternative_analysis 字段

文件结构：
  data/eval/
    schema.py           — EvalCase dataclass + load + validate
    gold/               — 12 个手写 gold JSON 文件
      bach_wtc_prelude_bwv846.json
      bach_wtc_fugue_bwv846.json
      mozart_k545_m1.json
      beethoven_pathetique_m1.json
      haydn_hobxvi52_m1.json
      chopin_op9_no2.json
      chopin_op28_no20.json
      schubert_op90_no3.json
      debussy_faun.json
      ravel_jeux_deau.json
      autumn_leaves.json
      so_what.json
    music21_draft.py    — music21 自动生成 key/罗马数字初版（待人工校）
    benchmark.py        — 跑 Agent 对比 gold，输出 accuracy 报告

12 个 gold 分布（4 流派平衡）：
  古典 (6): Bach Prelude / Bach Fugue / Mozart K545 / Beethoven Pathétique /
            Haydn Hob.XVI:52 / Chopin Op.9 No.2
  浪漫 (2): Chopin Op.28 No.20 / Schubert Op.90 No.3
  印象派 (2): Debussy Faun / Ravel Jeux d'eau
  Jazz (2):  Autumn Leaves / So What
"""
