import pandas as pd

from app import FILTER_COLUMNS, _apply_filters, _column_label, _display_columns, _filter_options_with_context
from modules.loader import apply_column_mapping, load_yaml
from modules.pipeline import prepare_full_sku_table


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


def test_category_level_3_filter_is_linked_with_other_dimensions():
    df = pd.DataFrame(
        {
            "parent_asin": ["P1", "P1", "P2"],
            "product_line": ["LineA", "LineA", "LineB"],
            "category_level_3": ["Cat1", "Cat2", "Cat1"],
        }
    )
    columns = ["parent_asin", "product_line", "category_level_3"]

    category_options = _filter_options_with_context(df, columns, {"product_line": ["LineA"]})
    line_options = _filter_options_with_context(df, columns, {"category_level_3": ["Cat1"]})

    assert "category_level_3" in FILTER_COLUMNS
    assert category_options["category_level_3"] == ["Cat1", "Cat2"]
    assert line_options["product_line"] == ["LineA", "LineB"]


def test_category_level_3_is_mapped_and_kept_in_full_sku_output():
    mapping_config = load_yaml("config/column_mapping.yaml")
    mapped, mapping_report = apply_column_mapping(pd.DataFrame({"SKU": ["A"], "三级类目": ["家居收纳"]}), mapping_config)

    full_sku = prepare_full_sku_table(mapped)

    assert mapping_report["matched_columns"]["category_level_3"] == "三级类目"
    assert full_sku.loc[0, "category_level_3"] == "家居收纳"


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
    assert _column_label("category_level_3") == "三级分类"
    assert _column_label("unknown_field") == "unknown_field"
