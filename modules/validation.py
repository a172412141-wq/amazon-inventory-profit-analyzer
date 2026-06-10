from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def get_missing_required_fields(
    mapping_report: dict[str, Any],
    mapping_config: dict[str, Any],
) -> list[str]:
    missing = set(mapping_report.get("missing_fields", []))
    required = [field for field in mapping_config.get("required_fields", []) if field in missing]

    for group in mapping_config.get("required_any_groups", []):
        fields = group.get("fields", [])
        if all(field in missing for field in fields):
            required.append(group.get("label") or " / ".join(fields))
    return required


def _add_error(
    errors: list[dict[str, Any]],
    sku: Any,
    error_type: str,
    error_level: str,
    error_message: str,
) -> None:
    errors.append(
        {
            "sku": "" if pd.isna(sku) else str(sku),
            "error_type": error_type,
            "error_level": error_level,
            "error_message": error_message,
        }
    )


def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(df.get(column, pd.Series(index=df.index, dtype=float)), errors="coerce")


def _source_exists(mapping_report: dict[str, Any], field: str) -> bool:
    return field not in set(mapping_report.get("missing_fields", []))


def _fmt(value: float) -> str:
    if pd.isna(value):
        return "-"
    if not np.isfinite(float(value)):
        return "无穷大"
    return f"{float(value):,.2f}"


def _fmt_pct(value: float) -> str:
    return "-" if pd.isna(value) else f"{float(value):.2%}"


def _sort_errors(errors: pd.DataFrame) -> pd.DataFrame:
    if errors.empty:
        return errors
    type_order = [
        "库存信息不匹配",
        "库存天数口径不一致",
        "毛利率 > 100%",
        "毛利率 < -50%",
        "缺少必填字段",
        "SKU 为空",
        "SKU 重复",
        "广告花费 > 0 但广告销售额 = 0",
        "ACOS > 100%",
    ]
    level_order = ["高", "中", "低"]
    result = errors.copy()
    result["_type_sort"] = pd.Categorical(result["error_type"], categories=type_order, ordered=True)
    result["_level_sort"] = pd.Categorical(result["error_level"], categories=level_order, ordered=True)
    return result.sort_values(["_type_sort", "_level_sort", "sku"], na_position="last").drop(columns=["_type_sort", "_level_sort"])


