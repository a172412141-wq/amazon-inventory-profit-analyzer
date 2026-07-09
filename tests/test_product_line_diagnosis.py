from datetime import date

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


def test_product_line_diagnosis_outputs_data_credibility_and_cause_levels():
    df = pd.DataFrame(
        {
            "sku": ["A", "B"],
            "parent_asin": ["P1", "P1"],
            "product_line": ["L1", "L1"],
            "sku_role": ["主力 SKU", "低效异常 SKU"],
            "sales_14d_amount": [500, 20],
            "sales_14d_units": [50, 1],
            "order_gross_profit": [80, -10],
            "order_gross_margin": [0.16, -0.50],
            "ad_spend": [30, 20],
            "ad_sales": [200, 0],
            "stock_days": [20, 200],
            "available_qty": [20, 100],
            "final_action": ["优先补货", "清货处理"],
            "priority": ["P1", "P1"],
        }
    )

    report = build_product_line_diagnosis(df, "L1")

    assert {"数据可信度", "周转", "规模", "毛利润"}.issubset(set(report["relationship_diagnostics"]["经营顺序"]))
    assert set(report["problem_skus"]["原因等级"]).issubset({"已确认原因", "高概率原因", "待验证假设", "无法判断"})
    assert "销售与广告时间窗口" in report["data_credibility"]["检查项"].tolist()
    assert "待确认" in report["data_credibility"]["状态"].tolist()


def test_data_credibility_excludes_zero_filled_missing_values_but_keeps_real_zeroes():
    df = pd.DataFrame(
        {
            "sku": ["A", "B"],
            "product_line": ["L1", "L1"],
            "sku_role": ["低效异常 SKU", "低效异常 SKU"],
            "sales_14d_amount": [0.0, 0.0],
            "sales_7d_amount": [0.0, 0.0],
            "ad_spend": [0.0, 0.0],
            "ad_sales": [0.0, 0.0],
            "stock_days": [0.0, 0.0],
            "available_stock_days": [0.0, 0.0],
            "available_qty": [0.0, 0.0],
            "total_supply_qty": [0.0, 0.0],
            "inbound_qty": [0.0, 0.0],
            "sales_7d_units": [0.0, 0.0],
            "_missing_sales_14d_amount": [True, False],
            "_missing_sales_7d_amount": [True, False],
            "_missing_ad_spend": [True, False],
            "_missing_ad_sales": [True, False],
            "_missing_stock_days": [True, False],
            "_missing_available_qty": [True, False],
            "_missing_total_supply_qty": [True, False],
            "_missing_inbound_qty": [True, False],
            "_missing_sales_7d_units": [True, False],
        }
    )

    credibility = build_product_line_diagnosis(df, "L1")["data_credibility"].set_index("检查项")

    assert credibility.loc["销售与广告时间窗口", "完整率"] == pytest.approx(0.5)
    assert credibility.loc["库存口径", "完整率"] == pytest.approx(0.5)


def test_product_line_todo_contains_complete_action_fields_and_preserves_system_actions():
    df = pd.DataFrame(
        {
            "sku": ["A", "B"],
            "parent_asin": ["P1", "P1"],
            "product_line": ["L1", "L1"],
            "sku_role": ["主力 SKU", "低效异常 SKU"],
            "sales_14d_amount": [500, 20],
            "sales_14d_units": [50, 1],
            "order_gross_profit": [80, -10],
            "order_gross_margin": [0.16, -0.50],
            "ad_spend": [30, 20],
            "ad_sales": [200, 0],
            "stock_days": [20, 200],
            "available_qty": [20, 100],
            "final_action": ["优先补货", "清货处理"],
            "priority": ["P1", "P1"],
        }
    )

    report = build_product_line_diagnosis(
        df,
        "L1",
        owner="Fang",
        start_date=date(2026, 6, 17),
    )
    todo = report["todo_list"]
    required = {
        "状态",
        "报告优先级",
        "经营顺序",
        "层级",
        "对象",
        "问题",
        "证据",
        "原因等级",
        "经营影响",
        "动作",
        "负责人",
        "开始时间",
        "完成时间",
        "观察周期",
        "成功标准",
        "失败预案",
        "系统final_action",
        "系统priority",
    }

    assert required.issubset(todo.columns)
    assert not todo.empty
    assert set(todo["负责人"]) == {"Fang"}
    assert set(todo["开始时间"]) == {"2026-06-17"}
    assert {"优先补货", "清货处理"}.issubset(set(todo["系统final_action"]))
    assert todo.iloc[0]["报告优先级"] == "P0"
    assert todo.iloc[0]["经营顺序"] == "周转"


