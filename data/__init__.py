"""数据和案例库 — ReAct Agent 检索和推理的知识源。

子模块：
- repertoire: 经典作品曲式+和声分析案例（贝多芬、肖邦、巴赫、莫扎特、德彪西 等）
- error_cases: 四部和声写作常见错误案例（平行五八、声部交叉、隐藏五度 等）
- style_profiles: 5 流派分析标准（sposobin / schoenberg / functional / modal / jazz）

所有数据使用 dataclass，可被 theory/ 和 llm/ 模块直接 import。
"""
