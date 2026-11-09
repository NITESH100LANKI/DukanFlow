"""
Unit tests for the Scheme Engine (backend/app/services/scheme_engine.py).

Verifies all 13 core calculation rules:
1. No scheme.
2. Buy 10 Get 1 below threshold.
3. Buy 10 Get 1 exact threshold.
4. Multiple qualifying sets.
5. 25 cases of biscuit.
6. Percentage discount below threshold.
7. Percentage discount at threshold.
8. Decimal rounding (ROUND_HALF_UP).
9. Expired scheme.
10. Future scheme.
11. Inactive scheme.
12. Invalid scheme configuration.
13. Physical free-goods stock validation.
"""

from datetime import date, timedelta
from decimal import Decimal
import pytest

from app.services.scheme_engine import calculate_line_scheme, SchemeResult


class MockScheme:
    def __init__(
        self,
        scheme_type: str,
        min_qty: int,
        free_qty: int | None = None,
        discount_pct: Decimal | None = None,
        valid_from: date | None = None,
        valid_to: date | None = None,
        is_active: bool = True,
    ):
        self.scheme_type = scheme_type
        self.min_qty = min_qty
        self.free_qty = free_qty
        self.discount_pct = discount_pct
        today = date.today()
        self.valid_from = valid_from or (today - timedelta(days=10))
        self.valid_to = valid_to or (today + timedelta(days=10))
        self.is_active = is_active


# 1. No scheme
def test_no_scheme():
    case_price = Decimal("777.60")
    res = calculate_line_scheme(case_price=case_price, paid_qty=3, scheme=None)
    assert res.paid_qty_cases == 3
    assert res.free_qty_cases == 0
    assert res.fulfilment_qty_cases == 3
    assert res.gross_amount == Decimal("2332.80")
    assert res.discount_amount == Decimal("0.00")
    assert res.benefit_value == Decimal("0.00")
    assert res.net_payable == Decimal("2332.80")
    assert not res.scheme_applied


# 2. Buy 10 Get 1 below threshold (9 cases)
def test_buy_n_get_m_below_threshold():
    case_price = Decimal("777.60")
    scheme = MockScheme(scheme_type="BUY_N_GET_M_FREE", min_qty=10, free_qty=1)
    res = calculate_line_scheme(case_price=case_price, paid_qty=9, scheme=scheme)
    assert res.paid_qty_cases == 9
    assert res.free_qty_cases == 0
    assert res.fulfilment_qty_cases == 9
    assert res.gross_amount == Decimal("6998.40")
    assert res.discount_amount == Decimal("0.00")
    assert res.benefit_value == Decimal("0.00")
    assert res.net_payable == Decimal("6998.40")
    assert not res.scheme_applied


# 3. Buy 10 Get 1 exact threshold (10 cases)
def test_buy_n_get_m_exact_threshold():
    case_price = Decimal("777.60")
    scheme = MockScheme(scheme_type="BUY_N_GET_M_FREE", min_qty=10, free_qty=1)
    res = calculate_line_scheme(case_price=case_price, paid_qty=10, scheme=scheme)
    assert res.paid_qty_cases == 10
    assert res.free_qty_cases == 1
    assert res.fulfilment_qty_cases == 11
    assert res.gross_amount == Decimal("7776.00")
    assert res.discount_amount == Decimal("0.00")  # Not deducted!
    assert res.benefit_value == Decimal("777.60")  # Informational value of free goods
    assert res.net_payable == Decimal("7776.00")
    assert res.scheme_applied


# 4. Multiple qualifying sets (20 cases -> 2 free)
def test_buy_n_get_m_multiple_sets():
    case_price = Decimal("777.60")
    scheme = MockScheme(scheme_type="BUY_N_GET_M_FREE", min_qty=10, free_qty=1)
    res = calculate_line_scheme(case_price=case_price, paid_qty=20, scheme=scheme)
    assert res.paid_qty_cases == 20
    assert res.free_qty_cases == 2
    assert res.fulfilment_qty_cases == 22
    assert res.gross_amount == Decimal("15552.00")
    assert res.discount_amount == Decimal("0.00")
    assert res.benefit_value == Decimal("1555.20")
    assert res.net_payable == Decimal("15552.00")
    assert res.scheme_applied


# 5. 25 cases of biscuit (2 free, 27 fulfilment, payable on 25)
def test_buy_n_get_m_partial_extra():
    case_price = Decimal("777.60")
    scheme = MockScheme(scheme_type="BUY_N_GET_M_FREE", min_qty=10, free_qty=1)
    res = calculate_line_scheme(case_price=case_price, paid_qty=25, scheme=scheme)
    assert res.paid_qty_cases == 25
    assert res.free_qty_cases == 2
    assert res.fulfilment_qty_cases == 27
    assert res.gross_amount == Decimal("19440.00")
    assert res.discount_amount == Decimal("0.00")
    assert res.benefit_value == Decimal("1555.20")
    assert res.net_payable == Decimal("19440.00")
    assert res.scheme_applied


