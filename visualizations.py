from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


NAV_ITEMS = [
    "总览 Dashboard",
    "引流 SKU",
    "主力 SKU",
    "利润 SKU",
    "低效异常 SKU",
    "父体分析",
    "SPU / 品线分析",
    "SKU 完整判断",
    "数据异常",
    "导出 Excel",
]

SECTION_TO_SHEET = {
    "总览 Dashboard": "01_总览",
    "引流 SKU": "02_引流SKU",
    "主力 SKU": "03_主力SKU",
    "利润 SKU": "04_利润SKU",
    "低效异常 SKU": "05_低效异常SKU",
    "SKU 完整判断": "06_SKU完整判断",
    "父体分析": "07_父体分析",
    "SPU / 品线分析": "09_SPU分析",
    "数据异常": "11_数据异常",
}

TABLE_ALIASES = {
    "overview": ("overview", "01_总览"),
    "traffic_skus": ("traffic_skus", "02_引流SKU"),
    "main_skus": ("main_skus", "03_主力SKU"),
    "profit_skus": ("profit_skus", "04_利润SKU"),
    "low_efficiency_skus": ("low_efficiency_skus", "05_低效异常SKU"),
    "full_sku": ("full_sku", "sku_full", "full_sku_df", "06_SKU完整判断"),
    "parent_analysis": ("parent_analysis", "07_父体分析"),
    "parent_structure_anomalies": ("parent_structure_anomalies", "08_父体结构异常"),
    "spu_analysis": ("spu_analysis", "09_SPU分析"),
    "product_line_analysis": ("product_line_analysis", "10_品线分析"),
    "data_errors": ("data_errors", "11_数据异常"),
}

EXPORT_SHEETS = [
    ("01_总览", "overview"),
    ("02_引流SKU", "traffic_skus"),
    ("03_主力SKU", "main_skus"),
    ("04_利润SKU", "profit_skus"),
    ("05_低效异常SKU", "low_efficiency_skus"),
    ("06_SKU完整判断", "full_sku"),
    ("07_父体分析", "parent_analysis"),
    ("08_父体结构异常", "parent_structure_anomalies"),
    ("09_SPU分析", "spu_analysis"),
    ("10_品线分析", "product_line_analysis"),
    ("11_数据异常", "data_errors"),
]

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


def render_visualizations(section_name: str, result_tables: dict[str, pd.DataFrame]) -> None:
    """Render charts for the selected section without mutating result tables."""
    st.divider()
    st.subheader("可视化分析")

    renderers = {
        "总览 Dashboard": _render_overview,
        "引流 SKU": _render_traffic_sku,
        "主力 SKU": _render_main_sku,
        "利润 SKU": _render_profit_sku,
        "低效异常 SKU": _render_low_efficiency_sku,
        "父体分析": _render_parent_analysis,
        "SPU / 品线分析": _render_spu_product_line,
        "SKU 完整判断": _render_full_sku,
        "数据异常": _render_data_anomaly,
        "导出 Excel": _render_export_summary,
    }
    renderer = renderers.get(section_name)
    if renderer is None:
        st.info("当前栏目暂未配置可视化图表。")
        return
    renderer(result_tables)