def validate_data(
    df: pd.DataFrame,
    mapping_report: dict[str, Any],
    mapping_config: dict[str, Any],
) -> pd.DataFrame:
    errors: list[dict[str, Any]] = []
    missing_source_fields = set(mapping_report.get("missing_fields", []))

    for field in get_missing_required_fields(mapping_report, mapping_config):
        _add_error(errors, "", "缺少必填字段", "高", f"缺少必填字段：{field}")

    sku_series = df.get("sku", pd.Series("", index=df.index)).astype("string").fillna("").str.strip()
    for idx in sku_series[sku_series == ""].index:
        _add_error(errors, "", "SKU 为空", "高", f"第 {idx + 1} 行 SKU 为空。")

    duplicated = sku_series[(sku_series != "") & sku_series.duplicated(keep=False)]
    for idx, sku in duplicated.items():
        _add_error(errors, sku, "SKU 重复", "中", f"SKU {sku} 在数据中重复出现。")

    field_groups = {
        "销量为空": ["predicted_daily_sales", "sales_7d_units", "sales_14d_units"],
        "库存为空": ["stock_days", "total_supply_qty", "available_qty"],
    }
    for error_type, fields in field_groups.items():
        for field in fields:
            if field in missing_source_fields:
                continue
            flag = f"_missing_{field}"
            if flag not in df.columns:
                continue
            for idx in df.index[df[flag].fillna(False)]:
                _add_error(errors, sku_series.loc[idx], error_type, "中", f"{field} 为空，已按 0 参与计算。")

    if "order_gross_margin" not in missing_source_fields:
        margin_missing = df.get("order_gross_margin", pd.Series(index=df.index, dtype=float)).isna()
        for idx in df.index[margin_missing]:
            _add_error(errors, sku_series.loc[idx], "毛利率为空", "高", "毛利率为空，已标记为无利润数据。")

    if "order_gross_profit" not in missing_source_fields:
        gross_profit_missing = df.get("order_gross_profit", pd.Series(index=df.index, dtype=float)).isna()
        for idx in df.index[gross_profit_missing]:
            _add_error(errors, sku_series.loc[idx], "毛利润为空", "高", "订单毛利润为空，无法判断利润健康。")

    ad_spend = _numeric(df, "ad_spend").fillna(0)
    ad_sales = _numeric(df, "ad_sales").fillna(0)
    acos = _numeric(df, "acos")
    margin = _numeric(df, "order_gross_margin")
    gross_profit = _numeric(df, "order_gross_profit")
    sales_7d_amount = _numeric(df, "sales_7d_amount")
    stock_days = _numeric(df, "stock_days")
    total_supply = _numeric(df, "total_supply_qty")
    available = _numeric(df, "available_qty")
    inbound = _numeric(df, "inbound_qty")
    replenishment = _numeric(df, "recommended_replenishment_qty")
    main_daily_sales = _numeric(df, "main_daily_sales")
    calculated_stock_days = _numeric(df, "calculated_stock_days")
    available_stock_days = _numeric(df, "available_stock_days")

    for idx in df.index[(ad_spend > 0) & (ad_sales <= 0)]:
        _add_error(errors, sku_series.loc[idx], "广告花费 > 0 但广告销售额 = 0", "高", "广告有花费但无销售转化。")

    for idx in df.index[acos > 1]:
        _add_error(errors, sku_series.loc[idx], "ACOS > 100%", "中", "ACOS 高于 100%，需复核广告效率或字段格式。")

    for idx in df.index[margin > 1]:
        _add_error(
            errors,
            sku_series.loc[idx],
            "毛利率 > 100%",
            "高",
            f"毛利率为 {_fmt_pct(margin.loc[idx])}，超过 100%，请检查百分比格式或字段映射。",
        )

    for idx in df.index[margin < -0.5]:
        _add_error(errors, sku_series.loc[idx], "毛利率 < -50%", "高", f"毛利率为 {_fmt_pct(margin.loc[idx])}，低于 -50%，需复核成本或利润数据。")

    if _source_exists(mapping_report, "total_supply_qty") and _source_exists(mapping_report, "available_qty"):
        for idx in df.index[available > total_supply]:
            _add_error(
                errors,
                sku_series.loc[idx],
                "库存信息不匹配",
                "高",
                f"可售库存 {_fmt(available.loc[idx])} 大于总供给 {_fmt(total_supply.loc[idx])}，请核对库存字段映射。",
            )

    if _source_exists(mapping_report, "total_supply_qty") and _source_exists(mapping_report, "inbound_qty"):
        for idx in df.index[inbound > total_supply]:
            _add_error(
                errors,
                sku_series.loc[idx],
                "库存信息不匹配",
                "高",
                f"在途库存 {_fmt(inbound.loc[idx])} 大于总供给 {_fmt(total_supply.loc[idx])}，请核对库存字段映射。",
            )

    if all(_source_exists(mapping_report, field) for field in ["total_supply_qty", "available_qty", "inbound_qty"]):
        expected_total = available.fillna(0) + inbound.fillna(0)
        supply_diff = (total_supply - expected_total).abs()
        tolerance = (total_supply.abs() * 0.05).clip(lower=5)
        for idx in df.index[total_supply.notna() & (supply_diff > tolerance)]:
            _add_error(
                errors,
                sku_series.loc[idx],
                "库存信息不匹配",
                "中",
                f"总供给 {_fmt(total_supply.loc[idx])} 与可售库存 {_fmt(available.loc[idx])} + 在途库存 {_fmt(inbound.loc[idx])} "
                f"不一致，差异 {_fmt(supply_diff.loc[idx])}，请核对库存口径。",
            )

    if _source_exists(mapping_report, "stock_days") and _source_exists(mapping_report, "total_supply_qty"):
        stock_day_diff = (stock_days - calculated_stock_days).abs()
        stock_day_rel_diff = stock_day_diff / stock_days.abs().replace(0, np.nan)
        mismatch = (
            stock_days.notna()
            & calculated_stock_days.notna()
            & stock_days.map(np.isfinite)
            & calculated_stock_days.map(np.isfinite)
            & (stock_day_diff > 15)
            & (stock_day_rel_diff > 0.35)
        )
        for idx in df.index[mismatch]:
            _add_error(
                errors,
                sku_series.loc[idx],
                "库存天数口径不一致",
                "中",
                f"表内库存天数 {_fmt(stock_days.loc[idx])}，按总供给 / 主日销量反算为 {_fmt(calculated_stock_days.loc[idx])}，"
                f"差异 {_fmt(stock_day_diff.loc[idx])} 天，请核对库存天数、总供给或销量口径。",
            )

    if _source_exists(mapping_report, "stock_days") and _source_exists(mapping_report, "available_qty"):
        stock_day_diff = (available_stock_days - stock_days).abs()
        stock_day_rel_diff = stock_day_diff / stock_days.abs().replace(0, np.nan)
        mismatch = (
            available_stock_days.notna()
            & stock_days.notna()
            & available_stock_days.map(np.isfinite)
            & stock_days.map(np.isfinite)
            & (stock_day_diff > 30)
            & (stock_day_rel_diff > 0.35)
        )
        for idx in df.index[mismatch]:
            _add_error(
                errors,
                sku_series.loc[idx],
                "库存天数口径不一致",
                "中",
                f"按可售库存 / 7天平均日销量计算的可售库存天数为 {_fmt(available_stock_days.loc[idx])}，"
                f"表内库存天数为 {_fmt(stock_days.loc[idx])}，差异 {_fmt(stock_day_diff.loc[idx])} 天，请核对可售库存、在途库存和库存天数字段口径。",
            )

    for idx in df.index[stock_days < 0]:
        _add_error(errors, sku_series.loc[idx], "stock_days 为负数", "高", "库存天数为负数，需复核库存字段。")

    for idx in df.index[replenishment < 0]:
        _add_error(errors, sku_series.loc[idx], "recommended_replenishment_qty 为负数", "中", "建议补货量为负数，需复核补货逻辑。")

    for idx in df.index[(main_daily_sales == 0) & (replenishment > 0)]:
        _add_error(
            errors,
            sku_series.loc[idx],
            "main_daily_sales = 0 但 recommended_replenishment_qty > 0",
            "高",
            "主销量为 0 但仍有补货建议，需人工复核。",
        )

    return _sort_errors(pd.DataFrame(errors, columns=["sku", "error_type", "error_level", "error_message"]))
