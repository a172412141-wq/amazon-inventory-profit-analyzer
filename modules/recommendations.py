from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


PRIORITY_ORDER = ["P0", "P1", "P2", "P3", "P4"]
ACTION_ORDER = [
    "立即补货",
    "优先补货",
    "加大投入加速周转",
    "控补货促周转",
    "正常补货",
    "谨慎补货",
    "控广告",
    "暂缓补货",
    "禁止补货",
    "高毛利停补",
    "清货处理",
    "可加广告",
    "观察",
]


def _threshold(thresholds: dict[str, Any] | None, path: tuple[str, ...], default: float) -> float:
    current: Any = thresholds or {}
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return float(current)


def _num(row: pd.Series, column: str, default: float = np.nan) -> float:
    value = row.get(column, default)
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_true(value: Any) -> bool:
    return bool(value) if not pd.isna(value) else False


def _decision(final_action: str, priority: str, reason: str) -> dict[str, str]:
    return {"final_action": final_action, "priority": priority, "reason": reason}


def recommend_action(row: pd.Series, thresholds: dict[str, Any] | None = None) -> dict[str, str]:
    stock_days = _num(row, "stock_days", 0)
    main_daily_sales = _num(row, "main_daily_sales", 0)
    total_supply_qty = _num(row, "total_supply_qty", 0)
    recommended_qty = _num(row, "recommended_replenishment_qty", 0)
    margin = _num(row, "order_gross_margin")
    profit_after_ads_margin = _num(row, "profit_after_ads_margin")
    ad_spend = _num(row, "ad_spend", 0)
    ad_sales = _num(row, "ad_sales", 0)
    acos = _num(row, "acos")
    aged_inventory = _num(row, "aged_inventory_181_plus", 0)
    inbound_qty = _num(row, "inbound_qty", 0)
    trend = str(row.get("recent_sales_trend", ""))

    high_margin = _threshold(thresholds, ("margin", "high_margin"), 0.30)
    severe_stockout_days = _threshold(thresholds, ("inventory", "severe_stockout_days"), 14)
    stockout_warning_days = _threshold(thresholds, ("inventory", "stockout_warning_days"), 30)
    healthy_max_days = _threshold(thresholds, ("inventory", "healthy_max_days"), 120)
    overstock_days = _threshold(thresholds, ("inventory", "overstock_days"), 180)
    clearance_days = _threshold(thresholds, ("inventory", "clearance_days"), 270)
    slow_min = _threshold(thresholds, ("cashflow", "high_margin_slow_turnover_min_days"), 60)

    ad_is_severe = (
        (ad_spend > 0 and ad_sales <= 0)
        or (not pd.isna(acos) and not pd.isna(margin) and acos >= margin)
        or (not pd.isna(profit_after_ads_margin) and profit_after_ads_margin < 0)
    )

    # 1. 严重清货 / 禁止补货
    if (
        stock_days > clearance_days
        or (main_daily_sales <= 0 and total_supply_qty > 0)
        or (stock_days > overstock_days and not pd.isna(margin) and margin <= 0)
        or (stock_days > overstock_days and not pd.isna(profit_after_ads_margin) and profit_after_ads_margin < 0)
    ):
        return _decision(
            "清货处理",
            "P1",
            "库存天数过高 / 无销量压货 / 毛利为负 / 广告后亏损，现金流风险高，建议清货并停止补货。",
        )

    # High-margin overstock is a special stop-replenishment action. Keeping it
    # ahead of the generic prohibition preserves the requested dedicated label.
    if not pd.isna(margin) and margin >= high_margin and stock_days > overstock_days:
        return _decision(
            "高毛利停补",
            "P2",
            "虽然毛利率高，但库存周转过慢，现金流风险高，禁止继续补货。",
        )

    # 2. 禁止补货
    if (
        stock_days > overstock_days
        or (aged_inventory > 0 and stock_days > healthy_max_days)
        or (inbound_qty > 0 and stock_days > healthy_max_days)
        or (not pd.isna(margin) and margin <= 0 and stock_days > 90)
    ):
        return _decision("禁止补货", "P2", "库存或在途压力较大，继续补货会恶化现金流。")

    # 3. 毛利为负 / 暂缓补货
    if not pd.isna(margin) and margin <= 0 and recommended_qty > 0:
        return _decision("暂缓补货", "P2", "虽有补货建议，但毛利率为负，不能继续放大亏损 SKU。")

    # 4. 广告严重异常 / 控广告
    if ad_is_severe:
        if stock_days < severe_stockout_days and recommended_qty > 0 and not pd.isna(margin) and margin > 0:
            return _decision(
                "立即补货",
                "P0",
                "可售天数低，存在严重缺货风险，且毛利为正，建议立即补货，同时控广告防断货。",
            )
        return _decision("控广告", "P2", "广告效率低于利润安全线，建议降低预算、暂停低效广告或重构投放。")

    # 5. 高毛利 + 良性偏慢周转
    if (
        not pd.isna(margin)
        and margin >= high_margin
        and slow_min <= stock_days <= healthy_max_days
        and main_daily_sales > 0
        and not pd.isna(profit_after_ads_margin)
        and profit_after_ads_margin >= 0
    ):
        return _decision(
            "加大投入加速周转",
            "P2",
            "毛利率较高，库存仍在良性可控区间，但周转偏慢。建议适度增加广告、优惠券或页面转化优化投入，把库存天数压回 45-90 天。",
        )

    # 6. 高毛利 + 慢周转
    if not pd.isna(margin) and margin >= high_margin and healthy_max_days < stock_days <= overstock_days and main_daily_sales > 0:
        return _decision(
            "控补货促周转",
            "P2",
            "毛利率较高，但库存周转偏慢，现金占用偏高。建议暂缓补货，通过有效广告和轻促销提升周转。",
        )

    # 8. 立即补货
    if stock_days < severe_stockout_days and recommended_qty > 0 and not pd.isna(margin) and margin > 0:
        return _decision(
            "立即补货",
            "P0",
            "可售天数低，存在严重缺货风险，且毛利为正，建议立即补货。若广告消耗较高，需同步控广告防断货。",
        )

    # 9. 优先补货
    if severe_stockout_days <= stock_days < stockout_warning_days and recommended_qty > 0 and not pd.isna(margin) and margin > 0:
        return _decision("优先补货", "P1", "可售天数低于安全范围，毛利为正，建议优先补货，广告不建议继续放大。")

    # 10. 正常补货
    if (
        recommended_qty > 0
        and stockout_warning_days <= stock_days <= healthy_max_days
        and not pd.isna(margin)
        and not pd.isna(acos)
        and margin > acos
        and not pd.isna(profit_after_ads_margin)
        and profit_after_ads_margin >= 0
    ):
        return _decision("正常补货", "P2", "库存处于可控范围，有补货需求，且广告和利润可覆盖，允许正常补货。")

    # 11. 谨慎补货
    if recommended_qty > 0 and not pd.isna(margin) and margin > 0:
        if (not pd.isna(acos) and acos >= margin) or (not pd.isna(profit_after_ads_margin) and profit_after_ads_margin < 0):
            return _decision("谨慎补货", "P2", "有补货建议，但广告或利润异常，建议先复核广告和利润后再补货。")

    # 12. 可加广告
    if (
        stockout_warning_days <= stock_days <= healthy_max_days
        and not pd.isna(margin)
        and not pd.isna(acos)
        and margin > acos
        and not pd.isna(profit_after_ads_margin)
        and profit_after_ads_margin > 0
        and trend in {"销量稳定", "近期起量"}
    ):
        return _decision("可加广告", "P3", "库存健康，利润可覆盖广告，销量稳定或上升，可适度放大盈利 SKU。")

    return _decision("观察", "P4", "暂无强动作，建议持续观察库存、销量、广告和利润变化。")


