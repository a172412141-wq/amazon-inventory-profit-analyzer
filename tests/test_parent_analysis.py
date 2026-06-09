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
