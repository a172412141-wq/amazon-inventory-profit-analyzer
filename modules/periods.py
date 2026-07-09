from __future__ import annotations

from typing import Literal


SalesPeriod = Literal["7d", "14d"]
DEFAULT_SALES_PERIOD: SalesPeriod = "7d"
SALES_PERIOD_OPTIONS: tuple[SalesPeriod, ...] = ("7d", "14d")
SALES_PERIOD_CONFIG: dict[SalesPeriod, dict[str, str | int]] = {
    "7d": {
        "label": "7天",
        "days": 7,
        "units_column": "sales_7d_units",
        "amount_column": "sales_7d_amount",
    },
    "14d": {
        "label": "14天",
        "days": 14,
        "units_column": "sales_14d_units",
        "amount_column": "sales_14d_amount",
    },
}


def normalize_sales_period(period: str | None) -> SalesPeriod:
    return "14d" if str(period).strip().lower() == "14d" else DEFAULT_SALES_PERIOD


def sales_period_label(period: str | None) -> str:
    return str(SALES_PERIOD_CONFIG[normalize_sales_period(period)]["label"])


def sales_period_days(period: str | None) -> int:
    return int(SALES_PERIOD_CONFIG[normalize_sales_period(period)]["days"])


def sales_period_units_column(period: str | None) -> str:
    return str(SALES_PERIOD_CONFIG[normalize_sales_period(period)]["units_column"])


def sales_period_amount_column(period: str | None) -> str:
    return str(SALES_PERIOD_CONFIG[normalize_sales_period(period)]["amount_column"])
