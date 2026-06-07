from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def _rewind(file: Any) -> None:
    if hasattr(file, "seek"):
        file.seek(0)


def normalize_column_name(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", "", text)
    return text.lower()


def _alias_lookup(mapping_config: dict[str, Any]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for standard_name, spec in mapping_config.get("fields", {}).items():
        for alias in spec.get("aliases", []):
            lookup[normalize_column_name(alias)] = standard_name
    return lookup


def get_sheet_names(excel_file: Any) -> list[str]:
    _rewind(excel_file)
    workbook = pd.ExcelFile(excel_file)
    names = list(workbook.sheet_names)
    _rewind(excel_file)
    return names


def detect_header_row(
    excel_file: Any,
    sheet_name: str,
    mapping_config: dict[str, Any],
    scan_rows: int = 12,
) -> int:
    """Find the row that best matches configured aliases.

    The sample replenishment workbook has two summary rows before its real
    header. Scanning keeps that shape compatible without hard-coding row 3.
    """
    _rewind(excel_file)
    preview = pd.read_excel(
        excel_file,
        sheet_name=sheet_name,
        header=None,
        nrows=scan_rows,
        dtype=object,
    )
    _rewind(excel_file)

    aliases = set(_alias_lookup(mapping_config).keys())
    best_row = 0
    best_score = -1
    for row_index, row in preview.iterrows():
        values = {normalize_column_name(value) for value in row.tolist()}
        score = sum(1 for value in values if value in aliases)
        # Prefer rows that include SKU and sales/profit anchors.
        if "sku" in values:
            score += 2
        if "预测日销量" in values or "predicteddailysales" in values:
            score += 1
        if "订单毛利率" in values or "ordergrossmargin" in values:
            score += 1
        if score > best_score:
            best_score = score
            best_row = int(row_index)

    return best_row if best_score > 0 else 0


def read_raw_sheet(
    excel_file: Any,
    sheet_name: str,
    mapping_config: dict[str, Any],
) -> tuple[pd.DataFrame, int]:
    header_row = detect_header_row(excel_file, sheet_name, mapping_config)
    _rewind(excel_file)
    df = pd.read_excel(excel_file, sheet_name=sheet_name, header=header_row, dtype=object)
    _rewind(excel_file)

    df = df.dropna(how="all").copy()
    df.columns = [str(column).strip() for column in df.columns]
    return df, header_row


def apply_column_mapping(
    raw_df: pd.DataFrame,
    mapping_config: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    normalized_columns = {
        normalize_column_name(column): column for column in raw_df.columns if str(column).strip()
    }

    mapped = pd.DataFrame(index=raw_df.index)
    matched_columns: dict[str, str] = {}
    missing_fields: list[str] = []

    for standard_name, spec in mapping_config.get("fields", {}).items():
        source_column = None
        for alias in spec.get("aliases", []):
            candidate = normalized_columns.get(normalize_column_name(alias))
            if candidate is not None:
                source_column = candidate
                break

        if source_column is None:
            mapped[standard_name] = pd.NA
            missing_fields.append(standard_name)
        else:
            mapped[standard_name] = raw_df[source_column]
            matched_columns[standard_name] = source_column

    report = {
        "matched_columns": matched_columns,
        "missing_fields": missing_fields,
        "raw_columns": list(raw_df.columns),
    }
    return mapped.reset_index(drop=True), report


def load_mapped_sheet(
    excel_file: Any,
    sheet_name: str,
    mapping_config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    raw_df, header_row = read_raw_sheet(excel_file, sheet_name, mapping_config)
    mapped_df, mapping_report = apply_column_mapping(raw_df, mapping_config)
    mapping_report["header_row"] = header_row
    mapping_report["sheet_name"] = sheet_name
    return raw_df.reset_index(drop=True), mapped_df, mapping_report


def get_sheet_summaries(
    excel_file: Any,
    mapping_config: dict[str, Any],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for sheet_name in get_sheet_names(excel_file):
        raw_df, header_row = read_raw_sheet(excel_file, sheet_name, mapping_config)
        summaries.append(
            {
                "sheet_name": sheet_name,
                "header_row": header_row,
                "rows": int(len(raw_df)),
                "columns": int(len(raw_df.columns)),
                "preview": raw_df.head(20),
            }
        )
    return summaries
