from __future__ import annotations

from math import ceil
from typing import Any

import numpy as np
import pandas as pd


PROBLEM_PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}
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
) -> dict[str, Any]:
    prepared = _prepare(df)
    line_df = _line_scope(prepared, product_line)
    if line_df.empty:
        empty = pd.DataFrame()
        return {
            "product_line": product_line,
            "conclusions": [f"未找到品线：{product_line}。"],
            "core_metrics": empty,
            "role_structure": empty,
            "sku_contribution": empty,
            "problem_skus": empty,
            "opportunity_skus": empty,
            "action_items": empty,
        }
    line_df = _add_shares(line_df, prepared)
    sku_analysis = _build_sku_analysis(line_df, prepared)
    core_metrics = _core_metrics(line_df)
    role_structure = _role_structure(line_df)
    sku_contribution = _sku_contribution_table(sku_analysis)
    problem_skus = _problem_skus(sku_analysis, top_n)
    opportunity_skus = _opportunity_skus(sku_analysis)
    action_items = _action_items(problem_skus, opportunity_skus)
    return {
        "product_line": product_line,
        "conclusions": _conclusions(product_line, line_df, core_metrics, problem_skus, opportunity_skus),
        "core_metrics": core_metrics,
        "role_structure": role_structure,
        "sku_contribution": sku_contribution,
        "problem_skus": problem_skus,
        "opportunity_skus": opportunity_skus,
        "action_items": action_items,
    }
