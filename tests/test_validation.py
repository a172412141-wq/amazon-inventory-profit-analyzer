import pandas as pd

from modules.validation import validate_data


def test_validation_reports_inventory_and_margin_mismatches():
    df = pd.DataFrame(
        {
            "sku": ["A"],
            "total_supply_qty": [100],
            "available_qty": [80],
            "inbound_qty": [50],
            "stock_days": [100],
            "main_daily_sales": [2],
            "calculated_stock_days": [50],
            "available_stock_days": [40],
            "order_gross_profit": [10],
            "order_gross_margin": [0.2],
            "sales_7d_amount": [100],
            "ad_spend": [0],
            "ad_sales": [0],
            "acos": [0],
            "recommended_replenishment_qty": [0],
        }
    )
    mapping_report = {"missing_fields": [], "matched_columns": {}}

    errors = validate_data(df, mapping_report, {})

    assert "库存信息不匹配" in errors["error_type"].tolist()
    assert "库存天数口径不一致" in errors["error_type"].tolist()
    assert "毛利率不匹配" in errors["error_type"].tolist()
