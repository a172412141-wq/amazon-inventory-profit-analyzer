# Fang 规则映射清单

最后核对：2026-06-18（Asia/Shanghai）

## 目的与事实来源

本文件把《Fang经营关系诊断模型 V0.1》的规范要求映射到当前生产代码、配置阈值和测试案例，用于判断规则是否可审计、是否具备合并条件，以及未跟踪 `fang_diagnosis/` 原型应如何处理。

- 规范来源：`Fang经营关系诊断模型_V0.1.docx`
- 来源文件 SHA-256：`5f793dfc0a77a6c8e4d3d06f51b84e94e50887373282edf92e439021672315bf`
- 生产入口：`modules/product_line_diagnosis.py::build_product_line_diagnosis`
- 系统动作入口：`modules/recommendations.py::recommend_action`
- SKU 角色入口：`modules/sku_roles.py::classify_sku_roles`
- 生产阈值：`config/thresholds.yaml`
- 未跟踪原型阈值：`config/fang_diagnosis.yaml`
- 未跟踪原型规则表：`fang_diagnosis/rule_registry.py`

状态定义：

- **已覆盖**：生产代码已实现且有直接回归测试。
- **部分覆盖**：生产代码只实现部分语义，或测试不足。
- **原型覆盖**：仅未跟踪原型存在，未进入生产管线。
- **未实现**：生产代码和原型都没有完整实现。

## 规则映射

