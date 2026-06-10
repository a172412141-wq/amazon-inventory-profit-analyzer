from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .classification import classify_skus
from .cleaning import clean_data
from .metrics import calculate_metrics
from .parent_analysis import analyze_parent
from .product_line_analysis import analyze_product_lines
from .recommendations import apply_recommendations, build_focus_reports
from .spu_analysis import analyze_spu
from .validation import validate_data


FULL_SKU_COLUMNS = [
    "sku",
    "asin",
    "parent_asin",
    "spu",
    "product_line",
    "category_level_1",
    "product_name",
    "predicted_daily_sales",
    "stock_days",
    "calculated_stock_days",
    "available_stock_qty",
    "available_stock_days",
    "inbound_stock_days",
    "over_90_stock_qty",
    "over_90_inventory_ratio",
    "recommended_replenishment_qty",
    "total_supply_qty",
    "available_qty",
    "inbound_qty",
    "sales_7d_units",
    "sales_14d_units",
    "sales_7d_amount",
    "sales_14d_amount",
    "avg_sales_7d",
    "avg_sales_14d",
    "main_daily_sales",
    "current_daily_sales_units",
    "current_daily_sales_amount",
    "ideal_turnover_daily_units",
    "recent_sales_trend",
    "order_gross_profit",
    "order_gross_margin",
    "ad_spend",
    "ad_sales",
    "ad_impressions",
    "ad_clicks",
    "ad_orders",
    "total_orders",
    "sessions_7d",
    "sessions_14d",
    "acos",
    "cpc",
    "ctr",
    "cvr",
    "ad_cvr",
    "ad_order_share",
    "aged_inventory_181_plus",
    "inventory_value",
    "margin_level",
    "turnover_level",
    "inventory_status",
    "profit_status",
    "ad_status",
    "cashflow_risk_level",
    "final_action",
    "priority",
    "reason",
]


def _sum(df: pd.DataFrame, column: str) -> float:
    if column not in df.columns:
        return 0.0
    value = pd.to_numeric(df[column], errors="coerce").sum(min_count=1)
    return 0.0 if pd.isna(value) else float(value)


