from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from modules.export_report import export_analysis_report
from modules.loader import get_sheet_summaries, load_mapped_sheet, load_yaml
from modules.parent_analysis import analyze_parent
from modules.pipeline import build_overview, prepare_full_sku_table, run_analysis
from modules.product_line_analysis import analyze_product_lines
from modules.recommendations import build_focus_reports
from modules.spu_analysis import analyze_spu
from modules.validation import get_missing_required_fields


BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
OUTPUT_DIR = BASE_DIR / "output" / "reports"
PERCENT_HINTS = (
    "margin",
    "acos",
    "rate",
    "share",
    "ratio",
    "ctr",
    "cvr",
    "percent",
    "percentage",
    "毛利率",
    "利润率",
    "转化率",
    "占比",
    "比率",
)


@st.cache_data(show_spinner=False)
def load_configs() -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        load_yaml(CONFIG_DIR / "column_mapping.yaml"),
        load_yaml(CONFIG_DIR / "thresholds.yaml"),
    )


def _format_metric(value: Any, percent: bool = False, money: bool = False) -> str:
    if pd.isna(value):
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if percent:
        return f"{number:.2%}"
    if money:
        return f"{number:,.2f}"
    if abs(number) >= 1000:
        return f"{number:,.0f}"
    return f"{number:.1f}" if number % 1 else f"{number:.0f}"


def _is_percent_column(column: str) -> bool:
    lower = column.lower()
    return any(hint in lower for hint in PERCENT_HINTS)


def _numeric_display_series(series: pd.Series) -> pd.Series | None:
    if pd.api.types.is_bool_dtype(series):
        return None
    if pd.api.types.is_numeric_dtype(series):
        numeric = pd.to_numeric(series, errors="coerce")
    else:
        non_empty = series.dropna()
        if non_empty.empty:
            return None
        non_empty_text = non_empty.astype(str).str.strip()
        non_empty = non_empty[non_empty_text != ""]
        if non_empty.empty:
            return None
        parsed = pd.to_numeric(non_empty, errors="coerce")
        if parsed.notna().sum() != len(non_empty):
            return None
        numeric = pd.to_numeric(series, errors="coerce")
    return numeric.mask(~np.isfinite(numeric), np.nan)


def _prepare_dataframe_display(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    display = df.copy()
    column_config: dict[str, Any] = {}
    for column in display.columns:
        numeric_values = _numeric_display_series(display[column])
        if numeric_values is None or not numeric_values.notna().any():
            continue
        if _is_percent_column(str(column)):
            display[column] = numeric_values * 100
            column_config[str(column)] = st.column_config.NumberColumn(format="%.2f%%")
        else:
            display[column] = numeric_values
            column_config[str(column)] = st.column_config.NumberColumn(format="%.2f")
    return display, column_config


def _options(df: pd.DataFrame, column: str) -> list[str]:
    if column not in df.columns:
        return []
    values = df[column].dropna().astype(str).map(str.strip)
    return sorted(value for value in values.unique().tolist() if value and value.lower() not in {"nan", "none"})


def _apply_filters(df: pd.DataFrame, filters: dict[str, list[str]]) -> pd.DataFrame:
    result = df.copy()
    for column, selected in filters.items():
        if selected and column in result.columns:
            result = result[result[column].astype(str).isin(selected)]
    return result


def _filter_errors(data_errors: pd.DataFrame, visible_skus: set[str]) -> pd.DataFrame:
    if data_errors.empty or not visible_skus:
        return data_errors
    blank = data_errors["sku"].astype(str).str.strip() == ""
    return data_errors[blank | data_errors["sku"].astype(str).isin(visible_skus)]


def _build_filtered_tables(
    full: pd.DataFrame,
    data_errors: pd.DataFrame,
    thresholds: dict[str, Any],
) -> tuple[dict[str, pd.DataFrame], dict[str, Any], str]:
    focus = build_focus_reports(full, thresholds)
    parent_analysis, parent_structure = analyze_parent(full, thresholds)
    spu_analysis = analyze_spu(full, thresholds)
    product_line_analysis = analyze_product_lines(full, thresholds)
    full_sku = prepare_full_sku_table(full)
    metrics, summary, overview = build_overview(full_sku, focus, thresholds)
    visible_skus = set(full_sku["sku"].astype(str)) if "sku" in full_sku.columns else set()
    tables = {
        "overview": overview,
        "head_problem_skus": focus["head_problem_skus"],
        "tail_abnormal_skus": focus["tail_abnormal_skus"],
        "high_margin_slow_turnover": focus["high_margin_slow_turnover"],
        "urgent_replenishment": focus["urgent_replenishment"],
        "clearance_stop": focus["clearance_stop"],
        "ad_optimization": focus["ad_optimization"],
        "full_sku": full_sku,
        "parent_analysis": parent_analysis,
        "parent_structure_anomalies": parent_structure,
        "spu_analysis": spu_analysis,
        "product_line_analysis": product_line_analysis,
        "data_errors": _filter_errors(data_errors, visible_skus),
    }
    return tables, metrics, summary


def _render_dashboard(full_sku: pd.DataFrame, metrics: dict[str, Any], summary: str) -> None:
    metric_specs = [
        ("SKU 总数", False, False),
        ("父体数", False, False),
        ("SPU 数", False, False),
        ("品线数", False, False),
        ("14天销售额", False, True),
        ("14天销量", False, False),
        ("目前日均销量", False, False),
        ("目前日均销售额", False, True),
        ("理想周转情况下日销量", False, False),
        ("总广告花费", False, True),
        ("广告销售额", False, True),
        ("整体 ACOS", True, False),
        ("广告订单占比", True, False),
        ("CPC", False, True),
        ("CTR", True, False),
        ("订单毛利润", False, True),
        ("平均毛利率", True, False),
        ("总库存/总供给", False, False),
        ("可售库存天数", False, False),
        ("在途库存天数", False, False),
        ("90天+库存占比", True, False),
        ("建议补货总量", False, False),
        ("清货风险 SKU 数", False, False),
        ("禁止补货 SKU 数", False, False),
        ("高毛利慢周转 SKU 数", False, False),
        ("立即补货 SKU 数", False, False),
        ("广告优化 SKU 数", False, False),
    ]
    for start in range(0, len(metric_specs), 4):
        cols = st.columns(4)
        for col, (label, is_percent, is_money) in zip(cols, metric_specs[start : start + 4]):
            col.metric(label, _format_metric(metrics.get(label), is_percent, is_money))

    st.markdown(summary.replace("\n", "\n\n"))

    chart_cols = st.columns(2)
    if "final_action" in full_sku.columns and not full_sku.empty:
        action_counts = full_sku["final_action"].value_counts().reset_index()
        action_counts.columns = ["final_action", "sku_count"]
        fig = px.bar(action_counts, x="final_action", y="sku_count", text="sku_count")
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=20, b=10))
        chart_cols[0].plotly_chart(fig, use_container_width=True)
    if "cashflow_risk_level" in full_sku.columns and not full_sku.empty:
        risk_counts = full_sku["cashflow_risk_level"].value_counts().reset_index()
        risk_counts.columns = ["cashflow_risk_level", "sku_count"]
        fig = px.pie(risk_counts, names="cashflow_risk_level", values="sku_count", hole=0.45)
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=20, b=10))
        chart_cols[1].plotly_chart(fig, use_container_width=True)


