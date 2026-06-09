from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _get_threshold(thresholds: dict[str, Any] | None, path: tuple[str, ...], default: float) -> float:
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


def _margin_level(value: float, thresholds: dict[str, Any] | None) -> str:
    high = _get_threshold(thresholds, ("margin", "high_margin"), 0.30)
    medium = _get_threshold(thresholds, ("margin", "medium_margin"), 0.15)
    low = _get_threshold(thresholds, ("margin", "low_margin"), 0.0)

    if pd.isna(value):
        return "无利润数据"
    if value >= high:
        return "高毛利"
    if medium <= value < high:
        return "中毛利"
    if low < value < medium:
        return "低毛利"
    return "亏损"


def _turnover_level(row: pd.Series, thresholds: dict[str, Any] | None) -> str:
    stock_days = _num(row, "stock_days")
    main_daily_sales = _num(row, "main_daily_sales", 0)
    total_supply_qty = _num(row, "total_supply_qty", 0)

    if main_daily_sales <= 0 and total_supply_qty > 0:
        return "无销量压货"
    if pd.isna(stock_days):
        return "未知"
    if stock_days < 30:
        return "快周转"
    if stock_days <= 90:
        return "良性周转"
    if stock_days <= 180:
        return "慢周转"
    if stock_days <= 270:
        return "高库存压力"
    return "严重滞销"


def _inventory_status(row: pd.Series, thresholds: dict[str, Any] | None) -> str:
    stock_days = _num(row, "stock_days")
    main_daily_sales = _num(row, "main_daily_sales", 0)
    total_supply_qty = _num(row, "total_supply_qty", 0)

    if main_daily_sales <= 0 and total_supply_qty > 0:
        return "无销量压货"
    if pd.isna(stock_days):
        return "未知"
    if stock_days < _get_threshold(thresholds, ("inventory", "severe_stockout_days"), 14):
        return "严重缺货风险"
    if stock_days < _get_threshold(thresholds, ("inventory", "stockout_warning_days"), 30):
        return "即将断货"
    if stock_days <= _get_threshold(thresholds, ("inventory", "healthy_max_days"), 120):
        return "库存健康"
    if stock_days <= _get_threshold(thresholds, ("inventory", "overstock_days"), 180):
        return "库存偏高"
    if stock_days <= _get_threshold(thresholds, ("inventory", "clearance_days"), 270):
        return "高库存压力"
    return "清货风险"


def _profit_status(row: pd.Series) -> str:
    gross_profit = _num(row, "order_gross_profit")

    if pd.isna(gross_profit):
        return "无利润数据"
    if gross_profit <= 0:
        return "亏损"
    return "盈利"


def _ad_status(row: pd.Series) -> str:
    ad_spend = _num(row, "ad_spend", 0)
    ad_sales = _num(row, "ad_sales", 0)
    acos = _num(row, "acos")
    margin = _num(row, "order_gross_margin")
    gross_profit = _num(row, "order_gross_profit")

    if ad_spend <= 0:
        return "无广告"
    if ad_sales <= 0:
        return "广告无转化"
    if not pd.isna(acos) and not pd.isna(margin) and acos >= margin:
        return "广告亏损"
    if not pd.isna(acos) and not pd.isna(margin) and not pd.isna(gross_profit) and acos < margin and gross_profit > 0:
        return "广告健康"
    return "广告需复核"


def _cashflow_risk(row: pd.Series) -> str:
    stock_days = _num(row, "stock_days")
    gross_profit = _num(row, "order_gross_profit")
    main_daily_sales = _num(row, "main_daily_sales", 0)
    total_supply_qty = _num(row, "total_supply_qty", 0)

    if main_daily_sales <= 0 and total_supply_qty > 0:
        return "极高"
    if not pd.isna(gross_profit) and gross_profit <= 0 and stock_days > 90:
        return "高"
    if not pd.isna(gross_profit) and stock_days <= 90 and gross_profit > 0:
        return "低"
    if not pd.isna(gross_profit) and stock_days <= 180 and gross_profit > 0:
        return "中"
    if stock_days <= 270:
        return "高"
    return "极高"


def classify_skus(df: pd.DataFrame, thresholds: dict[str, Any] | None = None) -> pd.DataFrame:
    result = df.copy()
    margin = pd.to_numeric(result.get("order_gross_margin"), errors="coerce")
    result["margin_level"] = margin.map(lambda value: _margin_level(value, thresholds))
    result["turnover_level"] = result.apply(lambda row: _turnover_level(row, thresholds), axis=1)
    result["inventory_status"] = result.apply(lambda row: _inventory_status(row, thresholds), axis=1)
    result["profit_status"] = result.apply(_profit_status, axis=1)
    result["ad_status"] = result.apply(_ad_status, axis=1)
    result["cashflow_risk_level"] = result.apply(_cashflow_risk, axis=1)
    return result