def _numeric_series(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce")


def _mean(df: pd.DataFrame, column: str) -> float:
    if column not in df.columns:
        return np.nan
    value = pd.to_numeric(df[column], errors="coerce").mean()
    return float(value) if not pd.isna(value) else np.nan


def _use_source_ratio_when_needed(calculated: float, source_average: float) -> float:
    if pd.isna(source_average):
        return calculated
    if pd.isna(calculated):
        return source_average
    if calculated == 0 and source_average > 0:
        return source_average
    return calculated


def _nunique(df: pd.DataFrame, column: str) -> int:
    if column not in df.columns:
        return 0
    values = df[column].astype("string").fillna("").str.strip()
    return int(values[values != ""].nunique())


def _safe_divide(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator and denominator > 0 else np.nan


def _format_ratio(value: float) -> str:
    return "-" if pd.isna(value) else f"{value:.2%}"


def _threshold(thresholds: dict[str, Any] | None, path: tuple[str, ...], default: float) -> float:
    current: Any = thresholds or {}
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return float(current)


def prepare_full_sku_table(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for column in FULL_SKU_COLUMNS:
        if column not in result.columns:
            result[column] = pd.NA
    return result[FULL_SKU_COLUMNS]


def build_overview(
    full_sku: pd.DataFrame,
    focus_reports: dict[str, pd.DataFrame],
    thresholds: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str, pd.DataFrame]:
    sku_count = _nunique(full_sku, "sku") or len(full_sku)
    ad_spend = _sum(full_sku, "ad_spend")
    ad_sales = _sum(full_sku, "ad_sales")
    overall_acos = _safe_divide(ad_spend, ad_sales)
    ad_clicks = _sum(full_sku, "ad_clicks")
    ad_impressions = _sum(full_sku, "ad_impressions")
    ad_orders = _sum(full_sku, "ad_orders")
    total_orders = _sum(full_sku, "total_orders")
    sessions_14d = _sum(full_sku, "sessions_14d")
    sales_14d_units = _sum(full_sku, "sales_14d_units")
    if total_orders <= 0:
        total_orders = sales_14d_units
    sales_7d_units = _sum(full_sku, "sales_7d_units")
    sales_14d_amount = _sum(full_sku, "sales_14d_amount")
    sales_7d_amount = _sum(full_sku, "sales_7d_amount")
    gross_profit = _sum(full_sku, "order_gross_profit")
    avg_margin = gross_profit / sales_7d_amount if sales_7d_amount > 0 and gross_profit != 0 else pd.to_numeric(
        full_sku.get("order_gross_margin", pd.Series(dtype=float)),
        errors="coerce",
    ).mean()
    total_supply = _sum(full_sku, "total_supply_qty")
    inbound_qty = _sum(full_sku, "inbound_qty")
    avg_sales_7d_total = sales_7d_units / 7
    available_stock_qty = _sum(full_sku, "available_stock_qty")
    if available_stock_qty <= 0:
        available_qty = _sum(full_sku, "available_qty")
        available_stock_qty = available_qty if available_qty > 0 else max(total_supply - inbound_qty, 0)
    ideal_turnover_daily_units = _sum(full_sku, "ideal_turnover_daily_units")
    over_90_inventory_ratio = _safe_divide(_sum(full_sku, "over_90_stock_qty"), available_stock_qty)
    max_over_90_ratio = _threshold(thresholds, ("inventory", "max_over_90_inventory_ratio"), 0.25)
    ad_order_share = _safe_divide(ad_orders, total_orders)
    cpc = _safe_divide(ad_spend, ad_clicks)
    if pd.isna(cpc):
        cpc = _mean(full_sku, "cpc")
    ctr = _safe_divide(ad_clicks, ad_impressions)
    if pd.isna(ctr):
        ctr = _mean(full_sku, "ctr")
    cvr = _safe_divide(sales_14d_units, sessions_14d)
    cvr = _use_source_ratio_when_needed(cvr, _mean(full_sku, "cvr"))
    ad_cvr = _safe_divide(ad_orders, ad_clicks)
    ad_cvr = _use_source_ratio_when_needed(ad_cvr, _mean(full_sku, "ad_cvr"))

    high_margin_slow_count = len(focus_reports.get("high_margin_slow_turnover", pd.DataFrame()))
    clearance_count = int(full_sku.get("final_action", pd.Series(dtype=str)).isin(["清货处理", "禁止补货", "高毛利停补"]).sum())
    urgent_count = int(full_sku.get("final_action", pd.Series(dtype=str)).isin(["立即补货", "优先补货"]).sum())
    ad_optimization_count = len(focus_reports.get("ad_optimization", pd.DataFrame()))
    available_days = _numeric_series(full_sku, "available_stock_days", np.nan)
    available_qty_series = _numeric_series(full_sku, "available_stock_qty", 0.0).fillna(0.0)
    finite_available_days = available_days.replace([np.inf, -np.inf], np.nan)
    warning_mask = (finite_available_days > 60) & (finite_available_days <= 90)
    redline_mask = (finite_available_days > 90) & (finite_available_days <= 180)
    urgent_redline_mask = finite_available_days > 180
    no_sales_stock_mask = available_days.map(np.isposinf) & (available_qty_series > 0)
    urgent_redline_mask = urgent_redline_mask | no_sales_stock_mask
    warning_qty = float(available_qty_series[warning_mask].sum())
    redline_qty = float(available_qty_series[redline_mask].sum())
    urgent_redline_qty = float(available_qty_series[urgent_redline_mask].sum())

    metrics = {
        "SKU 总数": sku_count,
        "父体数": _nunique(full_sku, "parent_asin"),
        "SPU 数": _nunique(full_sku, "spu"),
        "品线数": _nunique(full_sku, "product_line"),
        "14天销售额": _sum(full_sku, "sales_14d_amount"),
        "14天销量": sales_14d_units,
        "目前日均销量": _sum(full_sku, "current_daily_sales_units"),
        "目前日均销售额": _sum(full_sku, "current_daily_sales_amount"),
        "理想周转情况下日销量": ideal_turnover_daily_units,
        "总广告花费": ad_spend,
        "广告销售额": ad_sales,
        "整体 ACOS": overall_acos,
        "广告订单占比": ad_order_share,
        "CPC": cpc,
        "CTR": ctr,
        "CVR": cvr,
        "广告CVR": ad_cvr,
        "订单毛利润": gross_profit,
        "平均毛利率": avg_margin,
        "总库存/总供给": total_supply,
        "可售库存天数": _safe_divide(available_stock_qty, avg_sales_7d_total),
        "在途库存天数": _safe_divide(inbound_qty, avg_sales_7d_total),
        "61-90天可售库存量": warning_qty,
        "91-180天可售库存量": redline_qty,
        "180天+可售库存量": urgent_redline_qty,
        "90天+库存占比": over_90_inventory_ratio,
        "建议补货总量": _sum(full_sku, "recommended_replenishment_qty"),
        "清货风险 SKU 数": int((full_sku.get("final_action", pd.Series(dtype=str)) == "清货处理").sum()),
        "禁止补货 SKU 数": int((full_sku.get("final_action", pd.Series(dtype=str)) == "禁止补货").sum()),
        "高毛利慢周转 SKU 数": high_margin_slow_count,
        "立即补货 SKU 数": int((full_sku.get("final_action", pd.Series(dtype=str)) == "立即补货").sum()),
        "广告优化 SKU 数": ad_optimization_count,
        "清货/停补 SKU 数": clearance_count,
        "紧急补货 SKU 数": urgent_count,
    }

    summary = (
        f"本次共分析 {sku_count} 个 SKU，涉及 {metrics['父体数']} 个父体、{metrics['SPU 数']} 个 SPU、"
        f"{metrics['品线数']} 条品线。\n"
        f"当前主要问题：\n"
        f"1. 高毛利慢周转 SKU 有 {high_margin_slow_count} 个，说明部分利润被库存占用，需加速周转。\n"
        f"2. 91-180 天红线可售库存量为 {redline_qty:,.1f} 件，需 P0 处理周转。\n"
        f"3. 清货/停补 SKU 有 {clearance_count} 个，说明库存现金流风险较高。\n"
        f"4. 90天+库存占比为 {_format_ratio(over_90_inventory_ratio)}，理想状态应低于 {max_over_90_ratio:.0%}，"
        f"需围绕目标日销量 {ideal_turnover_daily_units:,.1f} 加速周转。\n"
        f"5. 广告优化 SKU 有 {ad_optimization_count} 个，说明广告花费存在亏损或无转化。\n"
        f"6. 紧急补货 SKU 有 {urgent_count} 个，需避免断货影响排名和销售。\n"
        f"7. 建议优先关注头部问题 SKU 和尾部极端异常 SKU。"
    )

    overview_rows = [{"metric": key, "value": value} for key, value in metrics.items()]
    overview_rows.append({"metric": "自动总结", "value": summary})
    return metrics, summary, pd.DataFrame(overview_rows)


def run_analysis(
    mapped_df: pd.DataFrame,
    mapping_report: dict[str, Any],
    mapping_config: dict[str, Any],
    thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cleaned = clean_data(mapped_df, mapping_config)
    metric_df = calculate_metrics(cleaned, thresholds)
    classified = classify_skus(metric_df, thresholds)
    full = apply_recommendations(classified, thresholds)
    data_errors = validate_data(full, mapping_report, mapping_config)
    focus_reports = build_focus_reports(full, thresholds)
    parent_analysis, parent_structure = analyze_parent(full, thresholds)
    spu_analysis = analyze_spu(full, thresholds)
    product_line_analysis = analyze_product_lines(full, thresholds)
    full_sku = prepare_full_sku_table(full)
    overview_metrics, overview_summary, overview = build_overview(full_sku, focus_reports, thresholds)

    report_tables = {
        "overview": overview,
        "head_problem_skus": focus_reports["head_problem_skus"],
        "tail_abnormal_skus": focus_reports["tail_abnormal_skus"],
        "high_margin_slow_turnover": focus_reports["high_margin_slow_turnover"],
        "urgent_replenishment": focus_reports["urgent_replenishment"],
        "clearance_stop": focus_reports["clearance_stop"],
        "ad_optimization": focus_reports["ad_optimization"],
        "full_sku": full_sku,
        "parent_analysis": parent_analysis,
        "parent_structure_anomalies": parent_structure,
        "spu_analysis": spu_analysis,
        "product_line_analysis": product_line_analysis,
        "data_errors": data_errors,
    }

    return {
        "full": full,
        "full_sku": full_sku,
        "focus_reports": focus_reports,
        "parent_analysis": parent_analysis,
        "parent_structure_anomalies": parent_structure,
        "spu_analysis": spu_analysis,
        "product_line_analysis": product_line_analysis,
        "data_errors": data_errors,
        "overview_metrics": overview_metrics,
        "overview_summary": overview_summary,
        "report_tables": report_tables,
    }