def _render_table(df: pd.DataFrame, height: int = 520) -> None:
    st.caption(f"{len(df):,} 行")
    display, column_config = _prepare_dataframe_display(df)
    st.dataframe(display, column_config=column_config, use_container_width=True, height=height)


def main() -> None:
    st.set_page_config(page_title="Amazon Inventory Profit Analyzer", layout="wide")
    st.title("amazon-inventory-profit-analyzer")

    mapping_config, thresholds = load_configs()
    uploaded_file = st.file_uploader("上传数据", type=["xlsx", "xls"])
    if uploaded_file is None:
        return

    sheet_summaries = get_sheet_summaries(uploaded_file, mapping_config)
    sheet_names = [item["sheet_name"] for item in sheet_summaries]
    selected_sheet = sheet_names[0] if len(sheet_names) == 1 else st.selectbox("分析 Sheet", sheet_names)

    sheet_info = pd.DataFrame(
        [
            {
                "Sheet 名称": item["sheet_name"],
                "表头行": item["header_row"] + 1,
                "行数": item["rows"],
                "列数": item["columns"],
            }
            for item in sheet_summaries
        ]
    )
    st.dataframe(sheet_info, use_container_width=True, hide_index=True)

    with st.spinner("正在分析 SKU..."):
        raw_df, mapped_df, mapping_report = load_mapped_sheet(uploaded_file, selected_sheet, mapping_config)
        analysis = run_analysis(mapped_df, mapping_report, mapping_config, thresholds)

    missing_required = get_missing_required_fields(mapping_report, mapping_config)
    if missing_required:
        st.warning("缺失必填字段：" + "、".join(missing_required))

    full = analysis["full"]
    with st.sidebar:
        st.header("筛选")
        filter_columns = [
            "parent_asin",
            "spu",
            "product_line",
            "final_action",
            "priority",
            "inventory_status",
            "margin_level",
            "turnover_level",
            "cashflow_risk_level",
        ]
        filters = {
            column: st.multiselect(column, _options(full, column))
            for column in filter_columns
            if _options(full, column)
        }

    filtered_full = _apply_filters(full, filters)
    report_tables, overview_metrics, overview_summary = _build_filtered_tables(
        filtered_full,
        analysis["data_errors"],
        thresholds,
    )

    tabs = st.tabs(
        [
            "总览 Dashboard",
            "头部重点问题 SKU",
            "尾部异常 SKU",
            "高毛利慢周转 SKU",
            "紧急补货 SKU",
            "清货停补 SKU",
            "广告优化 SKU",
            "父体分析",
            "SPU / 品线分析",
            "SKU 完整判断",
            "数据异常",
            "导出 Excel",
        ]
    )

    with tabs[0]:
        _render_dashboard(report_tables["full_sku"], overview_metrics, overview_summary)
    with tabs[1]:
        _render_table(report_tables["head_problem_skus"])
    with tabs[2]:
        _render_table(report_tables["tail_abnormal_skus"])
    with tabs[3]:
        _render_table(report_tables["high_margin_slow_turnover"])
    with tabs[4]:
        _render_table(report_tables["urgent_replenishment"])
    with tabs[5]:
        _render_table(report_tables["clearance_stop"])
    with tabs[6]:
        _render_table(report_tables["ad_optimization"])
    with tabs[7]:
        _render_table(report_tables["parent_analysis"], height=420)
        _render_table(report_tables["parent_structure_anomalies"], height=360)
    with tabs[8]:
        _render_table(report_tables["spu_analysis"], height=420)
        _render_table(report_tables["product_line_analysis"], height=420)
    with tabs[9]:
        _render_table(report_tables["full_sku"])
    with tabs[10]:
        _render_table(report_tables["data_errors"])
    with tabs[11]:
        export_bytes = export_analysis_report(report_tables)
        filename = f"amazon_inventory_profit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        st.download_button(
            "导出分析 Excel",
            data=export_bytes,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        if st.button("保存到 output/reports"):
            output_path = OUTPUT_DIR / filename
            export_analysis_report(report_tables, output_path)
            st.success(f"已保存：{output_path}")


if __name__ == "__main__":
    main()
