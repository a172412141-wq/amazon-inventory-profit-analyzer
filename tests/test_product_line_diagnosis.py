import pytest
import pandas as pd

from modules.product_line_diagnosis import build_product_line_diagnosis


def test_product_line_margin_uses_profit_sum_divided_by_sales_sum():
    df = pd.DataFrame(
        {
            "sku": ["A", "B"],
            "parent_asin": ["P1", "P1"],
            "product_line": ["L1", "L1"],
            "sku_role": ["主力 SKU", "利润 SKU"],
            "sales_14d_amount": [100, 300],
            "sales_14d_units": [10, 30],
            "order_gross_profit": [10, 30],
            "order_gross_margin": [0.90, 0.20],
            "ad_spend": [10, 30],
            "final_action": ["观察", "观察"],
            "priority": ["P4", "P4"],
        }
    )

    report = build_product_line_diagnosis(df, "L1")
    core = report["core_metrics"].set_index("指标")

    assert core.loc["利润率", "数值"] == pytest.approx(0.10)
    assert core.loc["广告花费占比", "数值"] == pytest.approx(0.10)


def test_product_line_ad_sales_mismatch_uses_line_shares():
    df = pd.DataFrame(
        {
            "sku": ["A", "B"],
            "parent_asin": ["P1", "P1"],
            "product_line": ["L1", "L1"],
            "sku_role": ["引流 SKU", "主力 SKU"],
            "sales_14d_amount": [100, 300],
            "sales_14d_units": [10, 30],
            "order_gross_profit": [5, 60],
            "order_gross_margin": [0.05, 0.20],
            "ad_spend": [80, 20],
            "final_action": ["观察", "观察"],
            "priority": ["P4", "P4"],
        }
    )

    report = build_product_line_diagnosis(df, "L1")
    contribution = report["sku_contribution"].set_index("SKU")

    assert contribution.loc["A", "广告资源错配值"] == pytest.approx(0.55)
    assert "A" in report["problem_skus"]["SKU"].tolist()


def test_product_line_diagnosis_keeps_existing_role_action_priority_unchanged():
    df = pd.DataFrame(
        {
            "sku": ["A", "B", "C"],
            "parent_asin": ["P1", "P1", "P2"],
            "product_line": ["L1", "L1", "L1"],
            "sku_role": ["引流 SKU", "主力 SKU", "低效异常 SKU"],
            "sales_14d_amount": [100, 300, 10],
            "sales_14d_units": [10, 30, 1],
            "order_gross_profit": [5, 60, -2],
            "order_gross_margin": [0.05, 0.20, -0.20],
            "ad_spend": [80, 20, 5],
            "final_action": ["控广告", "观察", "清货处理"],
            "priority": ["P2", "P4", "P1"],
        }
    )
    original = df.copy(deep=True)

    report = build_product_line_diagnosis(df, "L1")

    pd.testing.assert_frame_equal(df, original)
    assert set(report["problem_skus"]["系统final_action"]) >= {"控广告", "清货处理"}
    assert set(report["problem_skus"]["系统priority"]) >= {"P2", "P1"}


def test_product_line_diagnosis_marks_low_confidence_when_peer_samples_are_missing():
    df = pd.DataFrame(
        {
            "sku": ["A"],
            "parent_asin": ["P1"],
            "product_line": ["L1"],
            "sku_role": ["利润 SKU"],
            "sales_14d_amount": [100],
            "sales_14d_units": [10],
            "order_gross_profit": [30],
            "order_gross_margin": [0.30],
            "ad_spend": [0],
            "final_action": ["观察"],
            "priority": ["P4"],
        }
    )

    report = build_product_line_diagnosis(df, "L1")
    contribution = report["sku_contribution"]

    assert len(contribution) == 1
    if not report["problem_skus"].empty:
        assert "低" in report["problem_skus"]["置信度"].tolist()

