from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from modules.export_report import export_analysis_report
from modules.loader import get_sheet_summaries, load_mapped_sheet, load_yaml
from modules.parent_analysis import analyze_parent
from modules.periods import (
    DEFAULT_SALES_PERIOD,
    SALES_PERIOD_OPTIONS,
    normalize_sales_period,
    sales_period_amount_column,
    sales_period_label,
    sales_period_units_column,
)
from modules.pipeline import build_overview, prepare_full_sku_table, run_analysis
from modules.product_line_analysis import analyze_product_lines
from modules.product_line_diagnosis import build_product_line_diagnosis
from modules.sku_roles import build_sku_role_reports
from modules.spu_analysis import analyze_spu
from modules.validation import get_missing_required_fields
from visualizations import render_visualizations


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
    "acoas",
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
    "acos",
    "acoas",
    "available_stock_days",
    "stock_days",
    "available_stock_qty",
    "aged_inventory_90_plus",
    "aged_inventory_181_plus",
    "reason",
]
FILTER_COLUMNS = [
    "parent_asin",
    "asin",
    "spu",
    "product_line",
    "category_level_3",
    "sku_role",
    "final_action",
    "priority",
    "inventory_status",
    "margin_level",
    "turnover_level",
    "cashflow_risk_level",
]
FILTER_LABELS = {
    "parent_asin": "父ASIN",
    "product_line": "品线",
    "category_level_3": "尺寸",
    "sku_role": "SKU角色定位",
    "priority": "处理优先级",
    "inventory_status": "库存天数情况",
    "margin_level": "毛利率水平",
    "turnover_level": "周转水平",
    "cashflow_risk_level": "现金流风险",
}
TAB_LABELS = [
    "经营总览",
    "引流 SKU",
    "主力 SKU",
    "利润 SKU",
    "低效 SKU",
    "父体",
    "SPU / 品线",
    "全部 SKU",
    "数据质量",
    "导出报告",
]
SECTION_INTROS = {
    "经营总览": ("经营总览", "先看利润、周转和库存风险，再决定补货、清货与广告资源分配。"),
    "引流 SKU": ("引流 SKU", "识别承担流量入口的 SKU，重点检查广告投入是否带来有效销售与父体协同。"),
    "主力 SKU": ("主力 SKU", "保护销量与利润共同领先的核心 SKU，优先避免断货和资源分散。"),
    "利润 SKU": ("利润 SKU", "寻找高利润贡献 SKU，在库存健康和广告可控的前提下评估扩量。"),
    "低效 SKU": ("低效异常 SKU", "集中处理未形成明确角色价值的 SKU，减少库存、广告和管理资源浪费。"),
    "父体": ("父体分析", "检查父体内部的销量、库存、利润和广告结构是否匹配。"),
    "SPU / 品线": ("SPU / 品线分析", "从聚合表现进入经营关系诊断，形成带责任人与时间要求的行动清单。"),
    "全部 SKU": ("SKU 完整判断", "查看每个 SKU 的完整指标、系统动作、处理优先级与判断依据。"),
    "数据质量": ("数据质量", "先修复高优先级数据问题，避免错误字段和口径污染经营结论。"),
    "导出报告": ("导出报告", "下载当前筛选范围的完整分析结果，或保存到本地报告目录。"),
}
APP_STYLES = """
<style>
    :root {
        --brand-ink: #172033;
        --brand-blue: #315EFB;
        --brand-soft: #EEF3FF;
        --surface: #FFFFFF;
        --line: #E4E9F2;
        --muted: #667085;
    }
    .stApp { background: #F7F9FC; }
    .block-container { max-width: 1480px; padding-top: 2rem; padding-bottom: 4rem; }
    [data-testid="stSidebar"] { border-right: 1px solid var(--line); background: #FBFCFE; }
    [data-testid="stSidebar"] .block-container { padding-top: 1.5rem; }
    [data-testid="stMetric"] {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 16px 18px;
        box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    }
    [data-testid="stMetricLabel"] { color: var(--muted); }
    [data-testid="stMetricValue"] { color: var(--brand-ink); }
    [data-testid="stFileUploaderDropzone"] {
        background: var(--surface);
        border: 1.5px dashed #AFC0E8;
        border-radius: 16px;
        min-height: 112px;
    }
    [data-baseweb="tab-list"] { gap: 8px; }
    [data-baseweb="tab"] {
        border-radius: 10px 10px 0 0;
        padding-left: 14px;
        padding-right: 14px;
    }
    .product-hero {
        padding: 28px 30px;
        margin-bottom: 20px;
        border: 1px solid #DCE5FB;
        border-radius: 20px;
        background: linear-gradient(135deg, #FFFFFF 0%, #F0F4FF 100%);
        box-shadow: 0 8px 24px rgba(49, 94, 251, 0.08);
    }
    .product-eyebrow {
        color: var(--brand-blue);
        font-size: 13px;
        font-weight: 700;
        letter-spacing: .08em;
        text-transform: uppercase;
        margin-bottom: 8px;
    }
    .product-title {
        color: var(--brand-ink);
        font-size: clamp(30px, 4vw, 46px);
        line-height: 1.15;
        font-weight: 760;
        margin: 0 0 10px 0;
    }
    .product-subtitle {
        max-width: 820px;
        color: var(--muted);
        font-size: 16px;
        line-height: 1.7;
        margin: 0;
    }
    .product-tags { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
    .product-tag {
        color: #2949A3;
        background: var(--brand-soft);
        border: 1px solid #D9E4FF;
        border-radius: 999px;
        padding: 6px 10px;
        font-size: 13px;
        font-weight: 600;
    }
    .step-card {
        min-height: 132px;
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 18px;
    }
    .step-number { color: var(--brand-blue); font-size: 12px; font-weight: 800; letter-spacing: .08em; }
    .step-title { color: var(--brand-ink); font-size: 17px; font-weight: 700; margin: 8px 0 6px; }
    .step-copy { color: var(--muted); font-size: 14px; line-height: 1.55; }
    .section-intro { margin: 8px 0 20px; }
    .section-intro h2 { color: var(--brand-ink); margin-bottom: 4px; }
    .section-intro p { color: var(--muted); margin: 0; }
    .metric-group-title { color: #344054; font-size: 14px; font-weight: 700; margin: 20px 0 10px; }
    .line-card {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 16px 18px;
        margin: 12px 0;
        box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    }
    .line-card-header { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 8px; margin-bottom: 12px; }
    .line-card-title { color: var(--brand-ink); font-size: 18px; font-weight: 760; }
    .line-card-badge { color: #2949A3; background: var(--brand-soft); border: 1px solid #D9E4FF; border-radius: 999px; padding: 4px 8px; font-size: 12px; font-weight: 700; }
    .line-card-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
    .line-card-section { border-top: 1px solid #EEF2F7; padding-top: 10px; min-width: 0; }
    .line-card-section:first-child { border-top: 0; padding-top: 0; }
    .line-card-section h4 { color: #344054; font-size: 13px; margin: 0 0 8px; }
    .line-card-section p { color: var(--muted); font-size: 13px; line-height: 1.55; margin: 4px 0; }
    .line-card-value { color: var(--brand-ink); font-weight: 760; }
    @media (max-width: 1100px) { .line-card-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
    @media (max-width: 680px) { .line-card-grid { grid-template-columns: 1fr; } }
</style>
"""
COLUMN_LABELS = {
    "sku": "SKU",
    "asin": "ASIN",
    "parent_asin": "父ASIN",
    "spu": "SPU",
    "product_line": "品线",
    "size": "尺寸/规格",
    "category_level_1": "一级分类",
    "category_level_3": "三级分类",
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
    "selected_sales_units": "当前周期销量",
    "selected_sales_amount": "当前周期销售额",
    "selected_daily_sales_units": "当前周期日均销量",
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
    "acoas": "ACOAS",
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


def _inject_app_styles() -> None:
    st.markdown(APP_STYLES, unsafe_allow_html=True)


def _render_app_header() -> None:
    st.markdown(
        """
        <section class="product-hero">
            <div class="product-eyebrow">AMAZON 经营决策工作台</div>
            <h1 class="product-title">亚马逊库存与利润决策台</h1>
            <p class="product-subtitle">把补货、库存、广告和利润数据放到同一套经营逻辑里，快速识别该补、该停、该清和该加资源的 SKU。</p>
            <div class="product-tags">
                <span class="product-tag">现金流优先</span>
                <span class="product-tag">SKU 角色定位</span>
                <span class="product-tag">父体与品线诊断</span>
                <span class="product-tag">行动清单</span>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_empty_state() -> None:
    st.markdown("#### 上传后，你会得到什么")
    steps = [
        ("01", "识别数据", "自动识别真实表头和中文字段，并提示缺失、重复或口径异常。"),
        ("02", "形成判断", "按周转、利润和广告效率生成 SKU 主动作、角色定位和处理优先级。"),
        ("03", "落到行动", "汇总父体、SPU 与品线问题，生成可筛选、可导出的经营报告。"),
    ]
    columns = st.columns(3)
    for column, (number, title, copy) in zip(columns, steps):
        column.markdown(
            f'<div class="step-card"><div class="step-number">STEP {number}</div><div class="step-title">{title}</div><div class="step-copy">{copy}</div></div>',
            unsafe_allow_html=True,
        )
    st.caption("数据在当前应用会话中处理。建议上传单行代表一个 SKU 的 .xlsx 文件。")
    with st.expander("查看上传前检查清单"):
        st.markdown(
            """
            - 至少包含 SKU、销量、库存天数、补货量、毛利润、毛利率、广告花费、广告销售额和 ACOS。
            - `总供给` 与 `可用量` 至少提供一个；父 ASIN、SPU、品线和尺寸可增强横向诊断。
            - 支持表头不在首行、中文字段名，以及 `30`、`30%`、`0.3` 三种百分比写法。
            """
        )


def _render_section_intro(section: str) -> None:
    title, description = SECTION_INTROS[section]
    st.markdown(
        f'<div class="section-intro"><h2>{title}</h2><p>{description}</p></div>',
        unsafe_allow_html=True,
    )


def _clear_filter_state() -> None:
    for column in FILTER_COLUMNS:
        st.session_state.pop(_filter_key(column), None)


def _render_sales_period_filter() -> str:
    labels = {period: sales_period_label(period) for period in SALES_PERIOD_OPTIONS}
    current = normalize_sales_period(st.session_state.get("sales_period", DEFAULT_SALES_PERIOD))
    st.markdown("#### 快速周期")
    if hasattr(st, "segmented_control"):
        selected_label = st.segmented_control(
            "数据周期",
            options=[labels[period] for period in SALES_PERIOD_OPTIONS],
            default=labels[current],
            key="sales_period_segmented",
        )
        selected = next((period for period, label in labels.items() if label == selected_label), DEFAULT_SALES_PERIOD)
        st.session_state["sales_period"] = selected
        return selected
    selected = st.radio(
        "数据周期",
        SALES_PERIOD_OPTIONS,
        index=SALES_PERIOD_OPTIONS.index(current),
        format_func=lambda period: labels[period],
        horizontal=True,
        key="sales_period",
    )
    return normalize_sales_period(selected)


def _format_metric(value: Any, percent: bool = False, money: bool = False) -> str:
    if pd.isna(value):
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not np.isfinite(number):
        return "∞" if number > 0 else "-"
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


def _filter_label(column: str) -> str:
    return FILTER_LABELS.get(column, column)


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
        selected = st.multiselect(_filter_label(column), options, key=_filter_key(column))
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
    sales_period: str,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any], str]:
    role_reports = build_sku_role_reports(full, thresholds)
    parent_analysis, parent_structure = analyze_parent(full, thresholds, sales_period=sales_period)
    spu_analysis = analyze_spu(full, thresholds, sales_period=sales_period)
    product_line_analysis = analyze_product_lines(full, thresholds, sales_period=sales_period)
    full_sku = prepare_full_sku_table(full)
    metrics, summary, overview = build_overview(full_sku, role_reports, thresholds, sales_period=sales_period)
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


def _render_dashboard(full_sku: pd.DataFrame, metrics: dict[str, Any], summary: str, sales_period: str) -> None:
    period_label = sales_period_label(sales_period)
    metric_groups = [
        (
            "核心经营结果",
            [
                (f"{period_label}销售额", "当前周期销售额", False, True),
                ("订单毛利润", "订单毛利润", False, True),
                ("平均毛利率", "平均毛利率", True, False),
                ("整体 ACOAS", "整体 ACOAS", True, False),
            ],
        ),
        (
            "库存与现金流",
            [
                ("可售库存天数", "可售库存天数", False, False),
                ("在途库存天数", "在途库存天数", False, False),
                ("90天+库存占比", "90天+库存占比", True, False),
                ("库龄超过90天合计数量", "库龄超过90天合计数量", False, False),
            ],
        ),
        (
            "当前行动队列",
            [
                ("紧急补货 SKU 数", "紧急补货 SKU 数", False, False),
                ("清货/停补 SKU 数", "清货/停补 SKU 数", False, False),
                ("主力 SKU 数", "主力 SKU 数", False, False),
                ("低效异常 SKU 数", "低效异常 SKU 数", False, False),
            ],
        ),
    ]
    for group_title, metric_specs in metric_groups:
        st.markdown(f'<div class="metric-group-title">{group_title}</div>', unsafe_allow_html=True)
        cols = st.columns(4)
        for col, (label, metric_key, is_percent, is_money) in zip(cols, metric_specs):
            col.metric(label, _format_metric(metrics.get(metric_key), is_percent, is_money))

    st.markdown("#### 自动经营摘要")
    st.info(summary)

    detail_specs = [
        ("SKU 总数", "SKU 总数", False, False),
        ("父体数", "父体数", False, False),
        ("SPU 数", "SPU 数", False, False),
        ("品线数", "品线数", False, False),
        (f"{period_label}销售额", "当前周期销售额", False, True),
        (f"{period_label}销量", "当前周期销量", False, False),
        (f"{period_label}日均销量", "当前周期日均销量", False, False),
        (f"{period_label}日均销售额", "当前周期日均销售额", False, True),
        ("14天销售额", "14天销售额", False, True),
        ("14天销量", "14天销量", False, False),
        ("理想周转情况下日销量", "理想周转情况下日销量", False, False),
        ("总广告花费", "总广告花费", False, True),
        ("广告销售额", "广告销售额", False, True),
        ("整体 ACOS", "整体 ACOS", True, False),
        ("整体 ACOAS", "整体 ACOAS", True, False),
        ("广告订单占比", "广告订单占比", True, False),
        ("CPC", "CPC", False, True),
        ("CTR", "CTR", True, False),
        ("CVR", "CVR", True, False),
        ("广告CVR", "广告CVR", True, False),
        ("订单毛利润", "订单毛利润", False, True),
        ("平均毛利率", "平均毛利率", True, False),
        ("总库存/总供给", "总库存/总供给", False, False),
        ("可售库存天数", "可售库存天数", False, False),
        ("在途库存天数", "在途库存天数", False, False),
        ("61-90天可售库存量", "61-90天可售库存量", False, False),
        ("91-180天可售库存量", "91-180天可售库存量", False, False),
        ("180天+可售库存量", "180天+可售库存量", False, False),
        ("库龄超过90天合计数量", "库龄超过90天合计数量", False, False),
        ("90天+库存占比", "90天+库存占比", True, False),
        ("建议补货总量", "建议补货总量", False, False),
        ("清货风险 SKU 数", "清货风险 SKU 数", False, False),
        ("禁止补货 SKU 数", "禁止补货 SKU 数", False, False),
        ("立即补货 SKU 数", "立即补货 SKU 数", False, False),
        ("引流 SKU 数", "引流 SKU 数", False, False),
        ("主力 SKU 数", "主力 SKU 数", False, False),
        ("利润 SKU 数", "利润 SKU 数", False, False),
        ("低效异常 SKU 数", "低效异常 SKU 数", False, False),
    ]
    with st.expander("查看全部经营指标"):
        details = [
            {"指标": label, "数值": _format_metric(metrics.get(metric_key), is_percent, is_money)}
            for label, metric_key, is_percent, is_money in detail_specs
        ]
        st.dataframe(pd.DataFrame(details), use_container_width=True, hide_index=True, height=460)


def _render_table(
    df: pd.DataFrame,
    height: int = 520,
    table_key: str = "table",
    enable_metric_selector: bool = False,
) -> None:
    if df.empty:
        st.info("当前筛选范围内暂无数据。可调整左侧筛选条件后重试。")
        return
    st.caption(f"当前显示 {len(df):,} 行")
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


def _product_line_scope(full: pd.DataFrame, product_line: str) -> pd.DataFrame:
    if "product_line" not in full.columns:
        return pd.DataFrame(columns=full.columns)
    values = full["product_line"].astype("string").fillna("").str.strip()
    return full[values == str(product_line).strip()].copy()


def _text_count(df: pd.DataFrame, column: str) -> int:
    if column not in df.columns:
        return 0
    values = df[column].astype("string").fillna("").str.strip()
    return int(values[~values.isin(["", "nan", "none", "<NA>"])].nunique())


def _product_line_card_rows(
    full: pd.DataFrame,
    product_line_summary: pd.DataFrame,
    sales_period: str,
) -> list[dict[str, Any]]:
    if full.empty or product_line_summary.empty or "product_line" not in full.columns:
        return []
    summary = product_line_summary.copy()
    if "dimension_type" in summary.columns:
        summary = summary[summary["dimension_type"].astype("string").fillna("").eq("product_line")]
    if summary.empty:
        return []
    if "dimension_value" not in summary.columns:
        summary["dimension_value"] = summary.get("product_line", "")
    amount_column = "selected_sales_amount" if "selected_sales_amount" in summary.columns else sales_period_amount_column(sales_period)
    if amount_column in summary.columns:
        summary = summary.assign(_sort_sales=pd.to_numeric(summary[amount_column], errors="coerce").fillna(0.0))
        summary = summary.sort_values("_sort_sales", ascending=False)

    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        line = str(row.get("dimension_value", row.get("product_line", ""))).strip()
        if not line or line.lower() in {"nan", "none", "<na>"}:
            continue
        line_df = _product_line_scope(full, line)
        final_actions = line_df.get("final_action", pd.Series(dtype="string")).astype("string").fillna("").str.strip()
        priorities = line_df.get("priority", pd.Series(dtype="string")).astype("string").fillna("").str.strip()
        action_counts = final_actions[final_actions != ""].value_counts().head(3)
        rows.append(
            {
                "product_line": line,
                "line_status": row.get("line_status", ""),
                "operation_recommendation": row.get("operation_recommendation", ""),
                "sales_amount": row.get("selected_sales_amount", row.get(sales_period_amount_column(sales_period), np.nan)),
                "sales_units": row.get("selected_sales_units", row.get(sales_period_units_column(sales_period), np.nan)),
                "gross_profit": row.get("order_gross_profit", np.nan),
                "gross_margin": row.get("order_gross_margin", np.nan),
                "acoas": row.get("acoas", np.nan),
                "weighted_stock_days": row.get("weighted_stock_days", np.nan),
                "available_stock_qty": row.get("available_stock_qty", np.nan),
                "aged_inventory_90_plus": row.get("aged_inventory_90_plus", np.nan),
                "p0_p1_count": int(priorities.isin(["P0", "P1"]).sum()),
                "urgent_replenishment_count": int(final_actions.isin(["立即补货", "优先补货"]).sum()),
                "clearance_stop_count": int(final_actions.isin(["清货处理", "禁止补货", "高毛利停补"]).sum()),
                "action_summary": "、".join(f"{action} {count}个" for action, count in action_counts.items()) or "暂无系统动作",
                "sku_count": int(row.get("sku_count", len(line_df))),
                "parent_count": int(row.get("parent_count", _text_count(line_df, "parent_asin")) or 0),
                "spu_count": _text_count(line_df, "spu"),
            }
        )
    return rows


def _render_product_line_cards(
    full: pd.DataFrame,
    product_line_summary: pd.DataFrame,
    sales_period: str,
) -> None:
    rows = _product_line_card_rows(full, product_line_summary, sales_period)
    if not rows:
        st.info("缺少品线字段，暂时无法生成品线卡片。")
        return
    period_label = sales_period_label(sales_period)
    for row in rows:
        status = str(row.get("line_status") or "待判断")
        recommendation = str(row.get("operation_recommendation") or "待复核")
        st.markdown(
            f"""
            <section class="line-card">
                <div class="line-card-header">
                    <div class="line-card-title">{escape(str(row["product_line"]))}</div>
                    <div class="line-card-badge">{escape(status)} · {escape(recommendation)}</div>
                </div>
                <div class="line-card-grid">
                    <div class="line-card-section">
                        <h4>核心经营结果</h4>
                        <p>{period_label}销售额 <span class="line-card-value">{_format_metric(row["sales_amount"], money=True)}</span></p>
                        <p>订单毛利润 <span class="line-card-value">{_format_metric(row["gross_profit"], money=True)}</span></p>
                        <p>毛利率 <span class="line-card-value">{_format_metric(row["gross_margin"], percent=True)}</span> · ACOAS <span class="line-card-value">{_format_metric(row["acoas"], percent=True)}</span></p>
                    </div>
                    <div class="line-card-section">
                        <h4>库存与现金流</h4>
                        <p>加权库存天数 <span class="line-card-value">{_format_metric(row["weighted_stock_days"])}</span></p>
                        <p>可售库存 <span class="line-card-value">{_format_metric(row["available_stock_qty"])}</span></p>
                        <p>90天+库龄 <span class="line-card-value">{_format_metric(row["aged_inventory_90_plus"])}</span></p>
                    </div>
                    <div class="line-card-section">
                        <h4>当前行动队列</h4>
                        <p>P0/P1 <span class="line-card-value">{row["p0_p1_count"]}</span> 个</p>
                        <p>紧急补货 <span class="line-card-value">{row["urgent_replenishment_count"]}</span> 个 · 清货/停补 <span class="line-card-value">{row["clearance_stop_count"]}</span> 个</p>
                        <p>{escape(str(row["action_summary"]))}</p>
                    </div>
                    <div class="line-card-section">
                        <h4>数据</h4>
                        <p>SKU <span class="line-card-value">{row["sku_count"]}</span> 个 · 父体 <span class="line-card-value">{row["parent_count"]}</span> 个</p>
                        <p>SPU <span class="line-card-value">{row["spu_count"]}</span> 个 · {period_label}销量 <span class="line-card-value">{_format_metric(row["sales_units"])}</span></p>
                        <p>ACOAS = 广告花费 / {period_label}总销售额</p>
                    </div>
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )


def _format_core_metric_value(metric: str, value: Any) -> str:
    if metric in {"利润率", "广告花费占比"}:
        return _format_metric(value, percent=True)
    if metric in {"销售额", "利润额", "广告花费"}:
        return _format_metric(value, money=True)
    return _format_metric(value)


def _render_core_metrics_table(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("当前品线暂无核心指标。")
        return
    display = df.copy()
    display["数值"] = display.apply(lambda row: _format_core_metric_value(str(row.get("指标", "")), row.get("数值")), axis=1)
    st.dataframe(display, use_container_width=True, hide_index=True, height=260)


def _render_narrative_summary(summary: dict[str, str], sections: list[tuple[str, str]]) -> None:
    headline = summary.get("headline", "")
    if headline:
        st.info(headline)
    for label, key in sections:
        text = summary.get(key, "")
        if text:
            st.markdown(f"**{label}**  \n{text}")


def _render_product_line_diagnosis(full: pd.DataFrame, thresholds: dict[str, Any], sales_period: str) -> None:
    st.divider()
    st.subheader("品线经营诊断")
    product_lines = _options(full, "product_line")
    if not product_lines:
        st.info("缺少品线字段或当前筛选下没有可分析的品线。")
        return

    selected_line = st.selectbox("选择一条品线", product_lines, key="product_line_diagnosis_line")
    owner_col, date_col = st.columns(2)
    default_owner = owner_col.text_input("默认负责人", value="待指定", key="product_line_todo_owner")
    todo_start_date = date_col.date_input("计划开始日期", value=datetime.now().date(), key="product_line_todo_start_date")
    diagnosis = build_product_line_diagnosis(
        full,
        selected_line,
        owner=default_owner,
        start_date=todo_start_date,
        thresholds=thresholds,
        sales_period=sales_period,
    )

    st.markdown("### 一、管理层汇报摘要")
    _render_narrative_summary(
        diagnosis["executive_summary"],
        [
            ("经营概况", "operating_snapshot"),
            ("优先风险", "priority_risks"),
            ("增长机会", "growth_opportunities"),
            ("结论边界", "data_boundaries"),
        ],
    )

    st.markdown("### 二、数据可信度")
    _render_table(diagnosis["data_credibility"], height=300, table_key="product_line_data_credibility")

    st.markdown("### 三、品线经营结论展开")
    for index, sentence in enumerate(diagnosis["conclusions"], start=1):
        st.markdown(f"{index}. {sentence}")

    st.markdown("### 四、品线核心指标")
    _render_core_metrics_table(diagnosis["core_metrics"])

    st.markdown("### 五、经营关系诊断")
    _render_table(diagnosis["relationship_diagnostics"], height=440, table_key="product_line_relationship_diagnostics")

    st.markdown("### 六、SKU角色结构")
    _render_table(diagnosis["role_structure"], height=300, table_key="product_line_role_structure")

    with st.expander("规模贡献明细", expanded=False):
        _render_table(diagnosis["sku_contribution"], height=420, table_key="product_line_sku_contribution")

    st.markdown("### 七、重点问题与机会SKU")
    st.markdown("#### 重点问题SKU")
    if diagnosis["problem_skus"].empty:
        st.info("当前品线暂无明确重点问题 SKU。")
    else:
        _render_table(diagnosis["problem_skus"], height=480, table_key="product_line_problem_skus")

    st.markdown("#### 重点机会SKU")
    if diagnosis["opportunity_skus"].empty:
        st.info("当前品线暂无高置信度机会 SKU。")
    else:
        _render_table(diagnosis["opportunity_skus"], height=420, table_key="product_line_opportunity_skus")

    st.markdown("### 八、品线 ToDo 执行汇报")
    todo_list = diagnosis["todo_list"]
    _render_narrative_summary(
        diagnosis["todo_summary"],
        [
            ("优先级", "priority_summary"),
            ("责任分工", "ownership_summary"),
            ("时间要求", "schedule_summary"),
            ("执行重点", "execution_focus"),
        ],
    )
    if todo_list.empty:
        st.info("当前品线暂无可生成的 ToDo。")
    else:
        st.markdown("#### ToDo 执行明细")
        editable_columns = {"状态", "负责人", "开始时间", "完成时间"}
        disabled_columns = [column for column in todo_list.columns if column not in editable_columns]
        st.data_editor(
            todo_list,
            use_container_width=True,
            hide_index=True,
            height=520,
            num_rows="fixed",
            disabled=disabled_columns,
            column_config={
                "状态": st.column_config.SelectboxColumn(
                    "状态",
                    options=["待开始", "进行中", "已完成", "已暂停"],
                    required=True,
                ),
            },
            key=f"product_line_todo_editor_{selected_line}",
        )


def main() -> None:
    st.set_page_config(
        page_title="亚马逊库存与利润决策台",
        page_icon="📦",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _inject_app_styles()
    _render_app_header()

    mapping_path = CONFIG_DIR / "column_mapping.yaml"
    thresholds_path = CONFIG_DIR / "thresholds.yaml"
    mapping_config, thresholds = load_configs(mapping_path.stat().st_mtime, thresholds_path.stat().st_mtime)
    st.markdown("### 上传经营数据")
    st.caption("支持 Excel 文件；系统会自动识别表头、映射字段并检查数据质量。")
    uploaded_file = st.file_uploader(
        "选择补货、库存、广告与利润数据文件",
        type=["xlsx", "xls"],
        help="单个文件最大 200MB，建议每行对应一个 SKU。",
    )
    if uploaded_file is None:
        _render_empty_state()
        return

    st.success(f"已载入：{uploaded_file.name}")
    sheet_summaries = get_sheet_summaries(uploaded_file, mapping_config)
    sheet_names = [item["sheet_name"] for item in sheet_summaries]
    selected_sheet = sheet_names[0] if len(sheet_names) == 1 else st.selectbox("选择需要分析的 Sheet", sheet_names)

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
    with st.expander("查看文件识别结果", expanded=len(sheet_names) > 1):
        st.dataframe(sheet_info, use_container_width=True, hide_index=True)

    with st.spinner("正在清洗数据并生成经营判断..."):
        raw_df, mapped_df, mapping_report = load_mapped_sheet(uploaded_file, selected_sheet, mapping_config)
        analysis = run_analysis(mapped_df, mapping_report, mapping_config, thresholds)

    missing_required = get_missing_required_fields(mapping_report, mapping_config)
    if missing_required:
        st.warning("以下必填字段未识别，部分判断可能不完整：" + "、".join(missing_required))

    full = analysis["full"]
    with st.sidebar:
        st.header("筛选分析范围")
        sales_period = _render_sales_period_filter()
        st.caption(f"默认优先展示 7天；当前销售额、销量和 ACOAS 按 {sales_period_label(sales_period)} 口径重算。")
        st.caption("筛选器彼此联动，并同步影响全部页面、图表和导出结果。")
        st.button("清空所有筛选", use_container_width=True, on_click=_clear_filter_state)
        filters = _render_linked_filters(full, FILTER_COLUMNS)
        if filters:
            st.success(f"已启用 {len(filters)} 个筛选条件")
        else:
            st.caption("当前查看全部数据")

    filtered_full = _apply_filters(full, filters)
    report_tables, overview_metrics, overview_summary = _build_filtered_tables(
        filtered_full,
        analysis["data_errors"],
        thresholds,
        sales_period,
    )

    st.caption(f"分析范围：{len(filtered_full):,} / {len(full):,} 个 SKU")
    tabs = st.tabs(TAB_LABELS)

    with tabs[0]:
        _render_section_intro("经营总览")
        _render_dashboard(report_tables["full_sku"], overview_metrics, overview_summary, sales_period)
        render_visualizations("总览 Dashboard", report_tables)
    with tabs[1]:
        _render_section_intro("引流 SKU")
        _render_table(report_tables["traffic_skus"], table_key="traffic_skus", enable_metric_selector=True)
        render_visualizations("引流 SKU", report_tables)
    with tabs[2]:
        _render_section_intro("主力 SKU")
        _render_table(report_tables["main_skus"], table_key="main_skus", enable_metric_selector=True)
        render_visualizations("主力 SKU", report_tables)
    with tabs[3]:
        _render_section_intro("利润 SKU")
        _render_table(report_tables["profit_skus"], table_key="profit_skus", enable_metric_selector=True)
        render_visualizations("利润 SKU", report_tables)
    with tabs[4]:
        _render_section_intro("低效 SKU")
        _render_table(report_tables["low_efficiency_skus"], table_key="low_efficiency_skus", enable_metric_selector=True)
        render_visualizations("低效异常 SKU", report_tables)
    with tabs[5]:
        _render_section_intro("父体")
        st.markdown("#### 父体经营表现")
        _render_table(report_tables["parent_analysis"], height=420, table_key="parent_analysis")
        st.markdown("#### 结构异常明细")
        _render_table(report_tables["parent_structure_anomalies"], height=360, table_key="parent_structure_anomalies")
        render_visualizations("父体分析", report_tables)
    with tabs[6]:
        _render_section_intro("SPU / 品线")
        if not filters:
            st.markdown("#### 品线经营卡片")
            _render_product_line_cards(filtered_full, report_tables["product_line_analysis"], sales_period)
        st.markdown("#### SPU 汇总")
        _render_table(report_tables["spu_analysis"], height=420, table_key="spu_analysis")
        st.markdown("#### 品线汇总")
        _render_table(report_tables["product_line_analysis"], height=420, table_key="product_line_analysis")
        _render_product_line_diagnosis(filtered_full, thresholds, sales_period)
        render_visualizations("SPU / 品线分析", report_tables)
    with tabs[7]:
        _render_section_intro("全部 SKU")
        _render_table(report_tables["full_sku"], table_key="full_sku", enable_metric_selector=True)
        render_visualizations("SKU 完整判断", report_tables)
    with tabs[8]:
        _render_section_intro("数据质量")
        _render_table(report_tables["data_errors"], table_key="data_errors")
        render_visualizations("数据异常", report_tables)
    with tabs[9]:
        _render_section_intro("导出报告")
        export_bytes = export_analysis_report(report_tables)
        filename = f"amazon_inventory_profit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        st.download_button(
            "下载当前分析报告",
            data=export_bytes,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )
        st.caption("报告包含总览、四类 SKU、父体、SPU、品线和数据异常等 11 个 Sheet。")
        if st.button("同时保存到本地 output/reports", use_container_width=True):
            output_path = OUTPUT_DIR / filename
            export_analysis_report(report_tables, output_path)
            st.success(f"已保存：{output_path}")
        render_visualizations("导出 Excel", report_tables)


if __name__ == "__main__":
    main()
