from __future__ import annotations

from typing import Any

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

    ad_spend = pd.to_numeric(df.get("ad_spend", 0), errors="coerce").fillna(0)
    ad_sales = pd.to_numeric(df.get("ad_sales", 0), errors="coerce").fillna(0)
    acos = pd.to_numeric(df.get("acos", pd.Series(index=df.index, dtype=float)), errors="coerce")
    margin = pd.to_numeric(df.get("order_gross_margin", pd.Series(index=df.index, dtype=float)), errors="coerce")
    stock_days = pd.to_numeric(df.get("stock_days", pd.Series(index=df.index, dtype=float)), errors="coerce")
    replenishment = pd.to_numeric(
        df.get("recommended_replenishment_qty", pd.Series(index=df.index, dtype=float)),
        errors="coerce",
    )
    main_daily_sales = pd.to_numeric(
        df.get("main_daily_sales", pd.Series(index=df.index, dtype=float)),
        errors="coerce",
    )

    for idx in df.index[(ad_spend > 0) & (ad_sales <= 0)]:
        _add_error(errors, sku_series.loc[idx], "广告花费 > 0 但广告销售额 = 0", "高", "广告有花费但无销售转化。")

    for idx in df.index[acos > 1]:
        _add_error(errors, sku_series.loc[idx], "ACOS > 100%", "中", "ACOS 高于 100%，需复核广告效率或字段格式。")

    for idx in df.index[margin < -0.5]:
        _add_error(errors, sku_series.loc[idx], "毛利率 < -50%", "高", "毛利率低于 -50%，需复核成本或利润数据。")

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

    return pd.DataFrame(errors, columns=["sku", "error_type", "error_level", "error_message"])
