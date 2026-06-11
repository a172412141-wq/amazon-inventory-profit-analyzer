import pandas as pd

from app import _apply_filters, _filter_options_with_context


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
