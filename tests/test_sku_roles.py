import pandas as pd

from modules.sku_roles import build_sku_role_reports, classify_sku_roles


def test_sku_roles_are_parent_relative_and_mutually_exclusive():
    df = pd.DataFrame(
        {
            "sku": ["MAIN", "PROFIT", "TRAFFIC", "LOW"],
            "parent_asin": ["P1", "P1", "P1", "P1"],
            "sales_14d_units": [100, 20, 40, 0],
            "sales_7d_amount": [1500, 600, 800, 200],
            "sales_14d_amount": [1000, 300, 400, 0],
            "ad_spend": [50, 0, 200, 30],
            "ad_sales": [500, 0, 300, 0],
            "ad_impressions": [1000, 100, 2000, 100],
            "ad_clicks": [100, 5, 200, 10],
            "order_gross_profit": [100, 90, 10, -5],
            "order_gross_margin": [0.10, 0.30, 0.03, -0.10],
            "acos": [0.05, 0.00, 0.67, 0.00],
            "available_stock_qty": [100, 50, 80, 500],
            "available_stock_days": [30, 40, 40, 200],
            "stock_days": [30, 40, 40, 200],
            "main_daily_sales": [7, 2, 3, 0],
            "total_supply_qty": [100, 50, 80, 500],
            "recommended_replenishment_qty": [10, 0, 0, 0],
            "final_action": ["正常补货", "观察", "控广告", "清货处理"],
            "priority": ["P2", "P4", "P2", "P0"],
            "reason": ["", "", "", ""],
        }
    )

    result = classify_sku_roles(df)

    assert result["sku_role"].notna().all()
    assert result["sku_role"].isin(["引流 SKU", "主力 SKU", "利润 SKU", "低效异常 SKU"]).all()
    assert result.loc[result["sku"] == "MAIN", "sku_role"].iloc[0] == "主力 SKU"
    assert result.loc[result["sku"] == "PROFIT", "sku_role"].iloc[0] == "利润 SKU"
    assert result.loc[result["sku"] == "TRAFFIC", "sku_role"].iloc[0] == "引流 SKU"
    assert result.loc[result["sku"] == "LOW", "sku_role"].iloc[0] == "低效异常 SKU"
    assert "引流候选" in result.loc[result["sku"] == "TRAFFIC", "sku_role_candidates"].iloc[0]
    assert result.loc[result["sku"] == "LOW", "sku_role_candidates"].iloc[0] == "低效异常候选"
    assert result.loc[result["sku"] == "LOW", "final_action"].iloc[0] == "清货处理"
    assert result.loc[result["sku"] == "TRAFFIC", "sku_ad_spend_share_in_parent"].iloc[0] > 0.35
    assert result.loc[result["sku"] == "MAIN", "role_daily_sales"].iloc[0] > result.loc[
        result["sku"] == "MAIN", "parent_avg_role_daily_sales"
    ].iloc[0]
    parent_margin = result.loc[result["sku"] == "MAIN", "parent_order_gross_margin"].iloc[0]
    assert parent_margin == (100 + 90 + 10 - 5) / (1500 + 600 + 800 + 200)
    assert result.loc[result["sku"] == "MAIN", "order_gross_margin"].iloc[0] > parent_margin


