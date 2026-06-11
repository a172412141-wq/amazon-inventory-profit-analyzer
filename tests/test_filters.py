import pandas as pd

from app import _apply_filters, _column_label, _display_columns, _filter_options_with_context


def test_filter_options_are_linked_across_all_dimensions():
    df = pd.DataFrame(
        {
            "parent_asin": ["P1", "P1", "P2", "P2"],
            "asin": ["A1", "A2", "A3", "A4"],
            "product_line": ["LineA", "LineB", "LineA", "LineC"],
            "spu": ["S1", "S2", "S3", "S4"],
        }
    )
    columns = ["parent_asin", "asin", "product_line", "spu"]

    options = _filter_options_with_context(df, columns, {"product_line": ["LineA"]})

    assert options["asin"] == ["A1", "A3"]
    assert options["parent_asin"] == ["P1", "P2"]
    assert options["spu"] == ["S1", "S3"]


def test_filter_options_ignore_current_dimension_but_respect_other_filters():
    df = pd.DataFrame(
        {
            "parent_asin": ["P1", "P1", "P2", "P2"],
            "asin": ["A1", "A2", "A3", "A4"],
            "product_line": ["LineA", "LineB", "LineA", "LineC"],
        }
    )
    columns = ["parent_asin", "asin", "product_line"]

    options = _filter_options_with_context(
        df,
        columns,
        {"parent_asin": ["P1"], "product_line": ["LineA"]},
    )

    assert options["asin"] == ["A1"]
    assert options["parent_asin"] == ["P1", "P2"]
    assert options["product_line"] == ["LineA", "LineB"]


def test_apply_filters_strips_source_values_before_matching():
    df = pd.DataFrame({"asin": [" A1 ", "A2"], "product_line": ["LineA", "LineB"]})

    filtered = _apply_filters(df, {"asin": ["A1"]})

    assert filtered["product_line"].tolist() == ["LineA"]


def test_sku_table_defaults_to_pinned_columns_only_and_in_order():
    df = pd.DataFrame(
        columns=[
            "asin",
            "sku",
            "order_gross_margin",
            "role_daily_sales",
            "order_gross_profit",
            "ad_spend",
            "available_stock_days",
            "stock_days",
            "available_stock_qty",
            "reason",
            "final_action",
        ]
    )

    assert _display_columns(df) == [
        "sku",
        "role_daily_sales",
        "order_gross_profit",
        "order_gross_margin",
        "ad_spend",
        "available_stock_days",
        "stock_days",
        "available_stock_qty",
        "reason",
    ]


def test_selected_extra_columns_are_appended_after_pinned_columns():
    df = pd.DataFrame(columns=["sku", "role_daily_sales", "final_action", "priority"])

    assert _display_columns(df, ["priority", "final_action"]) == [
        "sku",
        "role_daily_sales",
        "priority",
        "final_action",
    ]


def test_non_sku_tables_can_show_all_columns():
    df = pd.DataFrame(columns=["parent_asin", "order_gross_profit", "order_gross_margin"])

    assert _display_columns(df, use_pinned_defaults=False) == [
        "parent_asin",
        "order_gross_profit",
        "order_gross_margin",
    ]


def test_column_headers_have_chinese_labels():
    assert _column_label("role_daily_sales") == "角色判断日均销量"
    assert _column_label("order_gross_margin") == "订单毛利率"
    assert _column_label("unknown_field") == "unknown_field"