| 规则 ID | 文档规则 | 当前生产代码 | 配置阈值 | 直接测试 | 状态与缺口 |
|---|---|---|---|---|---|
| `FANG_PRIORITY_001` | 默认经营优先序为周转 > 规模 > 毛利润 > 毛利率，且不能机械套用 | `product_line_diagnosis.py::BUSINESS_PRIORITY_ORDER`、`_relationship_diagnostics`、`_product_line_todo_list` | 无独立阈值 | `test_product_line_todo_contains_complete_action_fields_and_preserves_system_actions` | **已覆盖**；优先顺序已用于报告和 ToDo 排序，系统 `final_action` 仍由独立动作规则决定 |
| `FANG_DATA_001` | 销售、广告、库存、利润必须使用可比较的时间窗口 | 生产报告固定输出“销售与广告时间窗口待确认”，但没有时间窗口输入 | 原型无数值阈值；依赖 `metadata` | `test_product_line_diagnosis_outputs_data_credibility_and_cause_levels` | **部分覆盖**；原型 `data_validator.py` 可识别窗口冲突，但尚未接入；生产输入缺少起止日期和归因周期 |
| `FANG_DATA_002` | 毛利润、销售额和毛利率必须数学自洽；利润成本范围需确认 | 生产聚合毛利率按利润额/销售额计算；数据质量只检查异常毛利率，没有逐行利润率交叉校验 | 原型 `margin_conflict_tolerance=0.03`，标记为 provisional | `test_product_line_margin_uses_profit_sum_divided_by_sales_sum` | **部分覆盖**；原型有交叉校验，生产缺少冲突测试与成本包含项输入 |
| `FANG_DATA_003` | 广告花费、销售额、订单、点击、CVR、ACOS/ACOAS 必须自洽 | `metrics.py::calculate_metrics`、`validation.py::validate_data` | 生产 `ads.acos_warning_ratio`；原型 `ratio_tolerance=0.05` | `test_ad_and_inventory_metrics_are_calculated`、`test_validation_reports_inventory_mismatches_without_margin_period_guess` | **部分覆盖**；基础公式和明显异常已覆盖，广告订单/CVR/归因窗口冲突仅原型覆盖 |
| `FANG_DATA_004` | 库存数量、库存天数、库龄和销量口径必须自洽 | `validation.py::validate_data`、`metrics.py::calculate_metrics` | 生产库存阈值；原型相对容差 20%、绝对容差 30 天、数量容差 1 | `test_validation_reports_inventory_mismatches_without_margin_period_guess`、库龄指标测试 | **已覆盖**基础口径；原型的所有分段交叉校验尚未进入生产 |
| `FANG_DATA_005` | 缺失值不得被当作真实 0 | `cleaning.py` 生成 `_missing_*`；`product_line_diagnosis.py::_field_presence` 使用缺失标记 | 无 | `test_data_credibility_excludes_zero_filled_missing_values_but_keeps_real_zeroes` | **已覆盖** |
| `FANG_CAUSE_001` | 必须区分已确认原因、高概率原因、待验证假设、无法判断 | `_cause_level_for_sku`、`_relationship_diagnostics` | 多个判断阈值仍硬编码 | `test_product_line_diagnosis_outputs_data_credibility_and_cause_levels` | **已覆盖**输出枚举；各等级的证据最低要求尚未逐规则测试 |
| `FANG_COMPARE_001` | SKU 至少比较同父体、同品线、同规格、相近价格带和自身历史 | `_parent_compare`、`_line_compare`、`_peer_compare`；历史仅输出缺失提示 | 价格带为均价 ±10%，同尺寸/价格带最少 3 个样本，当前硬编码 | `test_product_line_diagnosis_marks_low_confidence_when_peer_samples_are_missing` | **部分覆盖**；父体、品线、尺寸、价格带已实现，自身历史没有输入；缺少具体比较边界测试 |
| `FANG_ROLE_001` | 角色尽量互斥，风险/机会状态可以叠加 | `sku_roles.py::classify_sku_roles`、`product_line_diagnosis.py::_role_status` | `traffic_ad_spend_share=0.35`、`profit_margin_multiplier=1.50` | `test_sku_roles_are_parent_relative_and_mutually_exclusive` 等 SKU 角色测试 | **已覆盖**角色互斥和角色履职状态；利润 SKU 仅用毛利率倍数，未覆盖文档所述“单位利润显著高” |
| `FANG_STAGE_001` | 结合目标、周转、利润、角色结构和增长确定性判断经营阶段 | 生产报告没有经营阶段字段 | 原型库存/利润/角色阈值 | 无 | **原型覆盖**；`lifecycle_classifier.py` 未接入且无测试 |
| `FANG_REL_001` | 高毛利、低销量、高库存说明账面空间未转化为现金贡献 | `_relationship_diagnostics` 的毛利率-周转关系、系统慢周转动作 | 生产 `high_margin=0.15`、库存 90/180 天 | 高毛利慢周转动作测试 | **部分覆盖**；有生产行为测试，缺少对应关系诊断文本和证据等级测试 |
| `FANG_REL_002` | 广告投入未形成自然销量增量时，不应直接继续放大 | 生产没有自然销量增长或广告增量字段 | 原型最低广告花费 20，provisional | 无 | **原型覆盖**；原型依赖 `metadata.naturalSalesGrowth`，当前数据管线不提供 |
| `FANG_REL_003` | 高库存必须有目标销量、流量、价格或活动计划支撑 | 生产诊断会提示缺少消化依据并生成验证动作 | 生产理想周转 90 天；原型严重库存 180 天 | 库存红线动作测试；无计划输入测试 | **部分覆盖**；能指出缺口，但无法读取或验证经营计划 |
| `FANG_REL_004` | 有规模但毛利润为负，规模正在放大亏损 | `_relationship_diagnostics` 的规模-毛利润关系、`recommend_action` 负毛利润保护 | `negative_profit=0` 为固定数学边界 | `test_negative_gross_profit_with_replenishment_pauses_replenishment`、品线诊断测试数据 | **已覆盖**核心行为；缺少独立关系规则测试 |
| `FANG_REL_005` | 有引流 SKU 但无主力和利润 SKU，流量没有形成承接 | 生产角色结构可显示该事实，但没有独立关系规则 | 无 | 无 | **原型覆盖**；`contradiction_detector.py` 已定义但未接入、无测试 |
| `FANG_REL_006` | 低效 SKU 占比高且仍占广告或库存，属于资源错配 | 生产逐 SKU 判断角色失效和广告错配，没有品线低效占比规则 | 原型 `inefficient_share_warning=0.50`，provisional | SKU 角色分区测试、广告错配测试 | **部分覆盖**；缺少品线级占比规则与边界测试 |
| `FANG_REL_007` | 当前销量显著低于目标且库存高，说明周转目标不可达 | 生产计算目标日销量并输出库存动作，但没有显式“达成率”关系规则 | 原型 `target_gap_ratio=0.75`，provisional | `test_ad_and_inventory_metrics_are_calculated`、库存动作测试 | **部分覆盖**；原型 `sales_analyzer.py` 已实现达成率，未接入、无测试 |
| `FANG_REL_008` | 广告绝对样本不足时，不得把高 ACOS/ACOAS 定义为核心矛盾 | `product_line_diagnosis.py::_relationship_diagnostics`；只降低 Fang 报告结论，不改系统动作 | 生产 `ads.minimum_spend_for_reliable_acos=20`、`ads.minimum_clicks_for_reliable_cvr=20`，均按 provisional 使用 | `test_fang_rel_008_downgrades_ad_diagnosis_when_sample_is_insufficient`、`test_fang_rel_008_keeps_ad_diagnosis_when_sample_reaches_boundary` | **已覆盖报告层**；覆盖低花费、低点击、缺点击和等于门槛边界，系统“控广告”逻辑保持不变 |
| `FANG_REL_009` | 广告字段冲突时禁止确定性停投或扩量 | 数据质量页可报告部分广告异常；Fang 报告未消费数据异常结果来阻断建议 | 原型容差 5% | 无直接阻断测试 | **部分覆盖**；当前只是并列展示，不会系统性降级不可逆动作 |
| `FANG_REL_010` | 91-180 天库存为 0 不能掩盖 180 天以上库存 | 生产动作优先处理 180 天以上库存；品线关系诊断统计 180 天以上 SKU | 生产 `urgent_redline_days=180` | `test_stock_days_above_180_clears_inventory` | **已覆盖** |
| `FANG_PRICE_001` | 调价必须明确目标、使用实验 SKU/对照并同时观察销量、利润和效率 | 生产仅有价格带比较和通用价格建议 | 原型仅有 `price_test_days=7`，provisional | 无 | **未实现**完整价格实验 |
| `FANG_ACTIVITY_001` | 活动必须验证增量、利润和活动后留存 | 生产仅把活动作为建议或缺失信息 | 无 | 无 | **未实现** |
| `FANG_EXPERIMENT_001` | 证据不足时采用有假设、对照、窗口、成功标准和停止条件的局部实验 | ToDo 有观察周期、成功标准和失败预案，但没有实验/对照数据结构 | 生产截止日硬编码 2/7/14/30 天；原型配置为 provisional | ToDo 完整字段测试 | **部分覆盖**；需要实验对象、对照对象、基准期和结果记录 |
| `FANG_ACTION_001` | 行动必须包含对象、问题、证据、影响、动作、负责人、时间、观察周期、成功标准和失败预案 | `_product_line_todo_list` | 截止日目前硬编码；原型配置存在但未使用 | `test_product_line_todo_contains_complete_action_fields_and_preserves_system_actions` | **已覆盖**字段完整度；编辑结果尚未持久化或导出 |
| `FANG_REPORT_001` | 输出必须能用于汇报，而不是只给表格或空泛建议 | `_executive_summary`、`_todo_summary`、页面“先汇报、后明细” | 无 | `test_product_line_diagnosis_provides_management_and_todo_narratives` | **已覆盖**当前品线报告层 |
| `FANG_VERSION_001` | 新规则记录来源；3 个不同案例验证后才能升级为稳定原则；冲突增加适用边界 | 生产报告没有规则版本或执行快照 | 原型 `RuleRecord.status` 和阈值状态存在，但多个 `stable` 没有案例记录 | 无 | **原型覆盖结构、未覆盖治理闭环** |

