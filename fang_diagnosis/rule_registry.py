from __future__ import annotations

from .types import RuleRecord


VERSION = "FANG_DIAGNOSIS_V0_1"
SOURCE = "Fang经营关系诊断模型_V0.1（用户提供规范；DOCX待复核）"


RULES = [
    RuleRecord("FANG_DATA_001", "跨时间窗口校验", VERSION, "stable", SOURCE, "销售、广告、利润与库存窗口必须可比较。", ["metadata"], "data_issue"),
    RuleRecord("FANG_DATA_002", "利润口径一致性", VERSION, "stable", SOURCE, "毛利润除以销售额应与毛利率在容差内一致。", ["sales.salesAmount14d", "profitability.grossProfit", "profitability.grossMargin"], "data_issue"),
    RuleRecord("FANG_DATA_003", "广告字段一致性", VERSION, "stable", SOURCE, "广告订单、销售额、点击、转化率和成本比必须自洽。", ["advertising"], "data_issue"),
    RuleRecord("FANG_DATA_004", "库存口径一致性", VERSION, "stable", SOURCE, "库存天数、库龄数量与库存占比必须自洽。", ["inventory", "sales.currentDailyUnits"], "data_issue"),
    RuleRecord("FANG_STAGE_001", "经营阶段识别", VERSION, "provisional", SOURCE, "使用周转、利润、角色结构和增长确定性联合识别阶段。", ["inventory", "profitability", "sales", "skuRoles"], "lifecycle"),
    RuleRecord("FANG_REL_001", "高毛利低销量高库存", VERSION, "stable", SOURCE, "账面利润空间未转化为现金贡献。", ["skuDetails"], "relationship_finding"),
    RuleRecord("FANG_REL_002", "广告未形成增量", VERSION, "experimental", SOURCE, "高广告投入未形成自然销量增长。", ["advertising", "sales"], "relationship_finding"),
    RuleRecord("FANG_REL_003", "高库存缺乏消化依据", VERSION, "stable", SOURCE, "高库存且缺少目标速度或流量价格计划。", ["inventory", "sales.targetDailyUnits"], "relationship_finding"),
    RuleRecord("FANG_REL_004", "高销量负毛利润", VERSION, "stable", SOURCE, "规模正在放大亏损。", ["sales", "profitability"], "relationship_finding"),
    RuleRecord("FANG_REL_005", "流量无承接", VERSION, "stable", SOURCE, "有引流SKU但无主力与利润SKU。", ["skuRoles"], "relationship_finding"),
    RuleRecord("FANG_REL_006", "低效资源错配", VERSION, "provisional", SOURCE, "低效SKU占比高但广告或库存仍持续投入。", ["skuRoles", "advertising", "inventory"], "relationship_finding"),
    RuleRecord("FANG_REL_007", "周转目标不可达", VERSION, "stable", SOURCE, "当前速度显著低于目标且库存天数高。", ["sales", "inventory"], "relationship_finding"),
    RuleRecord("FANG_REL_008", "广告样本不足", VERSION, "stable", SOURCE, "绝对花费或点击不足时不得把ACoS作为核心矛盾。", ["advertising"], "relationship_finding"),
    RuleRecord("FANG_REL_009", "广告数据冲突", VERSION, "stable", SOURCE, "广告字段冲突时不得直接用于确定性经营决策。", ["advertising"], "relationship_finding"),
    RuleRecord("FANG_REL_010", "180天库存优先", VERSION, "stable", SOURCE, "91-180天为0不能掩盖更严重的180天以上库存。", ["inventory.inventory91to180", "inventory.inventory180Plus"], "relationship_finding"),
    RuleRecord("FANG_ROLE_001", "SKU角色与状态分离", VERSION, "stable", SOURCE, "保留互斥角色并叠加风险或机会状态。", ["skuDetails"], "sku_structure"),
    RuleRecord("FANG_ACTION_001", "可验收行动计划", VERSION, "stable", SOURCE, "行动必须包含对象、期限、验收标准和失败预案。", ["relationshipFindings"], "action_plan"),
]


def enabled_rules() -> list[RuleRecord]:
    return [rule for rule in RULES if rule.enabled]


def rule_map() -> dict[str, RuleRecord]:
    return {rule.rule_id: rule for rule in RULES}

