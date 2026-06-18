# AGENTS.md

本文件记录项目的长期协作规则。除非项目治理方式发生变化，否则应保持稳定。

## 项目边界

- 应用项目根目录是当前目录 `amazon-inventory-profit-analyzer/`，不是其外层 `New project/`。
- 当前目录自身是独立 Git 仓库；执行状态检查、提交、测试和发布时必须以本目录为工作目录。
- 不得用外层仓库的 `git status` 判断本项目的真实变更范围。

## 每轮工作前

1. 阅读 `AGENTS.md`、`HANDOFF.md`、`README.md`、`PLANS.md` 和任务相关的 `docs/` 文档。
2. 检查内层仓库的 `git status --short --branch`、`git diff`、`git log --oneline -10`。
3. 以当前代码和测试为事实来源；文档与代码冲突时，先记录冲突，不静默假设文档正确。
4. 保护用户已有的未提交改动，不覆盖、不回滚、不顺手整理无关文件。

## 实施规则

- 入口为 `app.py`，主分析管线为 `modules/pipeline.py`。
- 字段别名和数据类型维护在 `config/column_mapping.yaml`；业务阈值维护在 `config/thresholds.yaml`。
- 每个 SKU 只能有一个 `final_action`；`sku_role` 与 `final_action` 是不同维度，不得互相覆盖。
- 品线诊断是报告层，只读取已有分析结果，不得改写原始数据、`sku_role`、`final_action` 或系统 `priority`。
- 业务判断优先序默认为：周转 > 规模 > 毛利润 > 毛利率。现金流和库存红线优先于表面高毛利。
- 新增或修改业务规则时，同步更新测试和 `docs/business-rules.md`；字段变化同步更新 `docs/data-dictionary.md`。
- 重要架构或口径决定写入 `docs/decisions.md`，避免只留在提交信息或对话里。
- 每轮完成或暂停前更新 `HANDOFF.md`；中长期范围、阶段和验收标准变化时更新 `PLANS.md`。

## 验证规则

- 标准测试命令：`.venv/bin/python -m pytest -q`。
- 不使用当前环境中的 `.venv/bin/pytest` 作为唯一验证入口，因为其脚本入口可能缺少项目根目录导入路径。
- 最低交付检查：
  - `.venv/bin/python -c "import app"`
  - `.venv/bin/python -m pytest -q`
  - `git diff --check`
- 涉及页面交互时，还需启动 Streamlit 做浏览器冒烟测试。
- 涉及 Excel 导出时，至少验证 Sheet 名称、列顺序、百分比/金额格式及可打开性。

## 文档职责

- `README.md`：面向使用者的安装、输入、运行和输出说明。
- `AGENTS.md`：稳定的协作和工程规则。
- `HANDOFF.md`：当前工作区状态、阻塞、验证结果和明确下一步。
- `PLANS.md`：中长期阶段、优先级和验收标准。
- `docs/business-rules.md`：可审计的业务判断规则。
- `docs/data-dictionary.md`：标准字段、来源、口径和派生字段。
- `docs/decisions.md`：重要决策及其原因、影响和状态。