## 阈值审计结论

1. `config/thresholds.yaml` 是现有生产动作和 SKU 角色的阈值来源，不因 Fang V0.1 文档自动失效。
2. `config/fang_diagnosis.yaml` 中除数学恒等边界外的数值，不能仅凭 V0.1 文档标记为 `stable`；文档明确说明阈值尚未量化且稳定原则需要至少 3 个案例验证。
3. 原型阈值在接入前必须补充 `source`、`case_count`、`last_validated_at` 和对应测试；未满足时统一视为 provisional 或 experimental。
4. 生产代码仍有未配置的硬编码，例如品线集中度 60%/80%、价格带 ±10%、同行样本至少 3、广告错配 10%/15%、ToDo 截止日 2/7/14/30 天。是否配置化应逐条判断，不能机械搬入 YAML。
5. `FANG_REL_008` 的花费 20、点击 20 已进入生产配置，但规范原文没有给出这两个数值；在案例验证完成前仍是 provisional，只用于 Fang 报告降级。

## 未跟踪原型合并决定

### 决定

当前生产入口继续使用 `modules/product_line_diagnosis.py::build_product_line_diagnosis`。未跟踪 `fang_diagnosis/` 不作为第二套运行引擎整体接入，也不直接删除；将其视为规则治理与证据模型的设计原型，按规则逐步吸收。

### 原因

- 生产实现已有页面、报告、ToDo 和 12 个直接测试，能够稳定运行。
- 原型在规则 ID、证据结构、数据输入规范、阈值状态和生命周期方面更强。
- 原型没有统一 `diagnose()` 入口，没有构造 `DiagnosisReport` 或 `ActionItem`，没有测试，也没有接入 Streamlit、导出和现有 `final_action`。
- 整体替换会形成第二套业务判断并带来规则漂移，违反报告层不得覆盖系统动作和优先级的约束。

### 合并阶段

1. **规则治理层**：先吸收 `RuleRecord`、规则 ID、版本和来源字段；修正“DOCX待复核”和未经案例验证的 `stable` 状态。
2. **证据层**：为现有生产诊断结果附加规则 ID、输入字段、公式、阈值、比较对象和证据强度，不改变现有中文结论。
3. **数据校验层**：逐条迁移原型的时间窗口、利润、广告和库存交叉校验；每迁移一条先补生产回归测试。
4. **关系规则层**：优先补 `FANG_REL_005`、`FANG_REL_008`、`FANG_REL_009`，因为它们是当前明确缺口或与现有动作存在潜在冲突的规则。
5. **阶段与实验层**：最后评估经营阶段、价格实验、活动实验和行动结果记录；没有历史与实验输入前不输出确定性结论。
6. **原型退场**：全部被采用的规则完成生产接入和测试后，删除重复原型文件；未采用规则记录废弃原因。

### 每条规则的合并门槛

- 有文档章节或业务案例来源。
- 有唯一规则 ID 和明确适用边界。
- 阈值状态与案例数量一致。
- 有正常、边界、缺失和冲突场景测试。
- 不改写 `sku_role`、`final_action` 或系统 `priority`。
- 能在报告中显示规则版本、证据和降级原因。

## 下一批建议任务

1. 建立最小规则执行快照：规则 ID、版本、阈值值、阈值状态、输入字段和是否命中。
2. 为 `FANG_REL_009` 建立广告字段冲突时的报告阻断测试，避免口径冲突仍输出确定性投放建议。
3. 为时间窗口增加显式输入，完成 `FANG_DATA_001`，避免永远输出“待确认”。