# 6. Percentage discount below threshold (4 cases -> 0 discount)
def test_percentage_discount_below_threshold():
    case_price = Decimal("2030.00")
    scheme = MockScheme(scheme_type="DISCOUNT_ON_MIN_QTY", min_qty=5, discount_pct=Decimal("3.00"))
    res = calculate_line_scheme(case_price=case_price, paid_qty=4, scheme=scheme)
    assert res.paid_qty_cases == 4
    assert res.free_qty_cases == 0
    assert res.fulfilment_qty_cases == 4
    assert res.gross_amount == Decimal("8120.00")
    assert res.discount_amount == Decimal("0.00")
    assert res.benefit_value == Decimal("0.00")
    assert res.net_payable == Decimal("8120.00")
    assert not res.scheme_applied


# 7. Percentage discount at threshold (5 cases × 2030 = 10150, 3% = 304.50, net = 9845.50)
def test_percentage_discount_at_threshold():
    case_price = Decimal("2030.00")
    scheme = MockScheme(scheme_type="DISCOUNT_ON_MIN_QTY", min_qty=5, discount_pct=Decimal("3.00"))
    res = calculate_line_scheme(case_price=case_price, paid_qty=5, scheme=scheme)
    assert res.paid_qty_cases == 5
    assert res.free_qty_cases == 0
    assert res.fulfilment_qty_cases == 5
    assert res.gross_amount == Decimal("10150.00")
    assert res.discount_amount == Decimal("304.50")
    assert res.benefit_value == Decimal("304.50")
    assert res.net_payable == Decimal("9845.50")
    assert res.scheme_applied


# 8. Decimal rounding (ROUND_HALF_UP)
def test_decimal_rounding_half_up():
    case_price = Decimal("123.45")
    # 7 cases × 123.45 = 864.15; 3.33% = 28.776195 -> 28.78
    scheme = MockScheme(scheme_type="DISCOUNT_ON_MIN_QTY", min_qty=1, discount_pct=Decimal("3.33"))
    res = calculate_line_scheme(case_price=case_price, paid_qty=7, scheme=scheme)
    assert res.gross_amount == Decimal("864.15")
    assert res.discount_amount == Decimal("28.78")
    assert res.net_payable == Decimal("835.37")


# 9. Expired scheme
def test_expired_scheme():
    case_price = Decimal("777.60")
    today = date.today()
    scheme = MockScheme(
        scheme_type="BUY_N_GET_M_FREE",
        min_qty=5,
        free_qty=1,
        valid_from=today - timedelta(days=30),
        valid_to=today - timedelta(days=1),
    )
    res = calculate_line_scheme(case_price=case_price, paid_qty=10, scheme=scheme)
    assert res.free_qty_cases == 0
    assert not res.scheme_applied
    assert "expired" in res.scheme_description.lower()


# 10. Future scheme
def test_future_scheme():
    case_price = Decimal("777.60")
    today = date.today()
    scheme = MockScheme(
        scheme_type="BUY_N_GET_M_FREE",
        min_qty=5,
        free_qty=1,
        valid_from=today + timedelta(days=5),
        valid_to=today + timedelta(days=30),
    )
    res = calculate_line_scheme(case_price=case_price, paid_qty=10, scheme=scheme)
    assert res.free_qty_cases == 0
    assert not res.scheme_applied
    assert "not yet active" in res.scheme_description.lower()


# 11. Inactive scheme
def test_inactive_scheme():
    case_price = Decimal("777.60")
    scheme = MockScheme(
        scheme_type="BUY_N_GET_M_FREE",
        min_qty=5,
        free_qty=1,
        is_active=False,
    )
    res = calculate_line_scheme(case_price=case_price, paid_qty=10, scheme=scheme)
    assert res.free_qty_cases == 0
    assert not res.scheme_applied
    assert "inactive" in res.scheme_description.lower()


# 12. Invalid scheme configuration (zero or negative params)
def test_invalid_scheme_configuration():
    case_price = Decimal("777.60")
    scheme = MockScheme(
        scheme_type="BUY_N_GET_M_FREE",
        min_qty=0,  # Invalid min_qty
        free_qty=1,
    )
    res = calculate_line_scheme(case_price=case_price, paid_qty=10, scheme=scheme)
    assert res.free_qty_cases == 0
    assert not res.scheme_applied

    with pytest.raises(ValueError):
        calculate_line_scheme(case_price=case_price, paid_qty=0, scheme=scheme)


# 13. Physical free-goods stock validation check
def test_physical_free_goods_stock_validation():
    case_price = Decimal("777.60")
    scheme = MockScheme(scheme_type="BUY_N_GET_M_FREE", min_qty=10, free_qty=1)
    res = calculate_line_scheme(case_price=case_price, paid_qty=10, scheme=scheme)

    # 10 paid cases requires 11 cases in inventory
    available_stock_cases = 10
    has_sufficient_stock = available_stock_cases >= res.fulfilment_qty_cases
    assert not has_sufficient_stock, "Must require 11 cases in stock, but only 10 available"

    available_stock_cases = 11
    has_sufficient_stock = available_stock_cases >= res.fulfilment_qty_cases
    assert has_sufficient_stock, "11 cases available is sufficient for 11 fulfilment cases"
