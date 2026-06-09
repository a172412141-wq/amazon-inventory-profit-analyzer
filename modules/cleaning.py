from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd


def is_empty_value(value: Any) -> bool:
    if pd.isna(value):
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"", "nan", "none", "null", "-"}
    return False


def to_number(value: Any) -> float:
    if is_empty_value(value):
        return np.nan
    if isinstance(value, (int, float, np.number)):
        return float(value)
    text = str(value).strip()
    text = text.replace(",", "")
    text = text.replace("￥", "").replace("¥", "").replace("$", "")
    text = re.sub(r"[^\d.\-%()]", "", text)
    if text.startswith("(") and text.endswith(")"):
        text = f"-{text[1:-1]}"
    text = text.replace("%", "")
    if text in {"", "-", ".", "-."}:
        return np.nan
    try:
        return float(text)
    except ValueError:
        return np.nan


def to_percentage(value: Any) -> float:
    if is_empty_value(value):
        return np.nan
    has_percent_symbol = isinstance(value, str) and "%" in value
    number = to_number(value)
    if np.isnan(number):
        return np.nan
    if has_percent_symbol:
        return number / 100
    # Plain 30 should mean 30%, while 1.2 is kept as 120%.
    if abs(number) > 2:
        return number / 100
    return number


def clean_data(df: pd.DataFrame, mapping_config: dict[str, Any]) -> pd.DataFrame:
    cleaned = df.copy()

    if "sku" in cleaned.columns:
        cleaned["sku"] = cleaned["sku"].astype("string").fillna("").str.strip()

    numeric_fields = mapping_config.get("numeric_fields", [])
    percentage_fields = set(mapping_config.get("percentage_fields", []))
    zero_fill_fields = set(mapping_config.get("zero_fill_fields", []))

    for field in numeric_fields:
        if field not in cleaned.columns:
            cleaned[field] = np.nan

        missing_flag = f"_missing_{field}"
        cleaned[missing_flag] = cleaned[field].map(is_empty_value)

        if field in percentage_fields:
            cleaned[field] = cleaned[field].map(to_percentage).astype(float)
        else:
            cleaned[field] = cleaned[field].map(to_number).astype(float)

        if field in zero_fill_fields:
            cleaned[field] = cleaned[field].fillna(0.0)

    cleaned["profit_data_missing_flag"] = cleaned.get("order_gross_profit", pd.Series(np.nan)).isna()
    return cleaned
