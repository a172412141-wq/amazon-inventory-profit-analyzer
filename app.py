from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from modules.export_report import export_analysis_report
from modules.loader import get_sheet_summaries, load_mapped_sheet, load_yaml
from modules.parent_analysis import analyze_parent
from modules.pipeline import build_overview, prepare_full_sku_table, run_analysis
from modules.product_line_analysis import analyze_product_lines
from modules.sku_roles import build_sku_role_reports
from modules.spu_analysis import analyze_spu
from modules.validation import get_missing_required_fields
from visualizations import NAV_ITEMS, render_visualizations


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
PINNED_SKU_COLUMNS = [
    "sku",
    "role_daily_sales",
    "order_gross_profit",
    "order_gross_margin",
    "ad_spend",
    "available_stock_days",
    "stock_days",
    "available_stock_qty",
    "aged_inventory_90_plus",
    "aged_inventory_181_plus",
    "reason",
]
COLUMN_LABELS = {
    "sku": "SKU",
    "asin": "ASIN",
    "parent_asin": "父ASIN",
    "spu": "SPU",
    "product_line": "品线",
    "category_level_1": "一级分类",
    "product_name": "产品名称",
    "predicted_daily_sales": "预测日销量",
    "stock_days": "库存天数",
    "calculated_stock_days": "计算库存天数",
    "available_stock_qty": "可售库存量",
    "available_stock_days": "可售库存天数",
    "inbound_stock_days": "在途库存天数",
    "over_90_stock_qty": "90天+库存量",
    "over_90_inventory_ratio": "90天+库存占比",
    "recommended_replenishment_qty": "建议补货量",
    "total_supply_qty": "总供给量",
    "available_qty": "可用量",
    "inbound_qty": "在途量",
    "sales_7d_units": "7天销量",
    "sales_14d_units": "14天销量",
    "sales_7d_amount": "7天销售额",
    "sales_14d_amount": "14天销售额",
    "avg_sales_7d": "7天日均销量",
    "avg_sales_14d": "14天日均销量",
    "main_daily_sales": "主日均销量",
    "current_daily_sales_units": "目前日均销量",
    "current_daily_sales_amount": "目前日均销售额",
    "ideal_turnover_daily_units": "理想周转日销量",
    "role_daily_sales": "角色判断日均销量",
    "parent_avg_role_daily_sales": "父体平均日均销量",
    "parent_order_gross_margin": "父体毛利率",
    "parent_avg_sales_14d_units": "父体平均14天销量",
    "parent_avg_order_gross_margin": "父体平均毛利率",
    "recent_sales_trend": "近期销量趋势",
    "order_gross_profit": "订单毛利润",
    "order_gross_margin": "订单毛利率",
    "ad_spend": "广告花费",
    "ad_sales": "广告销售额",
    "ad_impressions": "广告曝光",
    "ad_clicks": "广告点击",
    "ad_orders": "广告订单",
    "total_orders": "总订单",
    "sessions_7d": "7天会话数",
    "sessions_14d": "14天会话数",
    "acos": "ACOS",
    "cpc": "CPC",
    "ctr": "CTR",
    "cvr": "CVR",
    "ad_cvr": "广告CVR",
    "ad_order_share": "广告订单占比",
    "aged_inventory_90_plus": "库龄超过90天合计数量",
    "aged_inventory_181_plus": "181天以上库龄库存",
    "aged_inventory_91_180": "91-180天库龄数量",
    "aged_inventory_181_270": "181-270天库龄数量",
    "aged_inventory_271_330": "271-330天库龄数量",
    "aged_inventory_331_365": "331-365天库龄数量",
    "aged_inventory_365_plus": "365天以上库龄数量",
    "inventory_value": "库存金额",
    "margin_level": "毛利等级",
    "turnover_level": "周转等级",
    "inventory_status": "库存状态",
    "profit_status": "利润状态",
    "ad_status": "广告状态",
    "cashflow_risk_level": "现金流风险等级",
    "sku_role": "SKU经营角色",
    "sku_role_candidates": "SKU角色候选",
    "sku_role_reason": "SKU角色原因",
    "role_parent_key": "角色父体分组",
    "parent_sku_count": "父体SKU数",
    "sku_sales_share_in_parent": "父体内销量占比",
    "sku_revenue_share_in_parent": "父体内销售额占比",
    "sku_ad_spend_share_in_parent": "父体内广告花费占比",
    "sku_profit_share_in_parent": "父体内利润占比",
    "sku_stock_share_in_parent": "父体内库存占比",
    "final_action": "最终动作",
    "priority": "优先级",
    "reason": "判断原因",
    "parent_status": "父体状态",
    "sku_count": "SKU数",
    "parent_count": "父体数",
    "weighted_stock_days": "加权库存天数",
    "structure_problem": "结构问题",
    "spu_status": "SPU状态",
    "line_status": "品线状态",
    "operation_recommendation": "运营建议",
    "dimension_type": "维度类型",
    "dimension_value": "维度值",
    "error_type": "异常类型",
    "error_level": "异常等级",
    "error_message": "异常说明",
}