def _prepare(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    return df.copy()


def _get_df(result_tables: dict[str, pd.DataFrame], key: str) -> pd.DataFrame:
    for candidate in TABLE_ALIASES.get(key, (key,)):
        value = result_tables.get(candidate)
        if isinstance(value, pd.DataFrame):
            return _prepare(value)
    return pd.DataFrame()


def _has(df: pd.DataFrame, *columns: str) -> bool:
    return all(column in df.columns for column in columns)


def _empty_notice(label: str) -> None:
    st.info(f"{label}暂无可视化数据。")


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _is_percent_column(column: str) -> bool:
    lower = column.lower()
    return any(hint in lower for hint in PERCENT_HINTS)


def _update_layout(fig: Any, title: str) -> None:
    fig.update_layout(
        title=title,
        height=360,
        margin=dict(l=10, r=10, t=56, b=10),
        legend_title_text="",
    )


def _render_fig(fig: Any) -> None:
    st.plotly_chart(fig, use_container_width=True)


def _count_bar(df: pd.DataFrame, column: str, title: str) -> bool:
    if not _has(df, column):
        return False
    values = df[column].dropna().astype(str).str.strip()
    values = values[(values != "") & (values.str.lower() != "nan")]
    if values.empty:
        return False
    plot_df = values.value_counts().reset_index()
    plot_df.columns = [column, "SKU 数"]
    fig = px.bar(plot_df, x=column, y="SKU 数", text="SKU 数")
    _update_layout(fig, title)
    _render_fig(fig)
    return True


def _top_bar(
    df: pd.DataFrame,
    label_column: str,
    value_column: str,
    title: str,
    top_n: int = 15,
) -> bool:
    if not _has(df, label_column, value_column):
        return False
    plot_df = df[[label_column, value_column]].copy()
    plot_df[value_column] = _numeric(plot_df[value_column])
    plot_df[label_column] = plot_df[label_column].fillna("").astype(str)
    plot_df = plot_df[(plot_df[label_column].str.strip() != "") & plot_df[value_column].notna()]
    plot_df = plot_df.sort_values(value_column, ascending=False).head(top_n)
    if plot_df.empty:
        return False
    plot_df = plot_df.sort_values(value_column, ascending=True)
    fig = px.bar(plot_df, x=value_column, y=label_column, orientation="h", text=value_column)
    _update_layout(fig, title)
    if _is_percent_column(value_column):
        fig.update_xaxes(tickformat=".0%")
    _render_fig(fig)
    return True


def _scatter(
    df: pd.DataFrame,
    x_column: str,
    y_column: str,
    title: str,
    color_column: str | None = None,
    hover_column: str | None = "sku",
) -> bool:
    if not _has(df, x_column, y_column):
        return False
    plot_columns = [x_column, y_column]
    if color_column and color_column in df.columns:
        plot_columns.append(color_column)
    if hover_column and hover_column in df.columns:
        plot_columns.append(hover_column)
    plot_df = df[plot_columns].copy()
    plot_df[x_column] = _numeric(plot_df[x_column])
    plot_df[y_column] = _numeric(plot_df[y_column])
    plot_df = plot_df[plot_df[x_column].notna() & plot_df[y_column].notna()]
    if plot_df.empty:
        return False
    fig = px.scatter(
        plot_df,
        x=x_column,
        y=y_column,
        color=color_column if color_column in plot_df.columns else None,
        hover_name=hover_column if hover_column in plot_df.columns else None,
    )
    _update_layout(fig, title)
    if _is_percent_column(x_column):
        fig.update_xaxes(tickformat=".0%")
    if _is_percent_column(y_column):
        fig.update_yaxes(tickformat=".0%")
    _render_fig(fig)
    return True


def _inventory_bucket(df: pd.DataFrame, title: str = "库存天数风险分布") -> bool:
    days_column = "available_stock_days" if "available_stock_days" in df.columns else "stock_days"
    if days_column not in df.columns:
        return False
    plot_df = df[[days_column]].copy()
    values = pd.to_numeric(plot_df[days_column], errors="coerce")
    buckets = pd.Series("未知", index=plot_df.index, dtype="object")
    finite = values.replace([np.inf, -np.inf], np.nan)
    buckets[(finite >= 0) & (finite <= 30)] = "0-30天"
    buckets[(finite > 30) & (finite <= 60)] = "31-60天"
    buckets[(finite > 60) & (finite <= 90)] = "61-90天"
    buckets[(finite > 90) & (finite <= 180)] = "91-180天"
    buckets[finite > 180] = "180天+"
    buckets[np.isposinf(values)] = "无销量压货/∞"
    order = ["0-30天", "31-60天", "61-90天", "91-180天", "180天+", "无销量压货/∞", "未知"]
    plot_df = buckets.value_counts().reindex(order, fill_value=0).reset_index()
    plot_df.columns = ["库存天数区间", "SKU 数"]
    plot_df = plot_df[plot_df["SKU 数"] > 0]
    if plot_df.empty:
        return False
    fig = px.bar(plot_df, x="库存天数区间", y="SKU 数", text="SKU 数")
    _update_layout(fig, title)
    _render_fig(fig)
    return True


def _overview_value(overview: pd.DataFrame, metric: str) -> float:
    if not _has(overview, "metric", "value"):
        return np.nan
    matched = overview[overview["metric"].astype(str) == metric]
    if matched.empty:
        return np.nan
    return pd.to_numeric(matched["value"], errors="coerce").iloc[0]


def _render_overview(result_tables: dict[str, pd.DataFrame]) -> None:
    overview = _get_df(result_tables, "overview")
    full_sku = _get_df(result_tables, "full_sku")
    if overview.empty and full_sku.empty:
        _empty_notice("总览 Dashboard")
        return

    cols = st.columns(3)
    cols[0].metric("SKU 总数", f"{_overview_value(overview, 'SKU 总数'):,.0f}" if not pd.isna(_overview_value(overview, "SKU 总数")) else "-")
    cols[1].metric("总毛利润", f"{_overview_value(overview, '订单毛利润'):,.2f}" if not pd.isna(_overview_value(overview, "订单毛利润")) else "-")
    cols[2].metric("广告花费", f"{_overview_value(overview, '总广告花费'):,.2f}" if not pd.isna(_overview_value(overview, "总广告花费")) else "-")

    rendered = 0
    chart_cols = st.columns(2)
    with chart_cols[0]:
        rendered += int(_count_bar(full_sku, "sku_role", "SKU 经营角色分布"))
    with chart_cols[1]:
        rendered += int(_count_bar(full_sku, "final_action", "final_action 主动作分布"))
    chart_cols = st.columns(2)
    with chart_cols[0]:
        rendered += int(_count_bar(full_sku, "priority", "priority 优先级分布"))
    with chart_cols[1]:
        rendered += int(_inventory_bucket(full_sku, "库存天数风险分布"))
    if rendered == 0:
        _empty_notice("总览 Dashboard")


def _render_traffic_sku(result_tables: dict[str, pd.DataFrame]) -> None:
    df = _get_df(result_tables, "traffic_skus")
    if df.empty:
        _empty_notice("引流 SKU")
        return
    rendered = 0
    cols = st.columns(2)
    with cols[0]:
        rendered += int(_top_bar(df, "sku", "ad_spend", "广告花费 Top SKU"))
    with cols[1]:
        rendered += int(_top_bar(df, "sku", "ad_sales", "广告销售额 Top SKU"))
    cols = st.columns(2)
    with cols[0]:
        rendered += int(_scatter(df, "ad_spend", "ad_sales", "广告花费 vs 广告销售额散点图", "final_action"))
    with cols[1]:
        rendered += int(_scatter(df, "acos", "order_gross_margin", "ACOS vs 毛利率散点图", "final_action"))
    if rendered == 0:
        _empty_notice("引流 SKU")


def _render_main_sku(result_tables: dict[str, pd.DataFrame]) -> None:
    df = _get_df(result_tables, "main_skus")
    if df.empty:
        _empty_notice("主力 SKU")
        return
    rendered = 0
    cols = st.columns(2)
    with cols[0]:
        rendered += int(_top_bar(df, "sku", "sales_14d_units", "14 天销量 Top SKU"))
    with cols[1]:
        rendered += int(_count_bar(df, "final_action", "主力 SKU final_action 分布"))
    rendered += int(_scatter(df, "sales_14d_units", "order_gross_profit", "14 天销量 vs 毛利润散点图", "final_action"))
    if rendered == 0:
        _empty_notice("主力 SKU")


def _render_profit_sku(result_tables: dict[str, pd.DataFrame]) -> None:
    df = _get_df(result_tables, "profit_skus")
    if df.empty:
        _empty_notice("利润 SKU")
        return
    rendered = 0
    cols = st.columns(2)
    with cols[0]:
        rendered += int(_top_bar(df, "sku", "order_gross_profit", "毛利润 Top SKU"))
    with cols[1]:
        rendered += int(_top_bar(df, "sku", "order_gross_margin", "毛利率 Top SKU"))
    cols = st.columns(2)
    with cols[0]:
        rendered += int(_scatter(df, "available_stock_days", "order_gross_margin", "库存天数 vs 毛利率散点图", "final_action"))
    with cols[1]:
        rendered += int(_count_bar(df, "final_action", "利润 SKU final_action 分布"))
    if rendered == 0:
        _empty_notice("利润 SKU")


def _render_low_efficiency_sku(result_tables: dict[str, pd.DataFrame]) -> None:
    df = _get_df(result_tables, "low_efficiency_skus")
    if df.empty:
        _empty_notice("低效异常 SKU")
        return
    rendered = 0
    cols = st.columns(2)
    with cols[0]:
        rendered += int(_count_bar(df, "final_action", "低效异常 SKU final_action 分布"))
    with cols[1]:
        rendered += int(_count_bar(df, "priority", "低效异常 SKU priority 分布"))
    cols = st.columns(2)
    with cols[0]:
        rendered += int(_top_bar(df, "sku", "aged_inventory_181_plus", "180 天以上库龄库存 Top SKU"))
    with cols[1]:
        rendered += int(_scatter(df, "ad_spend", "order_gross_profit", "广告花费 vs 毛利润散点图", "final_action"))
    if rendered == 0:
        _empty_notice("低效异常 SKU")


def _render_parent_analysis(result_tables: dict[str, pd.DataFrame]) -> None:
    parent_df = _get_df(result_tables, "parent_analysis")
    full_sku = _get_df(result_tables, "full_sku")
    if parent_df.empty and full_sku.empty:
        _empty_notice("父体分析")
        return
    rendered = 0
    cols = st.columns(2)
    with cols[0]:
        rendered += int(_top_bar(parent_df, "parent_asin", "sales_14d_units", "父体 14 天销量排名"))
    with cols[1]:
        rendered += int(_top_bar(parent_df, "parent_asin", "order_gross_profit", "父体毛利润排名"))
    rendered += int(_count_bar(parent_df, "parent_status", "父体动作/状态分布"))
    rendered += int(_parent_role_stack(full_sku))
    if rendered == 0:
        _empty_notice("父体分析")


def _parent_role_stack(full_sku: pd.DataFrame, top_n: int = 10) -> bool:
    if not _has(full_sku, "parent_asin", "sku_role"):
        return False
    metric_column = "sales_14d_units" if "sales_14d_units" in full_sku.columns else None
    plot_columns = ["parent_asin", "sku_role"] + ([metric_column] if metric_column else [])
    plot_df = full_sku[plot_columns].copy()
    plot_df["parent_asin"] = plot_df["parent_asin"].fillna("").astype(str).str.strip()
    plot_df["sku_role"] = plot_df["sku_role"].fillna("").astype(str).str.strip()
    plot_df = plot_df[(plot_df["parent_asin"] != "") & (plot_df["sku_role"] != "")]
    if plot_df.empty:
        return False
    if metric_column is None:
        parent_order = plot_df["parent_asin"].value_counts().head(top_n).index.tolist()
    else:
        plot_df[metric_column] = _numeric(plot_df[metric_column]).fillna(0)
        parent_order = plot_df.groupby("parent_asin")[metric_column].sum().sort_values(ascending=False).head(top_n).index.tolist()
    plot_df = plot_df[plot_df["parent_asin"].isin(parent_order)]
    stack_df = plot_df.groupby(["parent_asin", "sku_role"]).size().reset_index(name="SKU 数")
    if stack_df.empty:
        return False
    fig = px.bar(stack_df, x="parent_asin", y="SKU 数", color="sku_role", barmode="stack")
    _update_layout(fig, "Top 父体内 SKU 角色结构堆叠柱状图")
    _render_fig(fig)
    return True


def _render_spu_product_line(result_tables: dict[str, pd.DataFrame]) -> None:
    spu_df = _get_df(result_tables, "spu_analysis")
    line_df = _get_df(result_tables, "product_line_analysis")
    if spu_df.empty and line_df.empty:
        _empty_notice("SPU / 品线分析")
        return
    rendered = 0
    cols = st.columns(2)
    with cols[0]:
        rendered += int(_top_bar(spu_df, "spu", "sales_14d_units", "SPU 14 天销量排名"))
    with cols[1]:
        rendered += int(_top_bar(spu_df, "spu", "order_gross_profit", "SPU 毛利润排名"))
    line_label = "dimension_value" if "dimension_value" in line_df.columns else "product_line"
    cols = st.columns(2)
    with cols[0]:
        rendered += int(_top_bar(line_df, line_label, "order_gross_profit", "品线毛利润贡献"))
    with cols[1]:
        rendered += int(_top_bar(line_df, line_label, "sales_14d_units", "品线 14 天销量贡献"))
    if rendered == 0:
        _empty_notice("SPU / 品线分析")


def _render_full_sku(result_tables: dict[str, pd.DataFrame]) -> None:
    df = _get_df(result_tables, "full_sku")
    if df.empty:
        _empty_notice("SKU 完整判断")
        return
    rendered = 0
    cols = st.columns(2)
    with cols[0]:
        rendered += int(_count_bar(df, "sku_role", "SKU 角色分布"))
    with cols[1]:
        rendered += int(_count_bar(df, "final_action", "全 SKU final_action 分布"))
    cols = st.columns(2)
    with cols[0]:
        rendered += int(_count_bar(df, "priority", "全 SKU priority 分布"))
    with cols[1]:
        rendered += int(_scatter(df, "available_stock_days", "order_gross_profit", "库存天数 vs 毛利润散点图", "sku_role"))
    if rendered == 0:
        _empty_notice("SKU 完整判断")


def _render_data_anomaly(result_tables: dict[str, pd.DataFrame]) -> None:
    df = _get_df(result_tables, "data_errors")
    if df.empty:
        st.info("暂未发现数据异常。")
        return
    anomaly_fields = ["异常类型", "anomaly_type", "issue_type", "error_type", "字段", "field", "missing_field"]
    field = next((column for column in anomaly_fields if column in df.columns), None)
    if field is None:
        st.info("暂未发现标准异常类型字段。")
        return
    if not _count_bar(df, field, "数据异常类型分布"):
        _empty_notice("数据异常")


def _render_export_summary(result_tables: dict[str, pd.DataFrame]) -> None:
    rows = []
    for sheet_name, key in EXPORT_SHEETS:
        df = _get_df(result_tables, key)
        rows.append({"Sheet": sheet_name, "行数": len(df), "列数": len(df.columns)})
    summary = pd.DataFrame(rows)
    if summary.empty:
        _empty_notice("导出 Excel")
        return
    st.dataframe(summary, use_container_width=True, hide_index=True)
    plot_df = summary.melt(id_vars="Sheet", value_vars=["行数", "列数"], var_name="指标", value_name="数量")
    fig = px.bar(plot_df, x="Sheet", y="数量", color="指标", barmode="group", text="数量")
    _update_layout(fig, "导出内容覆盖情况柱状图")
    _render_fig(fig)