def apply_recommendations(df: pd.DataFrame, thresholds: dict[str, Any] | None = None) -> pd.DataFrame:
    result = df.copy()
    decisions = result.apply(lambda row: recommend_action(row, thresholds), axis=1, result_type="expand")
    result[["final_action", "priority", "reason"]] = decisions[["final_action", "priority", "reason"]]
    return sort_by_priority_action(result)


def sort_by_priority_action(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    result = df.copy()
    if "priority" in result.columns:
        result["_priority_sort"] = pd.Categorical(result["priority"], categories=PRIORITY_ORDER, ordered=True)
    else:
        result["_priority_sort"] = len(PRIORITY_ORDER)
    if "final_action" in result.columns:
        result["_action_sort"] = pd.Categorical(result["final_action"], categories=ACTION_ORDER, ordered=True)
    else:
        result["_action_sort"] = len(ACTION_ORDER)
    sort_cols = ["_priority_sort", "_action_sort"]
    if "stock_days" in result.columns:
        sort_cols.append("stock_days")
    result = result.sort_values(sort_cols, ascending=[True, True, False] if len(sort_cols) == 3 else True)
    return result.drop(columns=["_priority_sort", "_action_sort"])


def _top_percent_mask(df: pd.DataFrame, column: str, top_percent: float) -> pd.Series:
    if column not in df.columns:
        return pd.Series(False, index=df.index)
    values = pd.to_numeric(df[column], errors="coerce").fillna(0)
    if len(values) == 0 or values.max() <= 0:
        return pd.Series(False, index=df.index)
    threshold = values.quantile(max(0, 1 - top_percent))
    return values >= threshold


def select_head_problem_skus(df: pd.DataFrame, thresholds: dict[str, Any] | None = None) -> pd.DataFrame:
    top_percent = _threshold(thresholds, ("ranking", "top_percent"), 0.20)
    top_columns = [
        "sales_14d_amount",
        "ad_spend",
        "recommended_replenishment_qty",
        "total_supply_qty",
        "inventory_value",
    ]
    top_masks = {column: _top_percent_mask(df, column, top_percent) for column in top_columns}
    head_mask = pd.concat(top_masks.values(), axis=1).any(axis=1)
    candidates = df.loc[head_mask].copy()

    def problem_types(row: pd.Series) -> str:
        problems: list[str] = []
        margin = _num(row, "order_gross_margin")
        stock_days = _num(row, "stock_days", 0)
        acos = _num(row, "acos")
        profit_after_ads_margin = _num(row, "profit_after_ads_margin")
        if _is_true(top_masks["sales_14d_amount"].reindex(df.index).loc[row.name]) and not pd.isna(margin) and margin <= 0:
            problems.append("高销量但毛利为负")
        if _is_true(top_masks["sales_14d_amount"].reindex(df.index).loc[row.name]) and stock_days < 30:
            problems.append("高销量但库存不足")
        if _is_true(top_masks["ad_spend"].reindex(df.index).loc[row.name]) and (
            row.get("ad_no_conversion_flag", False)
            or (not pd.isna(acos) and not pd.isna(margin) and acos >= margin)
            or (not pd.isna(profit_after_ads_margin) and profit_after_ads_margin < 0)
        ):
            problems.append("高广告花费但广告亏损")
        if not pd.isna(margin) and margin >= 0.30 and stock_days >= 120:
            problems.append("高毛利但周转慢")
        if _is_true(top_masks["recommended_replenishment_qty"].reindex(df.index).loc[row.name]) and (
            (not pd.isna(margin) and margin <= 0)
            or (not pd.isna(profit_after_ads_margin) and profit_after_ads_margin < 0)
            or (not pd.isna(acos) and not pd.isna(margin) and acos >= margin)
        ):
            problems.append("高补货建议但利润异常")
        if _is_true(top_masks["total_supply_qty"].reindex(df.index).loc[row.name]) and str(row.get("recent_sales_trend", "")) == "近期下滑":
            problems.append("高库存但销量下滑")
        return "；".join(dict.fromkeys(problems))

    if candidates.empty:
        candidates["problem_type"] = []
    else:
        candidates["problem_type"] = candidates.apply(problem_types, axis=1)
        candidates = candidates[candidates["problem_type"] != ""]

    columns = [
        "sku",
        "parent_asin",
        "spu",
        "product_line",
        "sales_14d_amount",
        "sales_14d_units",
        "ad_spend",
        "order_gross_margin",
        "acos",
        "profit_after_ads_margin",
        "stock_days",
        "recommended_replenishment_qty",
        "final_action",
        "priority",
        "reason",
        "problem_type",
    ]
    return _ensure_columns(sort_by_priority_action(candidates), columns)


def select_tail_abnormal_skus(df: pd.DataFrame, thresholds: dict[str, Any] | None = None) -> pd.DataFrame:
    n = int(_threshold(thresholds, ("ranking", "tail_top_n"), 20))
    abnormal: dict[Any, set[str]] = {}

    def add_rows(rows: pd.DataFrame, label: str) -> None:
        for idx in rows.index:
            abnormal.setdefault(idx, set()).add(label)

    add_rows(df.sort_values("stock_days", ascending=False).head(n), "库存天数最高")
    add_rows(
        df[(pd.to_numeric(df.get("main_daily_sales"), errors="coerce") == 0) & (pd.to_numeric(df.get("total_supply_qty"), errors="coerce") > 0)]
        .sort_values("total_supply_qty", ascending=False)
        .head(n),
        "无销量压货",
    )
    if "aged_inventory_181_plus" in df.columns:
        add_rows(df.sort_values("aged_inventory_181_plus", ascending=False).head(n), "181天以上库龄最高")
    add_rows(df[(df.get("ad_spend", 0) > 0) & (df.get("ad_sales", 0) <= 0)].sort_values("ad_spend", ascending=False).head(n), "广告无转化")
    add_rows(df.sort_values("order_gross_margin", ascending=True).head(n), "毛利率最低")
    pressure = df.copy()
    pressure["_stock_sales_pressure"] = pd.to_numeric(pressure.get("total_supply_qty"), errors="coerce").fillna(0) / (
        pd.to_numeric(pressure.get("sales_14d_units"), errors="coerce").fillna(0) + 1
    )
    add_rows(pressure.sort_values("_stock_sales_pressure", ascending=False).head(n), "高库存低销量")

    selected = df.loc[list(abnormal.keys())].copy() if abnormal else df.head(0).copy()
    selected["abnormal_type"] = ["；".join(sorted(abnormal[idx])) for idx in selected.index]
    columns = [
        "sku",
        "parent_asin",
        "spu",
        "product_line",
        "sales_14d_units",
        "main_daily_sales",
        "total_supply_qty",
        "stock_days",
        "aged_inventory_181_plus",
        "ad_spend",
        "ad_sales",
        "order_gross_margin",
        "final_action",
        "priority",
        "reason",
        "abnormal_type",
    ]
    return _ensure_columns(sort_by_priority_action(selected), columns)


def select_high_margin_slow_turnover(df: pd.DataFrame) -> pd.DataFrame:
    selected = df[
        (pd.to_numeric(df.get("order_gross_margin"), errors="coerce") >= 0.30)
        & (pd.to_numeric(df.get("stock_days"), errors="coerce") >= 60)
        & (pd.to_numeric(df.get("main_daily_sales"), errors="coerce") > 0)
    ].copy()

    def investment(row: pd.Series) -> str:
        stock_days = _num(row, "stock_days", 0)
        margin_after_ads = _num(row, "profit_after_ads_margin")
        if 60 <= stock_days <= 120 and not pd.isna(margin_after_ads) and margin_after_ads >= 0:
            return "加大投入加速周转"
        if 120 < stock_days <= 180:
            return "控补货促周转"
        if stock_days > 180:
            return "高毛利停补"
        return "控风险测试"

    selected["investment_recommendation"] = selected.apply(investment, axis=1) if not selected.empty else []
    columns = [
        "sku",
        "parent_asin",
        "spu",
        "product_line",
        "order_gross_margin",
        "stock_days",
        "turnover_level",
        "cashflow_risk_level",
        "sales_14d_units",
        "sales_14d_amount",
        "ad_spend",
        "acos",
        "profit_after_ads_margin",
        "final_action",
        "investment_recommendation",
        "reason",
    ]
    return _ensure_columns(sort_by_priority_action(selected), columns)


def select_urgent_replenishment(df: pd.DataFrame) -> pd.DataFrame:
    selected = df[
        df.get("final_action").isin(["立即补货", "优先补货"])
        | (
            (pd.to_numeric(df.get("stock_days"), errors="coerce") < 30)
            & (pd.to_numeric(df.get("recommended_replenishment_qty"), errors="coerce") > 0)
        )
    ].copy()
    columns = [
        "sku",
        "parent_asin",
        "spu",
        "product_line",
        "stock_days",
        "total_supply_qty",
        "available_qty",
        "inbound_qty",
        "recommended_replenishment_qty",
        "predicted_daily_sales",
        "sales_7d_units",
        "sales_14d_units",
        "order_gross_margin",
        "acos",
        "final_action",
        "priority",
        "reason",
    ]
    return _ensure_columns(sort_by_priority_action(selected), columns)


def select_clearance_stop(df: pd.DataFrame) -> pd.DataFrame:
    selected = df[
        df.get("final_action").isin(["清货处理", "禁止补货", "高毛利停补"])
        | (pd.to_numeric(df.get("stock_days"), errors="coerce") > 180)
        | (
            (pd.to_numeric(df.get("main_daily_sales"), errors="coerce") <= 0)
            & (pd.to_numeric(df.get("total_supply_qty"), errors="coerce") > 0)
        )
    ].copy()
    columns = [
        "sku",
        "parent_asin",
        "spu",
        "product_line",
        "stock_days",
        "total_supply_qty",
        "available_qty",
        "inbound_qty",
        "aged_inventory_181_plus",
        "main_daily_sales",
        "sales_14d_units",
        "order_gross_margin",
        "profit_after_ads_margin",
        "final_action",
        "priority",
        "reason",
    ]
    return _ensure_columns(sort_by_priority_action(selected), columns)


def select_ad_optimization(df: pd.DataFrame) -> pd.DataFrame:
    selected = df[
        (df.get("final_action") == "控广告")
        | ((pd.to_numeric(df.get("ad_spend"), errors="coerce") > 0) & (pd.to_numeric(df.get("ad_sales"), errors="coerce") <= 0))
        | (
            pd.to_numeric(df.get("acos"), errors="coerce")
            >= pd.to_numeric(df.get("order_gross_margin"), errors="coerce")
        )
        | (pd.to_numeric(df.get("profit_after_ads_margin"), errors="coerce") < 0)
    ].copy()
    columns = [
        "sku",
        "parent_asin",
        "spu",
        "product_line",
        "ad_spend",
        "ad_sales",
        "acos",
        "order_gross_margin",
        "profit_after_ads_margin",
        "sales_7d_amount",
        "sales_14d_amount",
        "stock_days",
        "final_action",
        "priority",
        "reason",
    ]
    return _ensure_columns(sort_by_priority_action(selected), columns)


def build_focus_reports(df: pd.DataFrame, thresholds: dict[str, Any] | None = None) -> dict[str, pd.DataFrame]:
    return {
        "head_problem_skus": select_head_problem_skus(df, thresholds),
        "tail_abnormal_skus": select_tail_abnormal_skus(df, thresholds),
        "high_margin_slow_turnover": select_high_margin_slow_turnover(df),
        "urgent_replenishment": select_urgent_replenishment(df),
        "clearance_stop": select_clearance_stop(df),
        "ad_optimization": select_ad_optimization(df),
    }


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = df.copy()
    for column in columns:
        if column not in result.columns:
            result[column] = pd.NA
    return result[columns]
