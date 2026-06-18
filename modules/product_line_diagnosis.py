from __future__ import annotations

from datetime import date, timedelta
from math import ceil
from typing import Any

import numpy as np
import pandas as pd


PROBLEM_PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
BUSINESS_PRIORITY_ORDER = {"周转": 0, "规模": 1, "毛利润": 2, "毛利率": 3, "数据可信度": 4}
RISK_ACTIONS = {"清货处理", "禁止补货", "高毛利停补", "控广告", "暂缓补货"}
URGENT_ACTIONS = {"立即补货", "优先补货"}
ROLE_ORDER = ["引流 SKU", "主力 SKU", "利润 SKU", "低效异常 SKU"]


def _num(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce")


def _text(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series("", index=df.index, dtype="string")
    return df[column].astype("string").fillna("").str.strip()


def _safe_divide(numerator: float | pd.Series, denominator: float | pd.Series) -> float | pd.Series:
    if isinstance(numerator, pd.Series) or isinstance(denominator, pd.Series):
        if isinstance(numerator, pd.Series):
            num = pd.to_numeric(numerator, errors="coerce")
            index = numerator.index
        else:
            index = denominator.index if isinstance(denominator, pd.Series) else None
            num = pd.Series(numerator, index=index, dtype="float64")
        if isinstance(denominator, pd.Series):
            den = pd.to_numeric(denominator, errors="coerce")
        else:
            den = pd.Series(denominator, index=num.index, dtype="float64")
        return num.div(den.where(den > 0))
    return float(numerator / denominator) if denominator and denominator > 0 else np.nan


def _fmt_number(value: Any, digits: int = 2) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if pd.isna(number):
        return "-"
    return f"{number:,.{digits}f}"


def _fmt_int(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if pd.isna(number):
        return "-"
    return f"{number:,.0f}"


def _fmt_pct(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if pd.isna(number):
        return "-"
    return f"{number:.2%}"


def _first_non_empty(row: pd.Series, columns: list[str]) -> str:
    for column in columns:
        value = str(row.get(column, "")).strip()
        if value and value.lower() not in {"nan", "none", "<na>"}:
            return value
    return ""


def _top_contribution(values: pd.Series, total: float, percent: float = 0.2) -> tuple[int, float]:
    clean = pd.to_numeric(values, errors="coerce").fillna(0.0).sort_values(ascending=False)
    if clean.empty or total <= 0:
        return 0, np.nan
    top_n = max(1, int(ceil(len(clean) * percent)))
    return top_n, float(clean.head(top_n).sum() / total)


def _concentration_label(share: float) -> str:
    if pd.isna(share):
        return "无法判断"
    if share >= 0.8:
        return "高度集中"
    if share >= 0.6:
        return "较集中"
    return "相对分散"


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["_sku"] = _text(result, "sku")
    result["_product_line"] = _text(result, "product_line")
    result["_parent_asin"] = _text(result, "parent_asin")
    result["_parent_key"] = result["_parent_asin"].where(result["_parent_asin"] != "", "未分组-" + result["_sku"])
    result["_sku_name"] = _text(result, "product_name").where(_text(result, "product_name") != "", result["_sku"])
    result["_sku_role"] = _text(result, "sku_role").where(_text(result, "sku_role") != "", "未分类")
    result["_final_action"] = _text(result, "final_action")
    result["_system_priority"] = _text(result, "priority")
    result["_reason"] = _text(result, "reason")

    sales_14d_amount = _num(result, "sales_14d_amount", np.nan)
    sales_7d_amount = _num(result, "sales_7d_amount", np.nan)
    sales_14d_units = _num(result, "sales_14d_units", np.nan)
    sales_7d_units = _num(result, "sales_7d_units", np.nan)
    result["_sales_amount"] = sales_14d_amount.where(sales_14d_amount > 0, sales_7d_amount).fillna(0.0)
    result["_sales_units"] = sales_14d_units.where(sales_14d_units > 0, sales_7d_units).fillna(0.0)
    result["_daily_units"] = np.where(sales_14d_units > 0, sales_14d_units / 14, sales_7d_units / 7)
    result["_daily_units"] = pd.to_numeric(pd.Series(result["_daily_units"], index=result.index), errors="coerce").fillna(0.0)
    result["_average_price"] = _safe_divide(result["_sales_amount"], result["_sales_units"]).fillna(0.0)
    result["_gross_profit"] = _num(result, "order_gross_profit", np.nan).fillna(0.0)
    calculated_margin = _safe_divide(result["_gross_profit"], result["_sales_amount"])
    result["_gross_margin"] = _num(result, "order_gross_margin", np.nan).where(_num(result, "order_gross_margin", np.nan).notna(), calculated_margin)
    result["_ad_spend"] = _num(result, "ad_spend", 0.0).fillna(0.0)
    result["_acoas"] = _safe_divide(result["_ad_spend"], result["_sales_amount"])
    result["_available_stock_days"] = _num(result, "available_stock_days", np.nan)
    result["_stock_days"] = result["_available_stock_days"].where(result["_available_stock_days"].notna(), _num(result, "stock_days", np.nan))
    result["_inventory_qty"] = _num(result, "available_stock_qty", np.nan).where(
        _num(result, "available_stock_qty", np.nan).notna(),
        _num(result, "available_qty", 0.0),
    ).fillna(0.0)
    result["_size"] = _first_size(result)
    return result


def _first_size(df: pd.DataFrame) -> pd.Series:
    candidates = [column for column in ["size", "规格", "尺寸"] if column in df.columns]
    if not candidates:
        return pd.Series("", index=df.index, dtype="string")
    values = pd.Series("", index=df.index, dtype="string")
    for column in candidates:
        current = df[column].astype("string").fillna("").str.strip()
        values = values.where(values != "", current)
    return values.fillna("")


def _line_scope(prepared: pd.DataFrame, product_line: str) -> pd.DataFrame:
    selected = str(product_line).strip()
    return prepared[prepared["_product_line"] == selected].copy()


def _add_shares(line_df: pd.DataFrame, prepared: pd.DataFrame) -> pd.DataFrame:
    result = line_df.copy()
    line_sales = result["_sales_amount"].sum()
    line_units = result["_sales_units"].sum()
    line_profit = result["_gross_profit"].sum()
    positive_profit = result["_gross_profit"].clip(lower=0).sum()
    line_ad_spend = result["_ad_spend"].sum()

    result["sales_share_line"] = _safe_divide(result["_sales_amount"], line_sales).fillna(0.0)
    result["units_share_line"] = _safe_divide(result["_sales_units"], line_units).fillna(0.0)
    if line_profit > 0:
        result["profit_share_line"] = _safe_divide(result["_gross_profit"].clip(lower=0), line_profit).fillna(0.0)
    elif positive_profit > 0:
        result["profit_share_line"] = _safe_divide(result["_gross_profit"].clip(lower=0), positive_profit).fillna(0.0)
    else:
        result["profit_share_line"] = np.nan
    result["ad_spend_share_line"] = _safe_divide(result["_ad_spend"], line_ad_spend).fillna(0.0)
    result["ad_sales_mismatch"] = result["ad_spend_share_line"] - result["sales_share_line"]
    result["ad_profit_mismatch"] = result["ad_spend_share_line"] - result["profit_share_line"] if line_profit > 0 else np.nan

    parent_sales = prepared.groupby("_parent_key")["_sales_amount"].transform("sum")
    parent_ad_spend = prepared.groupby("_parent_key")["_ad_spend"].transform("sum")
    result["sales_share_parent"] = _safe_divide(result["_sales_amount"], parent_sales.loc[result.index]).fillna(0.0)
    result["ad_spend_share_parent"] = _safe_divide(result["_ad_spend"], parent_ad_spend.loc[result.index]).fillna(0.0)
    return result


def _core_metrics(line_df: pd.DataFrame) -> pd.DataFrame:
    sales = line_df["_sales_amount"].sum()
    units = line_df["_sales_units"].sum()
    daily_units = line_df["_daily_units"].sum()
    avg_price = _safe_divide(sales, units)
    profit = line_df["_gross_profit"].sum()
    margin = _safe_divide(profit, sales)
    ad_spend = line_df["_ad_spend"].sum()
    acoas = _safe_divide(ad_spend, sales)
    loss_sum = line_df.loc[line_df["_gross_profit"] < 0, "_gross_profit"].sum()
    sales_top_n, sales_top_share = _top_contribution(line_df["_sales_amount"], sales)
    profit_top_n, profit_top_share = _top_contribution(line_df["_gross_profit"].clip(lower=0), line_df["_gross_profit"].clip(lower=0).sum())
    ad_top_n, ad_top_share = _top_contribution(line_df["_ad_spend"], ad_spend)

    rows = [
        {
            "指标": "销售额",
            "数值": sales,
            "计算口径": "品线内 SKU 销售额合计，优先 14天销售额，缺失时使用 7天销售额",
            "判断": f"前20% SKU（{sales_top_n}个）贡献 {_fmt_pct(sales_top_share)}，销售额集中度为{_concentration_label(sales_top_share)}。",
        },
        {
            "指标": "销量",
            "数值": units,
            "计算口径": "品线内 SKU 销量合计，优先 14天销量，缺失时使用 7天销量",
            "判断": f"日均销量 {_fmt_number(daily_units)}，平均销售价格 {_fmt_number(avg_price)}。",
        },
        {
            "指标": "利润率",
            "数值": margin,
            "计算口径": "品线利润额合计 / 品线销售额合计，禁止使用 SKU 利润率算术平均",
            "判断": f"品线加权利润率为 {_fmt_pct(margin)}。",
        },
        {
            "指标": "利润额",
            "数值": profit,
            "计算口径": "品线内 SKU 毛利润合计",
            "判断": f"亏损 SKU 合计亏损 {_fmt_number(loss_sum)}；正利润 SKU 前20%（{profit_top_n}个）贡献 {_fmt_pct(profit_top_share)}。",
        },
        {
            "指标": "广告花费",
            "数值": ad_spend,
            "计算口径": "品线内 SKU 广告花费合计",
            "判断": f"前20% SKU（{ad_top_n}个）消耗 {_fmt_pct(ad_top_share)}，广告集中度为{_concentration_label(ad_top_share)}。",
        },
        {
            "指标": "广告花费占比",
            "数值": acoas,
            "计算口径": "品线广告花费合计 / 品线销售额合计，禁止对 SKU 广告花费占比取平均",
            "判断": f"品线 ACOAS 为 {_fmt_pct(acoas)}。",
        },
    ]
    return pd.DataFrame(rows)


def _role_structure(line_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    sales_total = line_df["_sales_amount"].sum()
    units_total = line_df["_sales_units"].sum()
    profit_total = line_df["_gross_profit"].sum()
    ad_total = line_df["_ad_spend"].sum()
    line_margin = _safe_divide(profit_total, sales_total)
    for role, group in line_df.groupby("_sku_role", dropna=False):
        sales = group["_sales_amount"].sum()
        units = group["_sales_units"].sum()
        profit = group["_gross_profit"].sum()
        ad_spend = group["_ad_spend"].sum()
        margin = _safe_divide(profit, sales)
        ad_share = _safe_divide(ad_spend, ad_total)
        sales_share = _safe_divide(sales, sales_total)
        units_share = _safe_divide(units, units_total)
        profit_share = _safe_divide(profit, profit_total) if profit_total > 0 else np.nan
        rows.append(
            {
                "SKU经营角色": role,
                "SKU数": int(len(group)),
                "销售额": sales,
                "销售额占比": sales_share,
                "销量": units,
                "销量占比": units_share,
                "利润额": profit,
                "利润率": margin,
                "利润额占比": profit_share,
                "广告花费": ad_spend,
                "广告花费占比": ad_share,
                "广告花费/销售额": _safe_divide(ad_spend, sales),
                "角色履职判断": _role_group_status(str(role), sales_share, units_share, profit, margin, ad_share, line_margin),
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["_role_sort"] = pd.Categorical(result["SKU经营角色"], categories=ROLE_ORDER, ordered=True)
    return result.sort_values(["_role_sort", "销售额"], ascending=[True, False]).drop(columns="_role_sort")


def _role_group_status(
    role: str,
    sales_share: float,
    units_share: float,
    profit: float,
    margin: float,
    ad_share: float,
    line_margin: float,
) -> str:
    if role == "引流 SKU":
        if ad_share > 0 and max(sales_share, units_share) < ad_share * 0.5:
            return "角色失效：广告投入与销售/销量贡献不匹配"
        return "角色履职正常：产生了流量或销量贡献"
    if role == "主力 SKU":
        if sales_share >= 0.2 and profit > 0:
            return "角色履职正常：承担规模且保持盈利"
        if sales_share >= 0.2 and profit <= 0:
            return "角色履职偏弱：规模存在但利润恶化"
        return "角色履职偏弱：规模贡献不足"
    if role == "利润 SKU":
        if profit > 0 and not pd.isna(margin) and not pd.isna(line_margin) and margin > line_margin:
            return "角色履职正常：利润率高于品线且产生利润"
        return "角色履职偏弱：尚未形成有效利润额"
    if ad_share > sales_share + 0.1:
        return "角色失效：低效 SKU 仍持续消耗广告"
    return "角色履职偏弱：需控制投入并观察去留"


def _comparison_flags(row: pd.Series, line_df: pd.DataFrame, prepared: pd.DataFrame) -> dict[str, Any]:
    parent_group = prepared[prepared["_parent_key"] == row["_parent_key"]]
    parent_ok = len(parent_group) >= 2
    parent_margin_median = parent_group["_gross_margin"].median()
    parent_sales_median = parent_group["_sales_amount"].median()
    parent_under = parent_ok and row["_sales_amount"] < parent_sales_median and row["_gross_margin"] < parent_margin_median

    line_ok = len(line_df) >= 2
    line_margin_median = line_df["_gross_margin"].median()
    line_sales_median = line_df["_sales_amount"].median()
    line_under = line_ok and row["_sales_amount"] < line_sales_median and row["_gross_margin"] < line_margin_median

    size_compare, size_ok, size_under = _peer_compare(row, prepared, line_df, mode="size")
    price_compare, price_ok, price_under = _peer_compare(row, prepared, line_df, mode="price")
    confidence = _confidence(row, [parent_ok, line_ok, size_ok, price_ok])
    return {
        "parent_compare": _parent_compare(row, parent_group, parent_ok),
        "line_compare": _line_compare(row, line_df, line_ok),
        "size_compare": size_compare,
        "price_compare": price_compare,
        "confidence": confidence,
        "parent_under": bool(parent_under),
        "line_under": bool(line_under),
        "size_under": bool(size_under),
        "price_under": bool(price_under),
        "comparison_ok_count": int(sum([parent_ok, line_ok, size_ok, price_ok])),
    }


def _parent_compare(row: pd.Series, parent_group: pd.DataFrame, ok: bool) -> str:
    if not ok:
        return "同父体 SKU 样本不足，无法输出确定性结论。"
    rank = int(parent_group["_sales_amount"].rank(method="min", ascending=False).loc[row.name])
    margin_median = parent_group["_gross_margin"].median()
    return (
        f"父体内 {len(parent_group)} 个SKU，销售额排名 {rank}/{len(parent_group)}；"
        f"销售额占父体 {_fmt_pct(row['sales_share_parent'])}，广告花费占父体 {_fmt_pct(row['ad_spend_share_parent'])}；"
        f"毛利率 {_fmt_pct(row['_gross_margin'])} vs 父体中位数 {_fmt_pct(margin_median)}。"
    )


def _line_compare(row: pd.Series, line_df: pd.DataFrame, ok: bool) -> str:
    if not ok:
        return "品线内 SKU 样本不足，无法输出确定性结论。"
    rank = int(line_df["_sales_amount"].rank(method="min", ascending=False).loc[row.name])
    margin_median = line_df["_gross_margin"].median()
    sales_median = line_df["_sales_amount"].median()
    return (
        f"品线内销售额排名 {rank}/{len(line_df)}；销售额贡献 {_fmt_pct(row['sales_share_line'])}，"
        f"利润贡献 {_fmt_pct(row['profit_share_line'])}，广告贡献 {_fmt_pct(row['ad_spend_share_line'])}；"
        f"销售额 {_fmt_number(row['_sales_amount'])} vs 品线中位数 {_fmt_number(sales_median)}，"
        f"毛利率 {_fmt_pct(row['_gross_margin'])} vs 品线中位数 {_fmt_pct(margin_median)}。"
    )


def _peer_compare(
    row: pd.Series,
    prepared: pd.DataFrame,
    line_df: pd.DataFrame,
    mode: str,
) -> tuple[str, bool, bool]:
    if mode == "size":
        size = str(row.get("_size", "")).strip()
        if not size:
            return "缺少尺寸/规格字段，无法做同尺寸比较。", False, False
        same_line = line_df[(line_df["_size"] == size) & (line_df.index != row.name)]
        peers = same_line if len(same_line) >= 3 else prepared[(prepared["_size"] == size) & (prepared.index != row.name)]
        scope = "同品线同尺寸" if len(same_line) >= 3 else "跨品线同尺寸"
    else:
        price = row.get("_average_price", np.nan)
        if pd.isna(price) or price <= 0:
            return "平均售价缺失或为0，无法做价格带比较。", False, False
        lower, upper = price * 0.9, price * 1.1
        same_line = line_df[(line_df["_average_price"].between(lower, upper)) & (line_df.index != row.name)]
        peers = same_line if len(same_line) >= 3 else prepared[(prepared["_average_price"].between(lower, upper)) & (prepared.index != row.name)]
        scope = "同品线同价格带" if len(same_line) >= 3 else "全品线同价格带"

    if len(peers) < 3:
        return f"{scope}有效对比 SKU 不足3个，标记低置信度。", False, False
    units_median = peers["_sales_units"].median()
    margin_median = peers["_gross_margin"].median()
    acoas_median = peers["_acoas"].median()
    under = row["_sales_units"] < units_median and row["_gross_margin"] < margin_median
    return (
        f"{scope}对比 {len(peers)} 个SKU；销量 {_fmt_number(row['_sales_units'])} vs 中位数 {_fmt_number(units_median)}，"
        f"毛利率 {_fmt_pct(row['_gross_margin'])} vs 中位数 {_fmt_pct(margin_median)}，"
        f"广告花费占比 {_fmt_pct(row['_acoas'])} vs 中位数 {_fmt_pct(acoas_median)}。",
        True,
        bool(under),
    )


def _confidence(row: pd.Series, comparison_ok: list[bool]) -> str:
    key_missing = 0
    for column in ["_sales_amount", "_sales_units", "_gross_profit", "_gross_margin", "_ad_spend"]:
        value = row.get(column)
        if pd.isna(value):
            key_missing += 1
    insufficient = len([ok for ok in comparison_ok if not ok])
    if insufficient >= 2 or key_missing >= 2:
        return "低"
    if insufficient == 1 or key_missing == 1:
        return "中"
    return "高"


def _role_status(row: pd.Series, line_margin: float) -> str:
    role = str(row.get("_sku_role", ""))
    sales_share = row.get("sales_share_line", 0.0)
    units_share = row.get("units_share_line", 0.0)
    ad_share = row.get("ad_spend_share_line", 0.0)
    profit = row.get("_gross_profit", 0.0)
    margin = row.get("_gross_margin", np.nan)
    if role == "引流 SKU":
        if ad_share > 0 and max(sales_share, units_share) < ad_share * 0.5:
            return "角色失效"
        if ad_share > sales_share + 0.15:
            return "角色履职偏弱"
        return "角色履职正常"
    if role == "主力 SKU":
        if sales_share >= 0.2 and profit > 0:
            return "角色履职正常"
        if sales_share >= 0.2 and profit <= 0:
            return "角色履职偏弱"
        return "角色履职偏弱"
    if role == "利润 SKU":
        if profit > 0 and not pd.isna(margin) and not pd.isna(line_margin) and margin > line_margin:
            return "角色履职正常"
        if not pd.isna(margin) and not pd.isna(line_margin) and margin > line_margin and profit <= 0:
            return "角色履职偏弱"
        return "角色失效"
    if ad_share > sales_share + 0.1 or profit < 0:
        return "角色失效"
    return "数据不足" if row.get("_sales_amount", 0) <= 0 else "角色履职偏弱"


def _problem_priority(row: pd.Series) -> str:
    final_action = row.get("_final_action", "")
    stock_days = row.get("_stock_days", np.nan)
    high_ad = row.get("ad_spend_share_line", 0.0) >= 0.2 or row.get("_ad_spend", 0.0) >= row.get("_line_ad_median", np.inf)
    if (row.get("_gross_profit", 0.0) < 0 and high_ad) or final_action in RISK_ACTIONS or final_action in URGENT_ACTIONS:
        return "P0"
    if not pd.isna(stock_days) and (stock_days > 90 or stock_days < 30):
        return "P0"
    if row.get("ad_sales_mismatch", 0.0) >= 0.15 or row.get("ad_profit_mismatch", 0.0) >= 0.15:
        return "P1"
    if row.get("role_fulfillment") in {"角色失效", "角色履职偏弱"}:
        return "P1"
    return "P2"


def _problem_facts(row: pd.Series) -> list[str]:
    facts: list[str] = []
    if row.get("_gross_profit", 0.0) < 0:
        facts.append(f"毛利润为负（{_fmt_number(row['_gross_profit'])}）")
    if row.get("ad_sales_mismatch", 0.0) >= 0.15:
        facts.append(f"广告贡献高于销售贡献 {_fmt_pct(row['ad_sales_mismatch'])}")
    if not pd.isna(row.get("ad_profit_mismatch", np.nan)) and row.get("ad_profit_mismatch", 0.0) >= 0.15:
        facts.append(f"广告贡献高于利润贡献 {_fmt_pct(row['ad_profit_mismatch'])}")
    stock_days = row.get("_stock_days", np.nan)
    if not pd.isna(stock_days) and stock_days > 90:
        facts.append(f"库存天数进入红线（{_fmt_number(stock_days)}天）")
    if not pd.isna(stock_days) and stock_days < 30:
        facts.append(f"库存偏低，存在断货风险（{_fmt_number(stock_days)}天）")
    if row.get("role_fulfillment") in {"角色失效", "角色履职偏弱"}:
        facts.append(row.get("role_fulfillment"))
    if not facts:
        facts.append("一般性优化项")
    return facts


def _judgement(row: pd.Series) -> str:
    under_flags = [row.get("parent_under"), row.get("line_under"), row.get("size_under"), row.get("price_under")]
    bad_count = sum(bool(flag) for flag in under_flags)
    if row.get("_sku_role") == "主力 SKU" and row.get("_sales_amount", 0) > row.get("_line_sales_median", 0) and row.get("_gross_profit", 0) > 0:
        return "可能是规模型主力 SKU，不得仅因利润率低判定为低效。"
    if bad_count >= 3:
        return "SKU 在多数基准中偏弱，可能存在结构性问题。"
    if row.get("parent_under") and not row.get("line_under"):
        return "主要方向是父体内部资源分配、变体抢量或父体结构问题。"
    if row.get("line_under") and not row.get("parent_under"):
        return "父体内正常但低于品线基准，需检查父体整体竞争力。"
    if row.get("size_under") and bad_count == 1:
        return "主要方向是尺寸定位、尺寸需求或同尺寸竞争力问题。"
    if row.get("price_under") and bad_count == 1:
        return "主要方向是价格竞争力、产品价值感或转化率问题。"
    return "需结合父体、品线、尺寸和价格带继续复核，不输出单一因果结论。"


def _suggested_action(row: pd.Series) -> str:
    role = row.get("_sku_role", "")
    final_action = row.get("_final_action", "")
    if final_action in RISK_ACTIONS:
        return f"执行系统动作“{final_action}”，同步减少低效广告并处理库存。"
    if final_action in URGENT_ACTIONS:
        return f"执行系统动作“{final_action}”，保护库存和核心流量，避免断货。"
    if row.get("ad_sales_mismatch", 0.0) >= 0.15:
        return "保留核心词，减少高花费低转化投放，对无订单搜索词做否定。"
    if role == "利润 SKU":
        return "先确认库存健康，再测试高转化关键词和小预算扩量。"
    if role == "主力 SKU":
        return "保护核心流量，排查价格、成本、转化率和促销，优先改善单位利润。"
    if role == "低效异常 SKU":
        return "减少或暂停广告，停止补货，进入限期测试或清理库存。"
    return "保持低风险观察，复核广告、库存和利润变化。"


def _impact(row: pd.Series) -> str:
    if row.get("_gross_profit", 0.0) < 0:
        return "继续放量会放大利润损失。"
    if row.get("ad_sales_mismatch", 0.0) >= 0.15:
        return "广告预算相对销售贡献偏重，可能挤压品线利润。"
    if row.get("_stock_days", 0.0) > 90:
        return "库存现金占用上升，周转风险增加。"
    if row.get("_stock_days", np.nan) < 30:
        return "断货会影响排名和销售稳定性。"
    return "影响中低，适合放入常规优化队列。"


def _cause_level_for_sku(row: pd.Series) -> str:
    stock_days = row.get("_stock_days", np.nan)
    direct_fact = (
        row.get("_gross_profit", 0.0) < 0
        or row.get("_final_action", "") in RISK_ACTIONS | URGENT_ACTIONS
        or (not pd.isna(stock_days) and (stock_days > 90 or stock_days < 30))
    )
    if direct_fact:
        return "已确认原因"
    if row.get("confidence") == "低" and row.get("comparison_ok_count", 0) <= 1:
        return "无法判断"
    if row.get("ad_sales_mismatch", 0.0) >= 0.15 and row.get("comparison_ok_count", 0) >= 2:
        return "高概率原因"
    if row.get("confidence") == "低":
        return "待验证假设"
    return "高概率原因"


def _sku_validation_action(row: pd.Series) -> str:
    missing: list[str] = []
    if "缺少尺寸" in str(row.get("size_compare", "")):
        missing.append("尺寸/规格")
    if "不足3个" in str(row.get("price_compare", "")):
        missing.append("更多同价格带样本")
    if row.get("cause_level") == "已确认原因":
        return "固定同一观察窗口复核指标，并按系统动作执行后记录结果。"
    if row.get("ad_sales_mismatch", 0.0) >= 0.15:
        return "固定7天广告窗口，拆分核心词与低转化词，比较调整前后销量、ACOAS和毛利润。"
    if missing:
        return "补充" + "、".join(missing) + "后再做同父体、同品线、同规格和价格带复核。"
    return "采用单SKU小范围测试并保留对照，观察销量、毛利润、ACOAS和库存天数。"


def _build_sku_analysis(line_df: pd.DataFrame, prepared: pd.DataFrame) -> pd.DataFrame:
    if line_df.empty:
        return pd.DataFrame()
    result = line_df.copy()
    line_sales = result["_sales_amount"].sum()
    line_profit = result["_gross_profit"].sum()
    line_margin = _safe_divide(line_profit, line_sales)
    result["_line_sales_median"] = result["_sales_amount"].median()
    result["_line_profit_median"] = result["_gross_profit"].median()
    result["_line_ad_median"] = result["_ad_spend"].median()
    result["role_fulfillment"] = result.apply(lambda row: _role_status(row, line_margin), axis=1)

    comparison_rows = []
    for _, row in result.iterrows():
        comparison_rows.append(_comparison_flags(row, result, prepared))
    comparison = pd.DataFrame(comparison_rows, index=result.index)
    result = pd.concat([result, comparison], axis=1)
    result["problem_priority"] = result.apply(_problem_priority, axis=1)
    result["problem_facts"] = result.apply(lambda row: "；".join(_problem_facts(row)), axis=1)
    result["problem_judgement"] = result.apply(_judgement, axis=1)
    result["suggested_action"] = result.apply(_suggested_action, axis=1)
    result["business_impact"] = result.apply(_impact, axis=1)
    result["cause_level"] = result.apply(_cause_level_for_sku, axis=1)
    result["validation_action"] = result.apply(_sku_validation_action, axis=1)
    return result


def _sku_contribution_table(sku_analysis: pd.DataFrame) -> pd.DataFrame:
    columns = {
        "_sku": "SKU",
        "_sku_name": "SKU名称",
        "_parent_asin": "父ASIN",
        "_size": "尺寸/规格",
        "_sku_role": "SKU经营角色",
        "_sales_amount": "销售额",
        "sales_share_line": "销售额占品线比例",
        "_sales_units": "销量",
        "units_share_line": "销量占品线比例",
        "_daily_units": "日均销量",
        "_average_price": "平均销售价格",
        "_gross_profit": "利润额",
        "_gross_margin": "利润率",
        "profit_share_line": "利润额占品线比例",
        "_ad_spend": "广告花费",
        "ad_spend_share_line": "广告花费占品线比例",
        "ad_spend_share_parent": "广告花费占父体比例",
        "sales_share_parent": "销售额占父体比例",
        "ad_sales_mismatch": "广告资源错配值",
        "ad_profit_mismatch": "广告利润错配值",
        "role_fulfillment": "角色履职判断",
        "_final_action": "系统final_action",
        "_system_priority": "系统priority",
    }
    existing = [column for column in columns if column in sku_analysis.columns]
    return sku_analysis[existing].rename(columns=columns).sort_values("销售额", ascending=False)


def _problem_skus(sku_analysis: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    if sku_analysis.empty:
        return pd.DataFrame()
    mask = (
        sku_analysis["_gross_profit"].lt(0)
        | sku_analysis["ad_sales_mismatch"].ge(0.15)
        | sku_analysis["ad_profit_mismatch"].ge(0.15).fillna(False)
        | sku_analysis["role_fulfillment"].isin(["角色失效", "角色履职偏弱"])
        | sku_analysis["_final_action"].isin(RISK_ACTIONS | URGENT_ACTIONS)
        | sku_analysis["_stock_days"].gt(90)
        | sku_analysis["_stock_days"].lt(30)
    )
    selected = sku_analysis[mask].copy()
    if selected.empty:
        return pd.DataFrame()
    selected["_priority_sort"] = selected["problem_priority"].map(PROBLEM_PRIORITY_ORDER).fillna(9)
    selected["_score"] = (
        selected["ad_sales_mismatch"].fillna(0).clip(lower=0)
        + selected["ad_profit_mismatch"].fillna(0).clip(lower=0)
        + selected["_gross_profit"].lt(0).astype(int)
    )
    selected = selected.sort_values(["_priority_sort", "_score", "_sales_amount"], ascending=[True, False, False]).head(top_n)
    return pd.DataFrame(
        {
            "SKU名称": selected["_sku_name"],
            "SKU": selected["_sku"],
            "经营角色": selected["_sku_role"],
            "问题事实": selected["problem_facts"],
            "父体比较": selected["parent_compare"],
            "品线比较": selected["line_compare"],
            "尺寸比较": selected["size_compare"],
            "价格带比较": selected["price_compare"],
            "问题判断": selected["problem_judgement"],
            "原因等级": selected["cause_level"],
            "验证动作": selected["validation_action"],
            "经营影响": selected["business_impact"],
            "建议动作": selected["suggested_action"],
            "问题优先级": selected["problem_priority"],
            "置信度": selected["confidence"],
            "系统final_action": selected["_final_action"],
            "系统priority": selected["_system_priority"],
        }
    )


def _opportunity_skus(sku_analysis: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
    if sku_analysis.empty:
        return pd.DataFrame()
    line_margin = _safe_divide(sku_analysis["_gross_profit"].sum(), sku_analysis["_sales_amount"].sum())
    line_acoas = _safe_divide(sku_analysis["_ad_spend"].sum(), sku_analysis["_sales_amount"].sum())
    healthy_stock = sku_analysis["_stock_days"].between(30, 120, inclusive="both") | sku_analysis["_stock_days"].isna()
    high_profit_low_invest = (
        sku_analysis["_gross_profit"].gt(0)
        & sku_analysis["_gross_margin"].gt(line_margin)
        & sku_analysis["ad_spend_share_line"].lt(sku_analysis["profit_share_line"].fillna(sku_analysis["sales_share_line"]))
        & healthy_stock
    )
    main_expand = (
        sku_analysis["_sku_role"].eq("主力 SKU")
        & sku_analysis["_gross_profit"].gt(0)
        & sku_analysis["_sales_amount"].ge(sku_analysis["_line_sales_median"])
        & sku_analysis["_acoas"].le(line_acoas)
        & healthy_stock
    )
    peer_outperform = (
        (~sku_analysis["size_under"])
        & (~sku_analysis["price_under"])
        & sku_analysis["comparison_ok_count"].ge(3)
        & sku_analysis["_gross_profit"].gt(0)
        & healthy_stock
    )
    selected = sku_analysis[high_profit_low_invest | main_expand | peer_outperform].copy()
    if selected.empty:
        return pd.DataFrame()
    selected["opportunity_type"] = np.select(
        [high_profit_low_invest.loc[selected.index], main_expand.loc[selected.index], peer_outperform.loc[selected.index]],
        ["高利润但投入不足", "主力SKU扩量空间", "同尺寸或同价格带表现较好"],
        default="稳健优化机会",
    )
    selected["_score"] = selected["_gross_profit"].clip(lower=0) + selected["_sales_amount"].clip(lower=0) * 0.05
    selected = selected.sort_values("_score", ascending=False).head(top_n)
    return pd.DataFrame(
        {
            "SKU名称": selected["_sku_name"],
            "SKU": selected["_sku"],
            "经营角色": selected["_sku_role"],
            "机会类型": selected["opportunity_type"],
            "机会事实": selected.apply(
                lambda row: (
                    f"利润率 {_fmt_pct(row['_gross_margin'])}，利润额 {_fmt_number(row['_gross_profit'])}，"
                    f"广告贡献 {_fmt_pct(row['ad_spend_share_line'])}，库存天数 {_fmt_number(row['_stock_days'])}"
                ),
                axis=1,
            ),
            "父体比较": selected["parent_compare"],
            "品线比较": selected["line_compare"],
            "尺寸比较": selected["size_compare"],
            "价格带比较": selected["price_compare"],
            "建议动作": selected.apply(_suggested_action, axis=1),
            "置信度": selected["confidence"],
            "系统final_action": selected["_final_action"],
        }
    )


def _action_items(problem_skus: pd.DataFrame, opportunity_skus: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for _, row in problem_skus.head(8).iterrows():
        rows.append(
            {
                "动作对象": row.get("SKU", ""),
                "动作内容": row.get("建议动作", ""),
                "动作原因": row.get("问题事实", ""),
                "预期改善指标": "广告花费占比、利润额、库存天数或断货风险",
                "复查周期": "7天复查一次；P0问题优先48小时内复查",
                "停止或调整条件": "若销售额、利润额或库存风险无改善，降低投入或执行系统 final_action",
            }
        )
    for _, row in opportunity_skus.head(5).iterrows():
        rows.append(
            {
                "动作对象": row.get("SKU", ""),
                "动作内容": row.get("建议动作", ""),
                "动作原因": row.get("机会事实", ""),
                "预期改善指标": "销售额、销量、利润额、ACOAS",
                "复查周期": "7-14天复查一次",
                "停止或调整条件": "若 ACOAS 高于利润承受能力或库存天数低于30天，暂停扩量",
            }
        )
    return pd.DataFrame(rows)


def _field_presence(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(False, index=df.index, dtype=bool)
    values = df[column]
    if pd.api.types.is_numeric_dtype(values):
        present = pd.to_numeric(values, errors="coerce").notna()
    else:
        text_values = values.astype("string").fillna("").str.strip()
        present = ~text_values.isin(["", "nan", "none", "<NA>"])

    missing_flag = f"_missing_{column}"
    if missing_flag in df.columns:
        present &= ~df[missing_flag].fillna(True).astype(bool)
    return present


def _field_completeness(df: pd.DataFrame, column: str) -> float:
    if df.empty:
        return 0.0
    return float(_field_presence(df, column).mean())


def _available_stock_days_completeness(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    available_source = _field_presence(df, "available_qty")
    fallback_source = _field_presence(df, "total_supply_qty") & _field_presence(df, "inbound_qty")
    sales_source = _field_presence(df, "sales_7d_units")
    return float(((available_source | fallback_source) & sales_source).mean())


def _data_credibility(df: pd.DataFrame, product_line: str) -> pd.DataFrame:
    if "product_line" in df.columns:
        line_mask = df["product_line"].astype("string").fillna("").str.strip().eq(str(product_line).strip())
        source = df[line_mask].copy()
    else:
        source = pd.DataFrame()

    def add_check(
        item: str,
        status: str,
        completeness: float | None,
        fact: str,
        gap: str,
        handling: str,
    ) -> dict[str, Any]:
        return {
            "检查项": item,
            "状态": status,
            "完整率": completeness,
            "已确认事实": fact,
            "缺失或冲突": gap,
            "当前处理": handling,
        }

    sku_ratio = _field_completeness(source, "sku")
    parent_ratio = _field_completeness(source, "parent_asin")
    profit_ratio = min(_field_completeness(source, "order_gross_profit"), _field_completeness(source, "order_gross_margin"))
    inventory_ratio = max(_available_stock_days_completeness(source), _field_completeness(source, "stock_days"))
    size_ratio = _field_completeness(source, "size")
    sales_ratio = max(_field_completeness(source, "sales_14d_amount"), _field_completeness(source, "sales_7d_amount"))
    ad_ratio = min(_field_completeness(source, "ad_spend"), _field_completeness(source, "ad_sales"))

    checks = [
        add_check(
            "SKU映射",
            "通过" if sku_ratio >= 0.99 else "无法判断",
            sku_ratio,
            f"SKU字段完整率 {_fmt_pct(sku_ratio)}。",
            "" if sku_ratio >= 0.99 else "存在空SKU，无法稳定定位行动对象。",
            "保留现有SKU映射" if sku_ratio >= 0.99 else "先补齐SKU并复核重复映射。",
        ),
        add_check(
            "父体映射",
            "通过" if parent_ratio >= 0.95 else "待补充",
            parent_ratio,
            f"父ASIN完整率 {_fmt_pct(parent_ratio)}。",
            "" if parent_ratio >= 0.95 else "部分SKU无法完成父体横向比较。",
            "保留父体比较" if parent_ratio >= 0.95 else "补齐父ASIN后重新生成父体比较。",
        ),
        add_check(
            "销售与广告时间窗口",
            "待确认",
            min(sales_ratio, ad_ratio),
            f"销售字段完整率 {_fmt_pct(sales_ratio)}，广告字段完整率 {_fmt_pct(ad_ratio)}。",
            "缺少报表起止日期和广告归因周期，无法确认销售与广告是否属于同一窗口。",
            "当前仅输出关系异常，不把广告与销量变化描述为确定因果。",
        ),
        add_check(
            "利润口径",
            "待确认" if profit_ratio >= 0.95 else "无法判断",
            profit_ratio,
            f"毛利润与毛利率字段完整率 {_fmt_pct(profit_ratio)}。",
            "无法确认毛利润是否包含广告费、平台费、仓储费、促销成本和退款。",
            "使用现有毛利润判断实际贡献，同时要求运营确认利润公式。",
        ),
        add_check(
            "库存口径",
            "通过" if inventory_ratio >= 0.95 else "无法判断",
            inventory_ratio,
            f"库存天数字段完整率 {_fmt_pct(inventory_ratio)}。",
            "" if inventory_ratio >= 0.95 else "缺少可售库存天数，周转优先级无法可靠判断。",
            "优先使用可售库存天数" if inventory_ratio >= 0.95 else "补充可售库存、在途和7天日均销量。",
        ),
        add_check(
            "尺寸/规格比较",
            "通过" if size_ratio >= 0.8 else "待补充",
            size_ratio,
            f"尺寸/规格字段完整率 {_fmt_pct(size_ratio)}。",
            "" if size_ratio >= 0.8 else "同尺寸样本不足时不得输出确定性尺寸结论。",
            "使用同尺寸比较" if size_ratio >= 0.8 else "标记低置信度并补充尺寸/规格字段。",
        ),
        add_check(
            "自身历史对比",
            "待补充",
            None,
            "当前文件主要是截面数据。",
            "缺少连续历史窗口、活动期、断货期和调价期标记。",
            "不把短期波动写成趋势因果；建议补充至少4周历史数据。",
        ),
    ]
    return pd.DataFrame(checks)


def _relationship_diagnostics(
    line_df: pd.DataFrame,
    sku_analysis: pd.DataFrame,
    data_credibility: pd.DataFrame,
    opportunity_skus: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(
        business_order: str,
        relation: str,
        fact: str,
        cause_level: str,
        diagnosis: str,
        impact: str,
        missing: str,
        validation: str,
        action: str,
        priority: str,
        status: str,
    ) -> None:
        rows.append(
            {
                "经营顺序": business_order,
                "诊断关系": relation,
                "已确认事实": fact,
                "原因等级": cause_level,
                "诊断判断": diagnosis,
                "经营影响": impact,
                "缺失数据": missing,
                "验证动作": validation,
                "建议动作": action,
                "报告优先级": priority,
                "行动状态": status,
            }
        )

    stock_days = pd.to_numeric(line_df["_stock_days"], errors="coerce")
    inventory_qty = pd.to_numeric(line_df["_inventory_qty"], errors="coerce").fillna(0.0)
    over_180 = int((stock_days > 180).sum())
    over_90 = int((stock_days > 90).sum())
    main_stockout = int(((sku_analysis["_sku_role"] == "主力 SKU") & (sku_analysis["_stock_days"] < 30)).sum())
    weighted_stock_days = _safe_divide((stock_days.fillna(0.0) * inventory_qty).sum(), inventory_qty.sum())
    if over_180 > 0 or main_stockout > 0:
        add(
            "周转",
            "库存-销量-资金",
            f"加权库存天数 {_fmt_number(weighted_stock_days)}；180天以上SKU {over_180}个；主力缺货风险SKU {main_stockout}个。",
            "已确认原因",
            "品线存在超长库存或核心SKU缺货风险，资金效率与规模承接发生冲突。",
            "可能造成资金长期占用，或因主力断货损失排名与规模。",
            "补货周期、活动计划、未来流量计划",
            "逐SKU核对在途、补货周期和未来14天日销量计划。",
            "先执行系统库存动作；超长库存停补清理，主力缺货优先保障库存和核心流量。",
            "P0",
            "需处理",
        )
    elif over_90 > 0:
        add(
            "周转",
            "库存-销量-资金",
            f"加权库存天数 {_fmt_number(weighted_stock_days)}；90天以上SKU {over_90}个。",
            "高概率原因",
            "库存消化速度可能低于资金承诺，需验证未来销量计划能否覆盖库存。",
            "现金占用增加，继续补货可能恶化周转。",
            "补货周期、活动计划和目标日销量",
            "按SKU测算30/60/90天库存消化目标并与实际日销量对比。",
            "控制补货，优先通过有效广告、价格或活动计划加速周转。",
            "P1",
            "需处理",
        )
    else:
        add(
            "周转",
            "库存-销量-资金",
            f"加权库存天数 {_fmt_number(weighted_stock_days)}，当前未发现90天以上SKU。",
            "已确认原因",
            "当前库存处于可承接区间。",
            "周转风险暂时可控。",
            "补货周期与未来活动计划",
            "持续按7天窗口复核库存天数。",
            "维持当前库存纪律，不因高毛利盲目补货。",
            "P3",
            "正常",
        )

    line_sales = float(line_df["_sales_amount"].sum())
    _, top_sales_share = _top_contribution(line_df["_sales_amount"], line_sales)
    main_sales_share = float(sku_analysis.loc[sku_analysis["_sku_role"] == "主力 SKU", "sales_share_line"].sum())
    if not pd.isna(top_sales_share) and top_sales_share >= 0.8:
        add(
            "规模",
            "规模-集中度-角色",
            f"销售额前20% SKU贡献 {_fmt_pct(top_sales_share)}；主力SKU销售额贡献 {_fmt_pct(main_sales_share)}。",
            "高概率原因",
            "品线规模高度依赖少数SKU，需要确认核心SKU库存和流量承接是否稳定。",
            "单SKU波动可能显著影响整条品线规模。",
            "自身历史趋势、活动期和断货期标记",
            "固定4周窗口比较核心SKU销量、CVR、库存和广告效率。",
            "保护核心SKU库存与有效流量，同时减少非核心SKU对资源的分流。",
            "P1",
            "需处理",
        )
    else:
        add(
            "规模",
            "规模-集中度-角色",
            f"销售额前20% SKU贡献 {_fmt_pct(top_sales_share)}；主力SKU销售额贡献 {_fmt_pct(main_sales_share)}。",
            "已确认原因",
            "当前规模集中度未达到高度依赖水平。",
            "品线对单一SKU的依赖相对可控。",
            "自身历史趋势",
            "按周观察主力SKU销售额贡献变化。",
            "维持资源集中度，避免无依据地平均分配广告和库存。",
            "P3",
            "正常",
        )

    line_profit = float(line_df["_gross_profit"].sum())
    line_margin = _safe_divide(line_profit, line_sales)
    negative_profit_count = int((line_df["_gross_profit"] < 0).sum())
    if line_profit <= 0:
        add(
            "毛利润",
            "规模-毛利润",
            f"品线毛利润 {_fmt_number(line_profit)}；亏损SKU {negative_profit_count}个；加权毛利率 {_fmt_pct(line_margin)}。",
            "已确认原因",
            "品线当前没有形成正向实际利润贡献。",
            "继续扩大规模可能放大亏损并占用现金。",
            "完整成本构成与退款、促销成本",
            "复核毛利润公式，并拆分价格、成本、广告和促销影响。",
            "暂停无利润支撑的扩量，优先修复单位利润和广告资源错配。",
            "P0",
            "需处理",
        )
    elif negative_profit_count > 0:
        add(
            "毛利润",
            "规模-毛利润",
            f"品线毛利润 {_fmt_number(line_profit)}；仍有 {negative_profit_count} 个亏损SKU。",
            "高概率原因",
            "正利润SKU可能在补贴亏损SKU，需要识别亏损是否承担明确引流或战略价值。",
            "亏损SKU会稀释品线现金贡献。",
            "完整成本构成、引流带动价值",
            "比较亏损SKU广告、销量和父体支持贡献，确认是否值得保留。",
            "保留有明确带动价值的引流SKU；其余亏损SKU限期修复或退出。",
            "P1",
            "需处理",
        )
    else:
        add(
            "毛利润",
            "规模-毛利润",
            f"品线毛利润 {_fmt_number(line_profit)}，当前SKU均未出现负毛利润。",
            "已确认原因",
            "品线当前形成正向利润贡献。",
            "利润风险暂时可控。",
            "完整成本构成",
            "持续复核毛利润而非只看毛利率。",
            "优先扩大能同时贡献规模、毛利润和周转的SKU。",
            "P3",
            "正常",
        )

    line_ad_spend = float(line_df["_ad_spend"].sum())
    line_acoas = _safe_divide(line_ad_spend, line_sales)
    ad_mismatch_count = int((sku_analysis["ad_sales_mismatch"] >= 0.15).sum())
    if line_ad_spend > 0 and not pd.isna(line_margin) and line_acoas >= line_margin:
        add(
            "毛利润",
            "广告-销售-利润",
            f"品线ACOAS {_fmt_pct(line_acoas)}，加权毛利率 {_fmt_pct(line_margin)}；广告错配SKU {ad_mismatch_count}个。",
            "高概率原因",
            "广告花费占销售额比例已触及或超过利润空间，广告可能放大利润压力。",
            "继续按历史结构投放可能挤压实际毛利润。",
            "广告归因周期、自然订单变化、搜索词明细",
            "固定7天窗口拆分广告与自然销量，验证核心词和低效词的真实贡献。",
            "保留核心流量，降低高花费低转化投放，并对无订单搜索词做否定。",
            "P1" if line_profit > 0 else "P0",
            "需处理",
        )
    elif ad_mismatch_count > 0:
        add(
            "毛利润",
            "广告-销售-利润",
            f"品线ACOAS {_fmt_pct(line_acoas)}；{ad_mismatch_count}个SKU广告贡献比销售贡献高15个百分点以上。",
            "高概率原因",
            "广告资源可能没有投向最有承接能力的SKU。",
            "资源错配会降低品线投入回报。",
            "搜索词、自然订单和广告归因周期",
            "对比调整前后销量、CVR、ACOAS和毛利润。",
            "从低效异常SKU回收预算，优先保障主力SKU和可承接的利润SKU。",
            "P1",
            "需处理",
        )
    else:
        add(
            "毛利润",
            "广告-销售-利润",
            f"品线ACOAS {_fmt_pct(line_acoas)}，未发现明显广告销售贡献错配。",
            "已确认原因",
            "当前广告投入与销售贡献关系相对匹配。",
            "广告风险暂时可控。",
            "自然订单变化和广告归因周期",
            "维持7天复核窗口。",
            "保持角色化预算分配，不按历史预算惯性延续。",
            "P3",
            "正常",
        )

    high_margin_slow = sku_analysis[(sku_analysis["_gross_margin"] > line_margin) & (sku_analysis["_stock_days"] > 90)]
    if not high_margin_slow.empty:
        add(
            "毛利率",
            "毛利率-周转",
            f"{len(high_margin_slow)}个SKU毛利率高于品线但库存天数超过90天。",
            "已确认原因",
            "高毛利没有转化为有效周转和现金回收。",
            "账面利润空间被库存占用。",
            "未来活动计划和目标日销量",
            "为每个SKU测算60/90天库存消化所需日销量。",
            "停止把高毛利等同于优质SKU；控制补货并设计低风险周转实验。",
            "P1",
            "需处理",
        )

    credibility_issues = data_credibility[data_credibility["状态"] != "通过"]
    critical_data_issue = credibility_issues[
        credibility_issues["检查项"].isin(["SKU映射", "利润口径", "库存口径"])
        & credibility_issues["状态"].eq("无法判断")
    ]
    if not credibility_issues.empty:
        add(
            "数据可信度",
            "数据-结论",
            f"{len(credibility_issues)}项数据检查未完全通过。",
            "无法判断" if not critical_data_issue.empty else "待验证假设",
            "部分经营结论只能作为验证方向，不能描述为确定因果。",
            "错误口径可能导致错误补货、停投或调价。",
            "；".join(credibility_issues["缺失或冲突"].astype(str).tolist()),
            "先补齐关键字段并固定销售、广告、利润和库存的同一时间窗口。",
            "仅执行低风险动作；对不可逆动作等待数据确认。",
            "P0" if not critical_data_issue.empty else "P3",
            "待验证",
        )

    if not opportunity_skus.empty:
        top = opportunity_skus.iloc[0]
        add(
            "规模",
            "资源-机会",
            f"发现 {len(opportunity_skus)} 个机会SKU；首要机会为 {top.get('SKU', '')}（{top.get('机会类型', '')}）。",
            "高概率原因" if top.get("置信度") != "低" else "待验证假设",
            "存在已有承接能力但资源不足的SKU，可通过局部实验验证扩量。",
            "若验证成立，可提升规模和毛利润而不显著破坏周转。",
            "实验前后自然销量、CVR和广告关键词明细",
            "选择单SKU和对照SKU，固定7-14天观察窗口。",
            "小预算增加高转化关键词覆盖，达到标准后再扩大。",
            "P1" if top.get("置信度") != "低" else "P2",
            "机会",
        )

    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["_priority_sort"] = result["报告优先级"].map(PROBLEM_PRIORITY_ORDER).fillna(9)
    result["_business_sort"] = result["经营顺序"].map(BUSINESS_PRIORITY_ORDER).fillna(9)
    return result.sort_values(["_priority_sort", "_business_sort"]).drop(columns=["_priority_sort", "_business_sort"])


def _todo_success_standard(problem: str, action: str) -> str:
    text = f"{problem} {action}"
    if "库存" in text or "补货" in text or "断货" in text:
        return "可售库存天数进入30-90天目标区间；主力SKU无断货；不新增90天以上库存。"
    if "广告" in text or "投放" in text or "搜索词" in text:
        return "广告资源错配值降至10个百分点以内；ACOAS低于可承受利润空间；毛利润不下降。"
    if "利润" in text or "成本" in text:
        return "毛利润转正或较基准期改善；销售额不出现不可接受下降。"
    if "规模" in text or "流量" in text or "扩量" in text:
        return "销量和销售额较基准期提升，同时毛利润不下降、库存天数不低于30天。"
    if "数据" in text or "字段" in text or "口径" in text:
        return "关键字段完整率达到95%以上，销售/广告/利润/库存时间窗口得到确认。"
    return "目标指标较基准期改善，并且周转、毛利润和风险指标未恶化。"


def _todo_failure_plan(problem: str, action: str) -> str:
    text = f"{problem} {action}"
    if "广告" in text or "扩量" in text:
        return "若观察期内ACOAS上升、毛利润下降或库存低于30天，恢复原预算并停止扩量。"
    if "价格" in text or "促销" in text:
        return "若销量提升不足以覆盖利润损失，恢复原价并停止同类SKU扩展。"
    if "库存" in text or "补货" in text:
        return "若实际销量未达到消化目标，继续停补并升级清货；若出现缺货风险，缩减广告并调整补货节奏。"
    if "数据" in text or "字段" in text:
        return "关键口径仍无法确认时，不执行不可逆的停投、清货或全量调价。"
    return "若成功标准未达到，缩小范围、恢复原方案或终止实验，并记录失败原因。"


def _todo_schedule(priority: str, start_date: date) -> tuple[str, str, str]:
    days_by_priority = {"P0": 2, "P1": 7, "P2": 14, "P3": 30}
    observation_by_priority = {"P0": "3天", "P1": "7天", "P2": "14天", "P3": "14-30天"}
    due_date = start_date + timedelta(days=days_by_priority.get(priority, 14))
    return start_date.isoformat(), due_date.isoformat(), observation_by_priority.get(priority, "14天")


def _product_line_todo_list(
    product_line: str,
    relationship_diagnostics: pd.DataFrame,
    problem_skus: pd.DataFrame,
    opportunity_skus: pd.DataFrame,
    owner: str,
    start_date: date,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    def add_row(
        priority: str,
        business_order: str,
        level: str,
        target: str,
        problem: str,
        evidence: str,
        cause_level: str,
        impact: str,
        action: str,
        system_action: str = "",
        system_priority: str = "",
    ) -> None:
        start, due, observation = _todo_schedule(priority, start_date)
        rows.append(
            {
                "状态": "待开始",
                "报告优先级": priority,
                "经营顺序": business_order,
                "层级": level,
                "对象": target,
                "问题": problem,
                "证据": evidence,
                "原因等级": cause_level,
                "经营影响": impact,
                "动作": action,
                "负责人": owner or "待指定",
                "开始时间": start,
                "完成时间": due,
                "观察周期": observation,
                "成功标准": _todo_success_standard(problem, action),
                "失败预案": _todo_failure_plan(problem, action),
                "系统final_action": system_action,
                "系统priority": system_priority,
            }
        )

    actionable = relationship_diagnostics[relationship_diagnostics["行动状态"].isin(["需处理", "待验证", "机会"])]
    for _, row in actionable.head(8).iterrows():
        add_row(
            str(row.get("报告优先级", "P2")),
            str(row.get("经营顺序", "规模")),
            "品线",
            product_line,
            f"{row.get('诊断关系', '')}：{row.get('诊断判断', '')}",
            str(row.get("已确认事实", "")),
            str(row.get("原因等级", "待验证假设")),
            str(row.get("经营影响", "")),
            str(row.get("建议动作", "")),
        )

    for _, row in problem_skus.head(10).iterrows():
        problem_text = str(row.get("问题事实", ""))
        business_order = "周转" if any(term in problem_text for term in ["库存", "断货"]) else "毛利润"
        if "规模型主力" in str(row.get("问题判断", "")):
            business_order = "规模"
        add_row(
            str(row.get("问题优先级", "P2")),
            business_order,
            "SKU",
            str(row.get("SKU", "")),
            problem_text,
            f"{row.get('父体比较', '')} {row.get('品线比较', '')}",
            str(row.get("原因等级", "待验证假设")),
            str(row.get("经营影响", "")),
            str(row.get("建议动作", "")),
            str(row.get("系统final_action", "")),
            str(row.get("系统priority", "")),
        )

    for _, row in opportunity_skus.head(5).iterrows():
        role = str(row.get("经营角色", ""))
        business_order = "规模" if role in {"引流 SKU", "主力 SKU"} else "毛利润"
        add_row(
            "P1" if row.get("置信度") != "低" else "P2",
            business_order,
            "SKU",
            str(row.get("SKU", "")),
            f"机会：{row.get('机会类型', '')}",
            str(row.get("机会事实", "")),
            "高概率原因" if row.get("置信度") != "低" else "待验证假设",
            "若验证成立，可提高资源投入回报。",
            str(row.get("建议动作", "")),
            str(row.get("系统final_action", "")),
            "",
        )

    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result = result.drop_duplicates(subset=["层级", "对象", "问题"], keep="first")
    result["_priority_sort"] = result["报告优先级"].map(PROBLEM_PRIORITY_ORDER).fillna(9)
    result["_business_sort"] = result["经营顺序"].map(BUSINESS_PRIORITY_ORDER).fillna(9)
    return result.sort_values(["_priority_sort", "_business_sort", "对象"]).drop(columns=["_priority_sort", "_business_sort"])


def _conclusions(
    product_line: str,
    line_df: pd.DataFrame,
    core_metrics: pd.DataFrame,
    problem_skus: pd.DataFrame,
    opportunity_skus: pd.DataFrame,
) -> list[str]:
    sales = line_df["_sales_amount"].sum()
    units = line_df["_sales_units"].sum()
    profit = line_df["_gross_profit"].sum()
    margin = _safe_divide(profit, sales)
    ad_spend = line_df["_ad_spend"].sum()
    acoas = _safe_divide(ad_spend, sales)
    parent_count = line_df["_parent_asin"].replace("", pd.NA).dropna().nunique()
    sales_row = core_metrics[core_metrics["指标"] == "销售额"]
    concentration = sales_row["判断"].iloc[0] if not sales_row.empty else ""
    top_problem = problem_skus.iloc[0]["问题事实"] if not problem_skus.empty else "暂无 P0/P1 级确定问题"
    top_opportunity = opportunity_skus.iloc[0]["机会类型"] if not opportunity_skus.empty else "暂无高置信度扩量机会"
    return [
        f"{product_line} 当前覆盖 {len(line_df)} 个 SKU、{parent_count} 个父ASIN，销售额 {_fmt_number(sales)}，销量 {_fmt_int(units)}；{concentration}",
        f"品线利润额 {_fmt_number(profit)}，加权利润率 {_fmt_pct(margin)}，该利润率按利润额合计除以销售额合计计算。",
        f"品线广告花费 {_fmt_number(ad_spend)}，ACOAS {_fmt_pct(acoas)}；需要重点检查广告资源是否与销售和利润贡献匹配。",
        f"当前最大问题：{top_problem}。",
        f"当前最大机会：{top_opportunity}。",
    ]


def build_product_line_diagnosis(
    df: pd.DataFrame,
    product_line: str,
    top_n: int = 20,
    owner: str = "待指定",
    start_date: date | None = None,
) -> dict[str, Any]:
    todo_start_date = start_date or date.today()
    prepared = _prepare(df)
    line_df = _line_scope(prepared, product_line)
    if line_df.empty:
        empty = pd.DataFrame()
        return {
            "product_line": product_line,
            "conclusions": [f"未找到品线：{product_line}。"],
            "data_credibility": empty,
            "core_metrics": empty,
            "relationship_diagnostics": empty,
            "role_structure": empty,
            "sku_contribution": empty,
            "problem_skus": empty,
            "opportunity_skus": empty,
            "todo_list": empty,
            "action_items": empty,
        }
    line_df = _add_shares(line_df, prepared)
    sku_analysis = _build_sku_analysis(line_df, prepared)
    core_metrics = _core_metrics(line_df)
    role_structure = _role_structure(line_df)
    sku_contribution = _sku_contribution_table(sku_analysis)
    problem_skus = _problem_skus(sku_analysis, top_n)
    opportunity_skus = _opportunity_skus(sku_analysis)
    data_credibility = _data_credibility(df, product_line)
    relationship_diagnostics = _relationship_diagnostics(line_df, sku_analysis, data_credibility, opportunity_skus)
    todo_list = _product_line_todo_list(
        product_line,
        relationship_diagnostics,
        problem_skus,
        opportunity_skus,
        owner,
        todo_start_date,
    )
    return {
        "product_line": product_line,
        "conclusions": _conclusions(product_line, line_df, core_metrics, problem_skus, opportunity_skus),
        "data_credibility": data_credibility,
        "core_metrics": core_metrics,
        "relationship_diagnostics": relationship_diagnostics,
        "role_structure": role_structure,
        "sku_contribution": sku_contribution,
        "problem_skus": problem_skus,
        "opportunity_skus": opportunity_skus,
        "todo_list": todo_list,
        "action_items": todo_list,
    }
