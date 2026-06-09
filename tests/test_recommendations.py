import pandas as pd

from modules.recommendations import recommend_action


def make_row(**overrides):
    base = {
        "stock_days": 60,
        "main_daily_sales": 2,
        "total_supply_qty": 120,
        "recommended_replenishment_qty": 0,
        "order_gross_profit": 100,
        "order_gross_margin": 0.2,
        "ad_spend": 0,
        "ad_sales": 0,
        "acos": 0.1,
        "aged_inventory_181_plus": 0,
        "inbound_qty": 0,
        "recent_sales_trend": "销量稳定",
    }
    base.update(overrides)
    return pd.Series(base)


def test_clearance_when_stock_days_above_270():
    decision = recommend_action(make_row(stock_days=300, order_gross_margin=0.4))

    assert decision["final_action"] == "清货处理"


def test_negative_gross_profit_with_replenishment_pauses_replenishment():
    decision = recommend_action(
        make_row(
            stock_days=60,
            recommended_replenishment_qty=10,
            order_gross_profit=-10,
            order_gross_margin=0.2,
            acos=0,
        )
    )

    assert decision["final_action"] == "暂缓补货"


def test_high_margin_60_to_120_days_accelerates_turnover():
    decision = recommend_action(make_row(stock_days=90, order_gross_profit=100, order_gross_margin=0.4))

    assert decision["final_action"] == "加大投入加速周转"


def test_high_margin_120_to_180_days_controls_replenishment():
    decision = recommend_action(make_row(stock_days=150, order_gross_profit=100, order_gross_margin=0.4))

    assert decision["final_action"] == "控补货促周转"


def test_high_margin_above_180_days_stops_replenishment():
    decision = recommend_action(make_row(stock_days=200, order_gross_profit=100, order_gross_margin=0.4))

    assert decision["final_action"] == "高毛利停补"


def test_stock_days_below_14_positive_margin_replenishes_immediately():
    decision = recommend_action(
        make_row(
            stock_days=10,
            recommended_replenishment_qty=20,
            order_gross_profit=100,
            order_gross_margin=0.2,
        )
    )

    assert decision["final_action"] == "立即补货"


def test_acos_over_margin_controls_ads():
    decision = recommend_action(make_row(stock_days=60, order_gross_margin=0.2, acos=0.25))

    assert decision["final_action"] == "控广告"


def test_healthy_inventory_and_ads_can_add_ads():
    decision = recommend_action(
        make_row(
            stock_days=60,
            order_gross_profit=100,
            order_gross_margin=0.2,
            acos=0.1,
            recommended_replenishment_qty=0,
            recent_sales_trend="销量稳定",
        )
    )

    assert decision["final_action"] == "可加广告"