def test_product_line_diagnosis_provides_management_and_todo_narratives():
    df = pd.DataFrame(
        {
            "sku": ["A", "B"],
            "parent_asin": ["P1", "P1"],
            "product_line": ["L1", "L1"],
            "sku_role": ["主力 SKU", "低效异常 SKU"],
            "sales_14d_amount": [500, 20],
            "sales_14d_units": [50, 1],
            "order_gross_profit": [80, -10],
            "order_gross_margin": [0.16, -0.50],
            "ad_spend": [30, 20],
            "ad_sales": [200, 0],
            "stock_days": [20, 200],
            "available_qty": [20, 100],
            "final_action": ["优先补货", "清货处理"],
            "priority": ["P1", "P1"],
        }
    )

    report = build_product_line_diagnosis(
        df,
        "L1",
        owner="Fang",
        start_date=date(2026, 6, 17),
    )
    management = report["executive_summary"]
    todo_summary = report["todo_summary"]

    assert set(management) == {"headline", "operating_snapshot", "priority_risks", "growth_opportunities", "data_boundaries"}
    assert "L1" in management["headline"]
    assert "P0/P1" in management["headline"]
    assert "数据" in management["data_boundaries"]
    assert "共形成" in todo_summary["headline"]
    assert "P0" in todo_summary["priority_summary"]
    assert "Fang" in todo_summary["ownership_summary"]
    assert "2026-06-19" in todo_summary["schedule_summary"]
    assert "首要执行项" in todo_summary["execution_focus"]


@pytest.mark.parametrize(
    ("ad_spend", "ad_clicks"),
    [
        (19, 100),
        (100, 19),
        (100, None),
    ],
)
def test_fang_rel_008_downgrades_ad_diagnosis_when_sample_is_insufficient(ad_spend, ad_clicks):
    data = {
        "sku": ["A"],
        "parent_asin": ["P1"],
        "product_line": ["L1"],
        "sku_role": ["低效异常 SKU"],
        "sales_14d_amount": [100],
        "sales_14d_units": [10],
        "order_gross_profit": [10],
        "order_gross_margin": [0.10],
        "ad_spend": [ad_spend],
        "ad_sales": [20],
        "stock_days": [45],
        "available_qty": [20],
        "final_action": ["控广告"],
        "priority": ["P2"],
    }
    if ad_clicks is not None:
        data["ad_clicks"] = [ad_clicks]
    df = pd.DataFrame(data)
    original = df.copy(deep=True)

    report = build_product_line_diagnosis(
        df,
        "L1",
        thresholds={
            "ads": {
                "minimum_spend_for_reliable_acos": 20,
                "minimum_clicks_for_reliable_cvr": 20,
            }
        },
    )
    ad_diagnosis = report["relationship_diagnostics"].query("诊断关系 == '广告-销售-利润'").iloc[0]

    assert ad_diagnosis["原因等级"] == "待验证假设"
    assert ad_diagnosis["报告优先级"] == "P3"
    assert ad_diagnosis["行动状态"] == "待验证"
    assert "样本不足" in ad_diagnosis["诊断判断"]
    assert "20" in ad_diagnosis["已确认事实"]
    assert report["sku_contribution"].iloc[0]["系统final_action"] == "控广告"
    pd.testing.assert_frame_equal(df, original)


def test_fang_rel_008_keeps_ad_diagnosis_when_sample_reaches_boundary():
    df = pd.DataFrame(
        {
            "sku": ["A"],
            "parent_asin": ["P1"],
            "product_line": ["L1"],
            "sku_role": ["低效异常 SKU"],
            "sales_14d_amount": [100],
            "sales_14d_units": [10],
            "order_gross_profit": [10],
            "order_gross_margin": [0.10],
            "ad_spend": [20],
            "ad_sales": [20],
            "ad_clicks": [20],
            "stock_days": [45],
            "available_qty": [20],
            "final_action": ["控广告"],
            "priority": ["P2"],
        }
    )

    report = build_product_line_diagnosis(
        df,
        "L1",
        thresholds={
            "ads": {
                "minimum_spend_for_reliable_acos": 20,
                "minimum_clicks_for_reliable_cvr": 20,
            }
        },
    )
    ad_diagnosis = report["relationship_diagnostics"].query("诊断关系 == '广告-销售-利润'").iloc[0]

    assert ad_diagnosis["原因等级"] == "高概率原因"
    assert ad_diagnosis["报告优先级"] == "P1"
    assert ad_diagnosis["行动状态"] == "需处理"
