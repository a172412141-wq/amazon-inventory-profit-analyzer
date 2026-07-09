from __future__ import annotations

from typing import Any

from .config import threshold
from .metric_normalizer import normalize_percentage, safe_divide, safe_number
from .types import DataIssue, DiagnosisInput, ValidationResult


def validate_input(data: DiagnosisInput, config: dict[str, Any]) -> ValidationResult:
    issues: list[DataIssue] = []
    blocked: set[str] = set()
    metadata = data.get("metadata", {})
    sales = data.get("sales", {})
    advertising = data.get("advertising", {})
    profitability = data.get("profitability", {})
    inventory = data.get("inventory", {})
    scope = data.get("scope", {})

    periods = {
        name: safe_number(metadata.get(name))
        for name in ["salesPeriodDays", "advertisingPeriodDays", "profitPeriodDays"]
        if metadata.get(name) is not None
    }
    if len(set(periods.values())) > 1:
        issues.append(DataIssue("TIME_WINDOW_MISMATCH", "error", "metadata", "销售、广告和利润使用了不同时间窗口。"))
        blocked.update({"advertising", "profitability"})
    elif len(periods) < 3:
        issues.append(DataIssue("TIME_WINDOW_UNCONFIRMED", "warning", "metadata", "销售、广告和利润时间窗口未全部提供，跨模块因果只能标记为待验证。"))

    sales_amount = safe_number(sales.get("salesAmount14d"))
    gross_profit = safe_number(profitability.get("grossProfit"))
    gross_margin = normalize_percentage(profitability.get("grossMargin"))
    expected_margin = safe_divide(gross_profit, sales_amount)
    margin_tolerance = threshold(config, ("profitability", "margin_conflict_tolerance")) or 0
    if expected_margin is not None and gross_margin is not None and abs(expected_margin - gross_margin) > margin_tolerance:
        issues.append(
            DataIssue(
                "GROSS_PROFIT_MARGIN_MISMATCH",
                "error",
                "profitability.grossMargin",
                "毛利润与毛利率数学口径不一致，禁止直接用毛利率归因。",
                expected=expected_margin,
                actual=gross_margin,
            )
        )
        blocked.add("profitability.grossMargin")

    spend = safe_number(advertising.get("spend"))
    ad_sales = safe_number(advertising.get("attributedSales"))
    ad_orders = safe_number(advertising.get("adOrders"))
    clicks = safe_number(advertising.get("clicks"))
    ctr = normalize_percentage(advertising.get("ctr"))
    cpc = safe_number(advertising.get("cpc"))
    ad_cvr = normalize_percentage(advertising.get("adCvr"))
    acos = normalize_percentage(advertising.get("acos"))
    tacoas = normalize_percentage(advertising.get("tacoas"))
    ratio_tolerance = threshold(config, ("advertising", "ratio_tolerance")) or 0

    if ad_sales is not None and ad_sales > 0 and (ad_orders is None or ad_orders == 0):
        issues.append(DataIssue("AD_SALES_WITHOUT_ORDERS", "error", "advertising.adOrders", "存在广告销售额但广告订单数为0，广告归因口径冲突。"))
        blocked.add("advertising")
    if spend is not None and spend > 0 and all(value is None or value == 0 for value in [clicks, ctr, cpc]):
        issues.append(DataIssue("AD_SPEND_WITHOUT_TRAFFIC_FIELDS", "error", "advertising", "存在广告花费，但点击、CTR和CPC全部为空或0。"))
        blocked.add("advertising")
    if ad_cvr == 0 and ((ad_orders or 0) > 0 or (ad_sales or 0) > 0):
        issues.append(DataIssue("AD_CVR_CONFLICT", "error", "advertising.adCvr", "广告CVR为0，但存在广告订单或广告销售额。"))
        blocked.add("advertising")

    expected_acos = safe_divide(spend, ad_sales)
    if expected_acos is not None and acos is not None and abs(expected_acos - acos) > ratio_tolerance:
        issues.append(DataIssue("ACOS_MISMATCH", "error", "advertising.acos", "ACoS与广告花费/广告销售额不一致。", expected_acos, acos))
        blocked.add("advertising.acos")
    expected_tacoas = safe_divide(spend, sales_amount)
    if expected_tacoas is not None and tacoas is not None and abs(expected_tacoas - tacoas) > ratio_tolerance:
        issues.append(DataIssue("TACOAS_MISMATCH", "error", "advertising.tacoas", "TACoS与广告花费/总销售额不一致。", expected_tacoas, tacoas))
        blocked.add("advertising.tacoas")

    count_90 = safe_number(inventory.get("inventory90PlusCount"))
    age_91_180 = safe_number(inventory.get("inventory91to180"))
    age_180 = safe_number(inventory.get("inventory180Plus"))
    count_tolerance = threshold(config, ("validation", "count_tolerance")) or 0
    age_sum = None if age_91_180 is None and age_180 is None else (age_91_180 or 0) + (age_180 or 0)
    if count_90 is not None and age_sum is not None and abs(count_90 - age_sum) > count_tolerance:
        issues.append(DataIssue("AGED_INVENTORY_COUNT_MISMATCH", "error", "inventory.inventory90PlusCount", "90天以上库存数量与91-180天及180天以上分段合计不一致。", age_sum, count_90))
        blocked.add("inventory.inventory90PlusCount")

    total_inventory = safe_number(inventory.get("totalInventory"))
    share_90 = normalize_percentage(inventory.get("inventory90PlusShare"))
    expected_share = safe_divide(count_90, total_inventory)
    if expected_share is not None and share_90 is not None and abs(expected_share - share_90) > ratio_tolerance:
        issues.append(DataIssue("AGED_INVENTORY_SHARE_MISMATCH", "error", "inventory.inventory90PlusShare", "90天以上库存占比与数量/总库存不一致。", expected_share, share_90))
        blocked.add("inventory.inventory90PlusShare")

    available_inventory = safe_number(inventory.get("availableInventory"))
    daily_units = safe_number(sales.get("currentDailyUnits"))
    available_days = safe_number(inventory.get("availableDays"))
    expected_days = safe_divide(available_inventory, daily_units)
    rel_tolerance = threshold(config, ("validation", "inventory_days_relative_tolerance")) or 0
    abs_tolerance = threshold(config, ("validation", "inventory_days_absolute_tolerance")) or 0
    if expected_days is not None and available_days is not None:
        allowed = max(abs_tolerance, abs(expected_days) * rel_tolerance)
        if abs(expected_days - available_days) > allowed:
            issues.append(DataIssue("AVAILABLE_DAYS_MISMATCH", "error", "inventory.availableDays", "可售库存天数与可售库存/当前日销量明显不一致。", expected_days, available_days))
            blocked.add("inventory.availableDays")

    source_presence = data.get("sourcePresence", {})
    zero_sensitive = {
        "ad_clicks": advertising.get("clicks"),
        "ad_orders": advertising.get("adOrders"),
        "sales_14d_amount": sales.get("salesAmount14d"),
        "available_qty": inventory.get("availableInventory"),
    }
    for field, value in zero_sensitive.items():
        if source_presence and source_presence.get(field) is False and safe_number(value) == 0:
            issues.append(DataIssue("MISSING_VALUE_COERCED_TO_ZERO", "warning", field, f"{field} 原始字段缺失，但当前值为0；不得把0当作已确认事实。"))

    currency = metadata.get("currency")
    if currency is None:
        issues.append(DataIssue("CURRENCY_UNCONFIRMED", "info", "metadata.currency", "币种未提供，金额可用于同表比较，但不应跨市场直接比较。"))
    elif not isinstance(currency, str) or len(currency.strip()) != 3:
        issues.append(DataIssue("CURRENCY_INVALID", "warning", "metadata.currency", "币种应使用三位代码，例如USD。"))

    expected_sku_count = int(safe_number(scope.get("skuCount")) or 0)
    actual_sku_count = len(data.get("skuDetails", []))
    if expected_sku_count != actual_sku_count:
        issues.append(DataIssue("SKU_COUNT_MISMATCH", "error", "scope.skuCount", "SKU数量与SKU明细数量不一致。", float(expected_sku_count), float(actual_sku_count)))
        blocked.add("skuDetails")

    errors = sum(issue.severity == "error" for issue in issues)
    warnings = sum(issue.severity == "warning" for issue in issues)
    confidence = "low" if errors else ("medium" if warnings else "high")
    return ValidationResult(is_valid=errors == 0, confidence=confidence, issues=issues, blocked_fields=blocked)

