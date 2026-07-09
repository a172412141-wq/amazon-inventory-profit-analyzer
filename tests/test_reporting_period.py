import pytest
import pandas as pd

from modules.aggregation import aggregate_dimension
from modules.pipeline import build_overview, prepare_full_sku_table
from modules.product_line_diagnosis import build_product_line_diagnosis


def _role_reports():
    return {
        "traffic_skus": pd.DataFrame(),
        "main_skus": pd.DataFrame(),
        "profit_skus": pd.DataFrame(),
        "low_efficiency_skus": pd.DataFrame(),
    }


def test_overview_acoas_uses_selected_period_sales_after_filtering():
    full = prepare_full_sku_table(
        pd.DataFrame(
            {
                "sku": ["A", "B"],
                "sales_7d_units": [7, 7],
                "sales_14d_units": [140, 140],
                "sales_7d_amount": [100, 100],
                "sales_14d_amount": [1000, 1000],
                "ad_spend": [10, 30],
                "order_gross_profit": [20, 40],
            }
        )
    )

    metrics_7d, _, _ = build_overview(full, _role_reports(), sales_period="7d")
    metrics_14d, _, _ = build_overview(full, _role_reports(), sales_period="14d")

    assert metrics_7d["当前周期"] == "7天"
    assert metrics_7d["当前周期销售额"] == 200
    assert metrics_7d["整体 ACOAS"] == pytest.approx(40 / 200)
    assert metrics_14d["当前周期销售额"] == 2000
    assert metrics_14d["整体 ACOAS"] == pytest.approx(40 / 2000)


def test_aggregate_dimension_uses_selected_period_for_acoas_and_margin():
    df = pd.DataFrame(
        {
            "product_line": ["L1", "L1"],
            "sku": ["A", "B"],
            "sales_7d_units": [7, 7],
            "sales_14d_units": [70, 70],
            "sales_7d_amount": [100, 100],
            "sales_14d_amount": [1000, 1000],
            "ad_spend": [10, 30],
            "order_gross_profit": [20, 40],
            "available_stock_qty": [20, 20],
        }
    )

    line_7d = aggregate_dimension(df, "product_line", sales_period="7d").iloc[0]
    line_14d = aggregate_dimension(df, "product_line", sales_period="14d").iloc[0]

    assert line_7d["selected_sales_amount"] == 200
    assert line_7d["acoas"] == pytest.approx(40 / 200)
    assert line_7d["order_gross_margin"] == pytest.approx(60 / 200)
    assert line_14d["selected_sales_amount"] == 2000
    assert line_14d["acoas"] == pytest.approx(40 / 2000)
    assert line_14d["order_gross_margin"] == pytest.approx(60 / 2000)


def test_product_line_diagnosis_core_metrics_follow_selected_period():
    df = pd.DataFrame(
        {
            "sku": ["A"],
            "parent_asin": ["P1"],
            "product_line": ["L1"],
            "sku_role": ["主力 SKU"],
            "sales_7d_amount": [100],
            "sales_14d_amount": [1000],
            "sales_7d_units": [7],
            "sales_14d_units": [70],
            "order_gross_profit": [20],
            "order_gross_margin": [0.2],
            "ad_spend": [10],
            "ad_sales": [50],
            "ad_clicks": [30],
            "final_action": ["观察"],
            "priority": ["P4"],
        }
    )

    report_7d = build_product_line_diagnosis(df, "L1", sales_period="7d")
    report_14d = build_product_line_diagnosis(df, "L1", sales_period="14d")
    core_7d = report_7d["core_metrics"].set_index("指标")
    core_14d = report_14d["core_metrics"].set_index("指标")

    assert core_7d.loc["销售额", "数值"] == 100
    assert core_7d.loc["广告花费占比", "数值"] == pytest.approx(0.10)
    assert "7天销售额" in core_7d.loc["销售额", "计算口径"]
    assert core_14d.loc["销售额", "数值"] == 1000
    assert core_14d.loc["广告花费占比", "数值"] == pytest.approx(0.01)
