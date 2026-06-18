# HANDOFF.md

最后更新：2026-06-18（Asia/Shanghai）

## 当前目标

继续完善 Amazon 库存利润分析器。本次把 Fang 品线诊断从“表格明细”升级为“先汇报、后明细”：增加管理层文字摘要和 ToDo 执行摘要，同时保留现有指标、诊断表和可编辑任务明细；底层指标、SKU 角色、系统动作和优先级保持不变。

## 仓库状态

- 项目仓库：当前目录 `amazon-inventory-profit-analyzer/`。
- 当前分支：`codex/fix-fang-data-credibility`，已推送并创建草稿 PR #1；本次汇报改造基于 `af7bda4 Fix Fang data credibility checks`。
- 目标发布分支：`main`。
- 外层 `New project/` 还有一个独立旧仓库；它不是本项目提交和状态判断的依据。

本次汇报改造范围：

- `modules/product_line_diagnosis.py`：新增管理层摘要和 ToDo 执行摘要，汇总经营概况、优先风险、增长机会、数据边界、任务数量、优先级、责任人、截止日和首要动作。
- `app.py`：品线诊断调整为先展示管理层汇报摘要；ToDo 区先展示执行摘要，再展示可编辑明细。
- `tests/test_product_line_diagnosis.py`：增加文字汇报和 ToDo 摘要回归测试。
- `HANDOFF.md`：记录本次汇报层改造、验证结果和下一步。

当前未跟踪内容（本次未修改、未接入现有应用）：

- `config/fang_diagnosis.yaml`
- `fang_diagnosis/`

当前 HEAD 已包含的近期发布内容：

- `README.md`：补充 Fang 诊断与 ToDo 说明。
- `app.py`：增加可信度、经营关系诊断和 ToDo 编辑界面。
- `modules/product_line_diagnosis.py`：增加原因分级、可信度检查、关系诊断和 ToDo 生成。
- `tests/test_product_line_diagnosis.py`：增加相应回归测试。
- `config/column_mapping.yaml`：新增 `category_level_3` 及三级分类常用别名。
- `modules/pipeline.py`：完整 SKU 输出保留三级分类。
- `tests/test_filters.py`：新增三级分类与其他维度双向联动测试。
- `modules/recommendations.py`：已从发布前 HEAD 原样恢复，动作规则未改写。
- `.gitignore`：增加 `.DS_Store` 忽略规则。

本轮新增治理文档：

- `AGENTS.md`
- `HANDOFF.md`
- `PLANS.md`
- `docs/business-rules.md`
- `docs/data-dictionary.md`
- `docs/decisions.md`

## 已验证

- `.venv/bin/python -c "import app"`：通过。
- `.venv/bin/python -m pytest -q -p no:cacheprovider`：原生运行 47 个测试，全部通过。
- `tests/test_product_line_diagnosis.py`：8 个定向测试全部通过；覆盖数据可信度、管理层摘要、ToDo 摘要和报告层不改写系统判断。
- Excel 11 Sheet 内存导出冒烟：通过。
- Streamlit 本地启动成功，`/_stcore/health` 返回 `ok`。
- 浏览器复核上传首页：应用正常启动，标题、上传区和使用说明正常显示，控制台无错误。因仓库无样例 Excel，本次未通过浏览器进入品线汇报页。
- `git diff --check` 通过。

## 剩余风险

1. `st.data_editor` 的返回值尚未接收；ToDo 可在页面编辑，但没有明确的持久化或 Excel 导出闭环。
2. 尚无可提交的输入样例文件用于端到端上传验证；`output/reports/` 中只有被忽略的历史冒烟输出。
3. 未跟踪的 `fang_diagnosis/` 与当前已上线的 `modules/product_line_diagnosis.py` 是两套潜在重复实现；在确认其用途前不得删除、提交或接入。

## 本轮筛选器命名发布

- 筛选器显示名更新为：父ASIN、品线、尺寸、SKU角色定位、处理优先级、库存天数情况、毛利率水平、周转水平、现金流风险。
- 底层字段名、筛选 key 和串联逻辑保持不变。

## 本轮界面优化发布

- 首页改为“亚马逊库存与利润决策台”，补充产品价值、三步流程和上传检查清单。
- 经营总览聚焦三组 12 个核心指标，其余指标收入展开区。
- 导航缩短为业务名称，并为每个栏目增加用途说明。
- 侧边栏增加筛选影响说明、筛选状态和一键清空。
- 表格空状态、文件识别、分析等待、数据缺失和导出文案已统一优化。
- 仅改变展示层，不修改指标公式、角色分类、动作或优先级。

## 本次品线汇报优化

- 管理层摘要用文字汇报经营概况、P0/P1 风险、增长机会和数据边界，放在所有明细表之前。
- 原有五条品线经营结论保留为“经营结论展开”，用于补充口径和事实。
- ToDo 摘要用文字汇报任务总量、P0/P1 数量、优先级分布、负责人、最近完成时间和前三项执行重点。
- 可编辑 ToDo 表继续作为执行明细，字段和生成逻辑不变。

## 本轮发布验收

- 动作模块恢复且规则不变：通过。
- 应用导入与服务健康检查：通过。
- 全量 47 个测试：通过。
- Fang 诊断不改写 `sku_role`、`final_action`、`priority`：测试覆盖并通过。
- 三级分类映射、完整 SKU 输出和跨维度联动：测试覆盖并通过。
- Excel 导出与 `git diff --check`：通过。

## 后续候选任务

准备一份可提交的脱敏样例 Excel，对管理层摘要、ToDo 摘要和完整上传路径做浏览器端到端验收；随后确认 ToDo 是仅会话编辑，还是需要纳入 Excel 导出或其他持久化。同时确认未跟踪 `fang_diagnosis/` 原型与当前品线诊断的关系。对应阶段见 `PLANS.md`。
