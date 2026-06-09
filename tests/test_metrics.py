import math

import pandas as pd

from modules.cleaning import clean_data
from modules.metrics import calculate_metrics


def test_main_daily_sales_uses_max_candidate():
    df = pd.DataFrame(
        {
            "sales_7d_units": [14],
            "sales_14d_units": [14],
            "predicted_daily_sales": [1.5],
            "total_supply_qty": [100],
        }
    )

    result = calculate_metrics(df)

    assert result.loc[0, "avg_sales_7d"] == 2
    assert result.loc[0, "avg_sales_14d"] == 1
    assert result.loc[0, "main_daily_sales"] == 2


def test_stock_days_avoids_division_by_zero():
    df = pd.DataFrame(
        {
            "sales_7d_units": [0],
            "sales_14d_units": [0],
            "predicted_daily_sales": [0],
            "total_supply_qty": [10],
        }
    )

    result = calculate_metrics(df)

    assert math.isinf(result.loc[0, "calculated_stock_days"])


def test_after_ads_profit_fields_are_not_created():
    df = pd.DataFrame(
        {
            "order_gross_profit": [100, None],
            "ad_spend": [30, 20],
            "sales_7d_amount": [200, 200],
            "order_gross_margin": [0.4, 0.4],
            "sales_7d_units": [7, 7],
            "sales_14d_units": [14, 14],
            "predicted_daily_sales": [1, 1],
            "total_supply_qty": [30, 30],
        }
    )

    result = calculate_metrics(df)

    assert "ad_profit_after_ads" not in result.columns
    assert "profit_after_ads_margin" not in result.columns
    assert result.loc[0, "order_gross_profit"] == 100


def test_percentage_fields_are_normalized():
    config = {
        "numeric_fields": ["order_gross_margin", "acos"],
        "percentage_fields": ["order_gross_margin", "acos"],
        "zero_fill_fields": [],
    }
    df = pd.DataFrame(
        {
            "sku": ["A", "B", "C"],
            "order_gross_margin": ["30%", 30, 0.3],
            "acos": ["25%", 25, 0.25],
        }
    )

    result = clean_data(df, config)

    assert result["order_gross_margin"].tolist() == [0.3, 0.3, 0.3]
    assert result["acos"].tolist() == [0.25, 0.25, 0.25]
