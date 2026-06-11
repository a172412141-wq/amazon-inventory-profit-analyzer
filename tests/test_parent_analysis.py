import pandas as pd

from modules.parent_analysis import analyze_parent


def test_parent_analysis_handles_missing_numeric_values():
    df = pd.DataFrame(
        {
            "parent_asin": ["P1", "P1"],
            "sku": ["A", "B"],
            "spu": ["S1", "S1"],
            "product_line": ["L1", "L1"],
            "sales_14d_units": [pd.NA, 10],
            "total_supply_qty": [pd.NA, 50],
            "ad_spend": [pd.NA, 20],
            "order_gross_profit": [pd.NA, 100],
            "order_gross_margin": [pd.NA, 0.2],
            "stock_days": [pd.NA, 50],
        }
    )

    summary, anomalies = analyze_parent(df, {"inventory": {"healthy_max_days": 60, "urgent_redline_days": 180}})

    assert len(summary) == 1
    assert isinstance(anomalies, pd.DataFrame)


def test_parent_margin_uses_profit_sum_divided_by_sales_amount_sum():
    df = pd.DataFrame(
        {
            "parent_asin": ["P1", "P1"],
            "sku": ["A", "B"],
            "spu": ["S1", "S1"],
            "product_line": ["L1", "L1"],
            "sales_7d_units": [10, 10],
            "sales_14d_units": [20, 20],
            "sales_7d_amount": [100, 300],
            "sales_14d_amount": [200, 600],
            "total_supply_qty": [20, 20],
            "available_stock_qty": [20, 20],
            "ad_spend": [0, 0],
            "ad_sales": [0, 0],
            "order_gross_profit": [10, 30],
            "order_gross_margin": [0.90, 0.20],
            "stock_days": [20, 20],
        }
    )

    summary, _ = analyze_parent(df, {"inventory": {"healthy_max_days": 60, "urgent_redline_days": 180}})

    assert summary.loc[0, "order_gross_margin"] == 0.10


def test_parent_analysis_sums_aged_inventory_90_plus():
    df = pd.DataFrame(
        {
            "parent_asin": ["P1", "P1"],
            "sku": ["A", "B"],
            "spu": ["S1", "S1"],
            "product_line": ["L1", "L1"],
            "sales_7d_units": [7, 7],
            "sales_14d_units": [14, 14],
            "sales_7d_amount": [100, 200],
            "total_supply_qty": [20, 20],
            "available_stock_qty": [20, 20],
            "ad_spend": [0, 0],
            "ad_sales": [0, 0],
            "order_gross_profit": [10, 20],
            "order_gross_margin": [0.1, 0.1],
            "aged_inventory_90_plus": [5, 8],
        }
    )

    summary, _ = analyze_parent(df, {"inventory": {"healthy_max_days": 60, "urgent_redline_days": 180}})

    assert summary.loc[0, "aged_inventory_90_plus"] == 13


def test_parent_analysis_calculates_acoas_from_total_sales_amount():
    df = pd.DataFrame(
        {
            "parent_asin": ["P1", "P1"],
            "sku": ["A", "B"],
            "spu": ["S1", "S1"],
            "product_line": ["L1", "L1"],
            "sales_7d_units": [7, 7],
            "sales_14d_units": [14, 14],
            "sales_7d_amount": [100, 300],
            "sales_14d_amount": [200, 600],
            "total_supply_qty": [20, 20],
            "available_stock_qty": [20, 20],
            "ad_spend": [10, 30],
            "ad_sales": [100, 300],
            "order_gross_profit": [10, 30],
            "order_gross_margin": [0.1, 0.1],
        }
    )

    summary, _ = analyze_parent(df, {"inventory": {"healthy_max_days": 60, "urgent_redline_days": 180}})

    assert summary.loc[0, "acoas"] == 0.05