def test_parent_average_uses_child_arithmetic_mean_by_parent_asin():
    df = pd.DataFrame(
        {
            "sku": ["P1-A", "P1-B", "P2-A", "P2-B"],
            "parent_asin": ["P1", "P1", "P2", "P2"],
            "current_daily_sales_units": [4, 6, 40, 60],
            "sales_14d_units": [56, 84, 560, 840],
            "sales_7d_amount": [100, 200, 1000, 2000],
            "sales_14d_amount": [100, 200, 1000, 2000],
            "order_gross_profit": [10, 30, 100, 300],
            "order_gross_margin": [0.10, 0.20, 0.12, 0.22],
            "available_stock_qty": [20, 20, 20, 20],
            "available_stock_days": [20, 20, 20, 20],
            "main_daily_sales": [4, 6, 40, 60],
            "total_supply_qty": [20, 20, 20, 20],
            "ad_spend": [0, 0, 0, 0],
            "ad_sales": [0, 0, 0, 0],
            "final_action": ["观察", "观察", "观察", "观察"],
            "priority": ["P4", "P4", "P4", "P4"],
            "reason": ["", "", "", ""],
        }
    )

    result = classify_sku_roles(df)

    assert result.loc[result["sku"] == "P1-A", "parent_avg_role_daily_sales"].iloc[0] == 5
    assert result.loc[result["sku"] == "P1-B", "parent_avg_role_daily_sales"].iloc[0] == 5
    assert result.loc[result["sku"] == "P2-A", "parent_avg_role_daily_sales"].iloc[0] == 50
    assert result.loc[result["sku"] == "P2-B", "parent_avg_role_daily_sales"].iloc[0] == 50
    assert result.loc[result["sku"] == "P1-B", "sku_role"].iloc[0] == "主力 SKU"
    assert result.loc[result["sku"] == "P2-B", "sku_role"].iloc[0] == "主力 SKU"


def test_role_reports_partition_all_skus():
    df = pd.DataFrame(
        {
            "sku": ["A", "B"],
            "parent_asin": ["P1", "P1"],
            "sales_14d_units": [10, 0],
            "sales_14d_amount": [100, 0],
            "order_gross_profit": [20, -1],
            "order_gross_margin": [0.2, -0.1],
            "available_stock_qty": [20, 100],
            "available_stock_days": [20, 200],
            "main_daily_sales": [1, 0],
            "total_supply_qty": [20, 100],
            "ad_spend": [0, 0],
            "ad_sales": [0, 0],
            "final_action": ["观察", "清货处理"],
            "priority": ["P4", "P0"],
            "reason": ["", ""],
        }
    )

    result = classify_sku_roles(df)
    reports = build_sku_role_reports(result)

    report_skus = set().union(*(set(report["sku"].dropna()) for report in reports.values()))
    assert report_skus == {"A", "B"}
    assert sum(len(report) for report in reports.values()) == len(result)


def test_traffic_rule_takes_priority_when_multiple_role_conditions_match():
    df = pd.DataFrame(
        {
            "sku": ["A", "B"],
            "parent_asin": ["P1", "P1"],
            "sales_14d_units": [100, 10],
            "sales_7d_amount": [1500, 100],
            "sales_14d_amount": [1000, 100],
            "order_gross_profit": [300, 5],
            "order_gross_margin": [0.30, 0.05],
            "available_stock_qty": [20, 20],
            "available_stock_days": [20, 20],
            "main_daily_sales": [10, 1],
            "total_supply_qty": [20, 20],
            "ad_spend": [80, 20],
            "ad_sales": [500, 50],
            "final_action": ["观察", "观察"],
            "priority": ["P4", "P4"],
            "reason": ["", ""],
        }
    )

    result = classify_sku_roles(df)

    row = result[result["sku"] == "A"].iloc[0]
    assert "引流候选" in row["sku_role_candidates"]
    assert "主力候选" in row["sku_role_candidates"]
    assert "利润候选" in row["sku_role_candidates"]
    assert row["sku_role"] == "引流 SKU"


def test_role_reports_classify_missing_role_columns_with_filtered_index():
    df = pd.DataFrame(
        {
            "sku": ["A", "B"],
            "parent_asin": ["P1", "P1"],
            "sales_14d_units": [10, 0],
            "sales_14d_amount": [100, 0],
            "order_gross_profit": [20, -1],
            "order_gross_margin": [0.2, -0.1],
            "available_stock_qty": [20, 100],
            "available_stock_days": [20, 200],
            "main_daily_sales": [1, 0],
            "total_supply_qty": [20, 100],
            "ad_spend": [0, 0],
            "ad_sales": [0, 0],
            "final_action": ["观察", "清货处理"],
            "priority": ["P4", "P0"],
            "reason": ["", ""],
        },
        index=[10, 20],
    )

    reports = build_sku_role_reports(df)

    report_skus = set().union(*(set(report["sku"].dropna()) for report in reports.values()))
    assert report_skus == {"A", "B"}