@st.cache_data(show_spinner=False)
def load_configs(mapping_mtime: float, thresholds_mtime: float) -> tuple[dict[str, Any], dict[str, Any]]:
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


def _column_label(column: str) -> str:
    return COLUMN_LABELS.get(str(column), str(column))


def _metric_option_label(column: str) -> str:
    label = _column_label(column)
    return label if label == column else f"{label} ({column})"


def _pinned_columns_for(df: pd.DataFrame) -> list[str]:
    return [column for column in PINNED_SKU_COLUMNS if column in df.columns]


def _display_columns(
    df: pd.DataFrame,
    selected_extra_columns: list[str] | None = None,
    use_pinned_defaults: bool = True,
) -> list[str]:
    if not use_pinned_defaults:
        return list(df.columns)
    pinned_columns = _pinned_columns_for(df)
    selected = [column for column in (selected_extra_columns or []) if column in df.columns and column not in pinned_columns]
    if not pinned_columns:
        return list(df.columns)
    return pinned_columns + selected


def _prepare_dataframe_display(
    df: pd.DataFrame,
    selected_extra_columns: list[str] | None = None,
    use_pinned_defaults: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    display = df[_display_columns(df, selected_extra_columns, use_pinned_defaults)].copy()
    column_config: dict[str, Any] = {}
    pinned_columns = set(_pinned_columns_for(df)) if use_pinned_defaults else set()
    for column in display.columns:
        label = _column_label(str(column))
        pinned = str(column) in pinned_columns
        numeric_values = _numeric_display_series(display[column])
        if numeric_values is None or not numeric_values.notna().any():
            column_config[str(column)] = st.column_config.Column(label=label, pinned=pinned)
            continue
        if _is_percent_column(str(column)):
            display[column] = numeric_values * 100
            column_config[str(column)] = st.column_config.NumberColumn(label=label, format="%.2f%%", pinned=pinned)
        else:
            display[column] = numeric_values
            column_config[str(column)] = st.column_config.NumberColumn(label=label, format="%.2f", pinned=pinned)
    return display, column_config


def _display_selector_key(table_key: str) -> str:
    return f"display_columns_{table_key}"


def _selector_container(label: str):
    if hasattr(st, "popover"):
        return st.popover(label)
    return st.expander(label, expanded=False)


def _selected_extra_columns(df: pd.DataFrame, table_key: str, enabled: bool) -> list[str]:
    pinned_columns = _pinned_columns_for(df)
    extra_columns = [column for column in df.columns if column not in pinned_columns]
    if not enabled or not pinned_columns or not extra_columns:
        return []

    key = _display_selector_key(table_key)
    selected = st.session_state.get(key) or []
    valid_selected = [column for column in selected if column in extra_columns]
    if valid_selected != selected:
        st.session_state[key] = valid_selected

    with _selector_container("显示指标"):
        st.caption("左侧固定列始终显示；这里选择需要临时查看的其他指标。")
        return st.multiselect(
            "选择额外指标",
            extra_columns,
            key=key,
            format_func=_metric_option_label,
        )


def _options(df: pd.DataFrame, column: str) -> list[str]:
    if column not in df.columns:
        return []
    values = df[column].dropna().astype(str).map(str.strip)
    return sorted(value for value in values.unique().tolist() if value and value.lower() not in {"nan", "none"})


def _normalize_filter_values(values: list[str] | None) -> list[str]:
    if not values:
        return []
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text.lower() not in {"nan", "none"}:
            result.append(text)
    return result


def _apply_filters(df: pd.DataFrame, filters: dict[str, list[str]]) -> pd.DataFrame:
    result = df.copy()
    for column, selected in filters.items():
        selected_values = _normalize_filter_values(selected)
        if selected_values and column in result.columns:
            result = result[result[column].astype(str).str.strip().isin(selected_values)]
    return result


def _filter_key(column: str) -> str:
    return f"filter_{column}"


def _filter_options_with_context(
    df: pd.DataFrame,
    filter_columns: list[str],
    filters: dict[str, list[str]],
) -> dict[str, list[str]]:
    normalized_filters = {
        column: _normalize_filter_values(selected)
        for column, selected in filters.items()
        if _normalize_filter_values(selected)
    }
    options_by_column: dict[str, list[str]] = {}
    for column in filter_columns:
        context_filters = {
            filter_column: selected
            for filter_column, selected in normalized_filters.items()
            if filter_column != column
        }
        scoped = _apply_filters(df, context_filters)
        options_by_column[column] = _options(scoped, column)
    return options_by_column


def _prune_filter_values(selected: list[str] | None, options: list[str]) -> list[str]:
    selected = _normalize_filter_values(selected)
    option_set = set(options)
    return [value for value in selected if value in option_set]


def _session_filters(filter_columns: list[str]) -> dict[str, list[str]]:
    return {
        column: _normalize_filter_values(st.session_state.get(_filter_key(column)))
        for column in filter_columns
    }


def _sync_linked_filter_state(
    df: pd.DataFrame,
    filter_columns: list[str],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    filters = _session_filters(filter_columns)
    options_by_column = _filter_options_with_context(df, filter_columns, filters)
    for _ in range(len(filter_columns) + 1):
        changed = False
        for column in filter_columns:
            pruned = _prune_filter_values(filters.get(column), options_by_column.get(column, []))
            if pruned != filters.get(column, []):
                filters[column] = pruned
                st.session_state[_filter_key(column)] = pruned
                changed = True
        if not changed:
            break
        options_by_column = _filter_options_with_context(df, filter_columns, filters)
    return filters, options_by_column


def _render_linked_filters(df: pd.DataFrame, filter_columns: list[str]) -> dict[str, list[str]]:
    filters, options_by_column = _sync_linked_filter_state(df, filter_columns)
    rendered_filters: dict[str, list[str]] = {}
    for column in filter_columns:
        options = options_by_column.get(column, [])
        if not options:
            continue
        selected = st.multiselect(column, options, key=_filter_key(column))
        selected_values = _normalize_filter_values(selected)
        if selected_values:
            rendered_filters[column] = selected_values
    return rendered_filters


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
    role_reports = build_sku_role_reports(full, thresholds)
    parent_analysis, parent_structure = analyze_parent(full, thresholds)
    spu_analysis = analyze_spu(full, thresholds)
    product_line_analysis = analyze_product_lines(full, thresholds)
    full_sku = prepare_full_sku_table(full)
    metrics, summary, overview = build_overview(full_sku, role_reports, thresholds)
    visible_skus = set(full_sku["sku"].astype(str)) if "sku" in full_sku.columns else set()
    tables = {
        "overview": overview,
        "traffic_skus": role_reports["traffic_skus"],
        "main_skus": role_reports["main_skus"],
        "profit_skus": role_reports["profit_skus"],
        "low_efficiency_skus": role_reports["low_efficiency_skus"],
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
        ("CVR", True, False),
        ("广告CVR", True, False),
        ("订单毛利润", False, True),
        ("平均毛利率", True, False),
        ("总库存/总供给", False, False),
        ("可售库存天数", False, False),
        ("在途库存天数", False, False),
        ("61-90天可售库存量", False, False),
        ("91-180天可售库存量", False, False),
        ("180天+可售库存量", False, False),
        ("库龄超过90天合计数量", False, False),
        ("90天+库存占比", True, False),
        ("建议补货总量", False, False),
        ("清货风险 SKU 数", False, False),
        ("禁止补货 SKU 数", False, False),
        ("立即补货 SKU 数", False, False),
        ("引流 SKU 数", False, False),
        ("主力 SKU 数", False, False),
        ("利润 SKU 数", False, False),
        ("低效异常 SKU 数", False, False),
    ]
    for start in range(0, len(metric_specs), 4):
        cols = st.columns(4)
        for col, (label, is_percent, is_money) in zip(cols, metric_specs[start : start + 4]):
            col.metric(label, _format_metric(metrics.get(label), is_percent, is_money))

    st.markdown(summary.replace("\n", "\n\n"))


def _render_table(
    df: pd.DataFrame,
    height: int = 520,
    table_key: str = "table",
    enable_metric_selector: bool = False,
) -> None:
    st.caption(f"{len(df):,} 行")
    selected_extra_columns = _selected_extra_columns(df, table_key, enable_metric_selector)
    display, column_config = _prepare_dataframe_display(
        df,
        selected_extra_columns,
        use_pinned_defaults=enable_metric_selector,
    )
    st.dataframe(
        display,
        column_config=column_config,
        use_container_width=True,
        height=height,
        key=f"dataframe_{table_key}",
    )


def main() -> None:
    st.set_page_config(page_title="Amazon Inventory Profit Analyzer", layout="wide")
    st.title("amazon-inventory-profit-analyzer")

    mapping_path = CONFIG_DIR / "column_mapping.yaml"
    thresholds_path = CONFIG_DIR / "thresholds.yaml"
    mapping_config, thresholds = load_configs(mapping_path.stat().st_mtime, thresholds_path.stat().st_mtime)
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
            "asin",
            "spu",
            "product_line",
            "sku_role",
            "final_action",
            "priority",
            "inventory_status",
            "margin_level",
            "turnover_level",
            "cashflow_risk_level",
        ]
        filters = _render_linked_filters(full, filter_columns)

    filtered_full = _apply_filters(full, filters)
    report_tables, overview_metrics, overview_summary = _build_filtered_tables(
        filtered_full,
        analysis["data_errors"],
        thresholds,
    )

    tabs = st.tabs(NAV_ITEMS)

    with tabs[0]:
        _render_dashboard(report_tables["full_sku"], overview_metrics, overview_summary)
        render_visualizations("总览 Dashboard", report_tables)
    with tabs[1]:
        _render_table(report_tables["traffic_skus"], table_key="traffic_skus", enable_metric_selector=True)
        render_visualizations("引流 SKU", report_tables)
    with tabs[2]:
        _render_table(report_tables["main_skus"], table_key="main_skus", enable_metric_selector=True)
        render_visualizations("主力 SKU", report_tables)
    with tabs[3]:
        _render_table(report_tables["profit_skus"], table_key="profit_skus", enable_metric_selector=True)
        render_visualizations("利润 SKU", report_tables)
    with tabs[4]:
        _render_table(report_tables["low_efficiency_skus"], table_key="low_efficiency_skus", enable_metric_selector=True)
        render_visualizations("低效异常 SKU", report_tables)
    with tabs[5]:
        _render_table(report_tables["parent_analysis"], height=420, table_key="parent_analysis")
        _render_table(report_tables["parent_structure_anomalies"], height=360, table_key="parent_structure_anomalies")
        render_visualizations("父体分析", report_tables)
    with tabs[6]:
        _render_table(report_tables["spu_analysis"], height=420, table_key="spu_analysis")
        _render_table(report_tables["product_line_analysis"], height=420, table_key="product_line_analysis")
        render_visualizations("SPU / 品线分析", report_tables)
    with tabs[7]:
        _render_table(report_tables["full_sku"], table_key="full_sku", enable_metric_selector=True)
        render_visualizations("SKU 完整判断", report_tables)
    with tabs[8]:
        _render_table(report_tables["data_errors"], table_key="data_errors")
        render_visualizations("数据异常", report_tables)
    with tabs[9]:
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
        render_visualizations("导出 Excel", report_tables)


if __name__ == "__main__":
    main()
