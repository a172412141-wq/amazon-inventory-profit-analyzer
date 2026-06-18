# HANDOFF.md

最后更新：2026-06-18（Asia/Shanghai）

## 当前目标

继续完善 Amazon 库存利润分析器。本轮发布筛选器业务显示名称更新；底层字段、筛选 key 和串联逻辑保持不变。

## 仓库状态

- 项目仓库：当前目录 `amazon-inventory-profit-analyzer/`。
- 发布分支：`main`；发布前基线为 `3475942 Add product line diagnosis report`。
- 外层 `New project/` 还有一个独立旧仓库；它不是本项目提交和状态判断的依据。

当前业务代码工作区变更：

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
- `.venv/bin/python -m pytest -q`：原生运行 44 个测试，全部通过；包含三级分类字段映射、输出保留、联动筛选和业务显示名称回归测试。
- Excel 11 Sheet 内存导出冒烟：通过。
- Streamlit 本地启动成功，`/_stcore/health` 返回 `ok`。
- `git diff --check` 通过。

## 剩余风险

1. 品线数据可信度目前直接检查清洗后的列；某些原始缺失字段会在清洗时补为 0，可能被误判为完整。
2. `st.data_editor` 的返回值尚未接收；ToDo 可在页面编辑，但没有明确的持久化或 Excel 导出闭环。
3. 尚无可提交的输入样例文件用于端到端上传验证；`output/reports/` 中只有被忽略的历史冒烟输出。

## 本轮筛选器命名发布

- 筛选器显示名更新为：父ASIN、品线、尺寸、SKU角色定位、处理优先级、库存天数情况、毛利率水平、周转水平、现金流风险。
- 底层字段名、筛选 key 和串联逻辑保持不变。

## 本轮发布验收

- 动作模块恢复且规则不变：通过。
- 应用导入与服务健康检查：通过。
- 全量 44 个测试：通过。
- Fang 诊断不改写 `sku_role`、`final_action`、`priority`：测试覆盖并通过。
- 三级分类映射、完整 SKU 输出和跨维度联动：测试覆盖并通过。
- Excel 导出与 `git diff --check`：通过。

## 后续候选任务

修正数据可信度对原始缺失字段的识别，并决定 ToDo 是仅会话编辑，还是需要纳入导出或持久化。对应阶段见 `PLANS.md`。
