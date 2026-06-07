from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .recommendations import ACTION_ORDER, PRIORITY_ORDER


SHEET_ORDER = [
    ("01_总览", "overview"),
    ("02_头部重点问题SKU", "head_problem_skus"),
    ("03_尾部异常SKU", "tail_abnormal_skus"),
    ("04_高毛利慢周转SKU", "high_margin_slow_turnover"),
    ("05_紧急补货SKU", "urgent_replenishment"),
    ("06_清货停补SKU", "clearance_stop"),
    ("07_广告优化SKU", "ad_optimization"),
    ("08_SKU完整判断", "full_sku"),
    ("09_父体分析", "parent_analysis"),
    ("10_父体结构异常", "parent_structure_anomalies"),
    ("11_SPU分析", "spu_analysis"),
    ("12_品线分析", "product_line_analysis"),
    ("13_数据异常", "data_errors"),
]

PERCENT_HINTS = ("margin", "acos", "rate", "share", "毛利率", "转化率", "占比")
MONEY_FIELDS = {
    "sales_7d_amount",
    "sales_14d_amount",
    "order_gross_profit",
    "ad_spend",
    "ad_sales",
    "ad_profit_after_ads",
    "inventory_value",
}
QUANTITY_HINTS = ("qty", "units", "days", "count", "sales_7d_units", "sales_14d_units")


def _sort_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    result = df.copy()
    sort_columns: list[str] = []
    ascending: list[bool] = []
    if "priority" in result.columns:
        result["_priority_sort"] = pd.Categorical(result["priority"], categories=PRIORITY_ORDER, ordered=True)
        sort_columns.append("_priority_sort")
        ascending.append(True)
    if "final_action" in result.columns:
        result["_action_sort"] = pd.Categorical(result["final_action"], categories=ACTION_ORDER, ordered=True)
        sort_columns.append("_action_sort")
        ascending.append(True)
    if "stock_days" in result.columns:
        sort_columns.append("stock_days")
        ascending.append(False)
    if sort_columns:
        result = result.sort_values(sort_columns, ascending=ascending)
    return result.drop(columns=[column for column in ["_priority_sort", "_action_sort"] if column in result.columns])


def _display_df(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    result = df.copy().astype("object")
    result = result.drop(columns=[column for column in result.columns if column.startswith("_missing_")], errors="ignore")
    for column_index in range(len(result.columns)):
        result.iloc[:, column_index] = result.iloc[:, column_index].map(_normalize_excel_value)
    return _sort_df(result)


def _normalize_excel_value(value: Any) -> Any:
    if isinstance(value, (float, np.floating)) and np.isinf(value):
        return "∞" if value > 0 else "-∞"
    return value


def _column_format(column: str, formats: dict[str, Any]) -> Any | None:
    lower = column.lower()
    if any(hint in lower for hint in PERCENT_HINTS):
        return formats["percent"]
    if column in MONEY_FIELDS or "amount" in lower or "profit" in lower or "spend" in lower or "sales" in lower and "units" not in lower:
        return formats["money"]
    if any(hint in lower for hint in QUANTITY_HINTS) or "库存" in column or "补货" in column:
        return formats["quantity"]
    return None


def _column_width(series: pd.Series, column: str) -> int:
    sample = series.astype(str).replace("nan", "").head(200).tolist()
    max_len = max([len(str(column))] + [len(str(value)) for value in sample])
    return max(10, min(max_len + 2, 48))


def _write_sheet(writer: pd.ExcelWriter, sheet_name: str, df: pd.DataFrame) -> None:
    display = _display_df(df)
    display.to_excel(writer, sheet_name=sheet_name, index=False)
    workbook = writer.book
    worksheet = writer.sheets[sheet_name]

    header_format = workbook.add_format({"bold": True, "bg_color": "#DDEBF7", "border": 1})
    formats = {
        "percent": workbook.add_format({"num_format": "0.00%"}),
        "money": workbook.add_format({"num_format": "#,##0.00"}),
        "quantity": workbook.add_format({"num_format": "#,##0.0"}),
    }

    for col_idx, column in enumerate(display.columns):
        worksheet.write(0, col_idx, column, header_format)
        width = _column_width(display[column], str(column))
        worksheet.set_column(col_idx, col_idx, width, _column_format(str(column), formats))

    worksheet.freeze_panes(1, 0)
    if len(display.columns) > 0:
        worksheet.autofilter(0, 0, max(len(display), 1), len(display.columns) - 1)


def export_analysis_report(
    report_tables: dict[str, pd.DataFrame],
    output_path: str | Path | None = None,
) -> bytes | Path:
    target: BytesIO | str | Path
    if output_path is None:
        target = BytesIO()
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        target = output_path

    with pd.ExcelWriter(target, engine="xlsxwriter") as writer:
        for sheet_name, key in SHEET_ORDER:
            _write_sheet(writer, sheet_name, report_tables.get(key, pd.DataFrame()))

    if output_path is not None:
        return output_path
    assert isinstance(target, BytesIO)
    return target.getvalue()
