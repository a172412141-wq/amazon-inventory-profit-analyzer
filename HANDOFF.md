# HANDOFF.md

最后更新：2026-07-08（Asia/Shanghai）

## 当前目标

继续完善 Amazon 库存利润分析器。本次完成最高优先级缺口 `FANG_REL_008`：广告样本不足时降低 Fang 报告结论的确定性和优先级，同时保留现有系统动作、数据结构和角色判断。

## 仓库状态

- 项目仓库：当前目录 `amazon-inventory-profit-analyzer/`。
- 当前分支：`codex/fix-fang-data-credibility`，已推送并创建草稿 PR #1；当前 HEAD 为 `1f5e444 Add narrative product line reporting`。
- 目标发布分支：`main`。
- 外层 `New project/` 还有一个独立旧仓库；它不是本项目提交和状态判断的依据。

当前未提交工作区包含此前规则治理文档和本次 `FANG_REL_008` 实现：

- `docs/fang-rule-mapping.md`：新增 Fang 规则映射、阈值审计、原型合并决定和逐规则合并门槛。
- `docs/decisions.md`：D-010 确认生产入口唯一、原型按规则吸收；D-011 记录广告样本不足只降级 Fang 报告。
- `modules/product_line_diagnosis.py`：读取广告花费和点击样本，按暂定门槛降级广告关系诊断。
- `app.py`：把生产阈值传入品线诊断。
- `config/thresholds.yaml`：新增广告可靠样本暂定门槛，默认花费 20、点击 20。
- `tests/test_product_line_diagnosis.py`：新增低花费、低点击、缺点击和等于门槛的边界测试。
- `README.md`、`docs/business-rules.md`、`PLANS.md`、`HANDOFF.md`：同步行为边界、状态和下一步。

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
- `.venv/bin/python -m pytest -q -p no:cacheprovider`：原生运行 51 个测试，全部通过。
- `tests/test_product_line_diagnosis.py`：12 个定向测试全部通过；覆盖数据可信度、管理层摘要、ToDo 摘要、`FANG_REL_008` 样本边界和报告层不改写系统判断。
- Excel 11 Sheet 内存导出冒烟：通过。
- Streamlit 本地启动成功，`/_stcore/health` 返回 `ok`。
- 浏览器复核上传首页：应用正常启动，标题、上传区和使用说明正常显示，控制台无错误。因仓库无样例 Excel，本次未通过浏览器进入品线汇报页。
- `git diff --check` 通过。

## 剩余风险

1. `st.data_editor` 的返回值尚未接收；ToDo 可在页面编辑，但没有明确的持久化或 Excel 导出闭环。
2. 尚无可提交的输入样例文件用于端到端上传验证；`output/reports/` 中只有被忽略的历史冒烟输出。
3. 未跟踪的 `fang_diagnosis/` 仍没有统一入口和测试；已决定不整体接入，只能按映射清单逐规则迁移，在迁移完成前不得删除或作为第二套引擎运行。
4. `FANG_REL_008` 的花费 20、点击 20 来自设计原型，规范原文没有量化该阈值；在至少三个不同案例验证前必须保持 provisional。

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

## 本次 Fang 规则治理

- 已对用户提供的 DOCX 原文件重新计算 SHA-256：`5f793dfc0a77a6c8e4d3d06f51b84e94e50887373282edf92e439021672315bf`，与记录一致。
- `modules/product_line_diagnosis.py::build_product_line_diagnosis` 保持为唯一生产入口。
- 未跟踪原型不整体提交或接入，先吸收规则 ID、版本、来源和证据结构，再逐条迁移校验与关系规则。
- 原型中没有案例记录的数值阈值不得标为稳定，也不得覆盖 `config/thresholds.yaml`。
- 完整规则状态和缺口见 `docs/fang-rule-mapping.md`，架构决定见 `docs/decisions.md` D-010。

## 本次 FANG_REL_008 实现

- 品线广告花费 `< 20`、广告点击 `< 20` 或点击字段缺失时，广告关系结论降为“待验证假设”、P3、“待验证”。
- 花费和点击均 `>= 20` 时，保留原有广告-销售-利润关系判断；等于门槛的边界已有测试。
- 门槛进入生产 `config/thresholds.yaml`，但按 provisional 使用，不从原型配置自动加载。
- 系统 `final_action`、系统 `priority`、SKU 角色和输入 DataFrame 均保持不变；`modules/recommendations.py` 未修改。

## 本轮发布验收

- 动作模块恢复且规则不变：通过。
- 应用导入与服务健康检查：通过。
- 全量 51 个测试：通过。
- Fang 诊断不改写 `sku_role`、`final_action`、`priority`：测试覆盖并通过。
- 三级分类映射、完整 SKU 输出和跨维度联动：测试覆盖并通过。
- Excel 导出与 `git diff --check`：通过。


## 本轮 7/14 天周期与品线卡片优化

- 侧边栏新增快速周期切换，默认 7 天，可切换 14 天。
- 总览、父体、SPU、品线汇总和 Fang 品线诊断均接入同一个周期口径；整体 ACOAS 按筛选后广告花费 / 当前周期总销售额计算。
- SPU / 品线页在未启用筛选时，为每条品线直接展示经营卡片，包含核心经营结果、库存与现金流、当前行动队列和数据。
- 页面周期只影响展示、聚合和报告口径，不改写 SKU 角色、系统 final_action 或系统 priority。

## 后续候选任务

优先建立最小规则执行快照：规则 ID、版本、阈值值、阈值状态、输入字段、是否命中和降级原因；随后为 `FANG_REL_009` 增加广告字段冲突时阻断确定性报告建议的测试。对应映射见 `docs/fang-rule-mapping.md`。
