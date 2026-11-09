"""
Pure Python Scheme Engine for DukaanFlow.

Implements promotional scheme calculations with zero floating-point arithmetic:
- Uses decimal.Decimal throughout with ROUND_HALF_UP.
- Supports BUY_N_GET_M_FREE (free goods physically fulfilled, not deducted from payable).
- Supports DISCOUNT_ON_MIN_QTY (percentage discount deducted from payable).
- Validates active status and validity date ranges.
- Fully unit-testable in isolation.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Any


TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class SchemeResult:
    """Calculated outcome of applying a promotional scheme to an order line."""
    paid_qty_cases: int
    free_qty_cases: int
    fulfilment_qty_cases: int
    gross_amount: Decimal
    discount_amount: Decimal
    benefit_value: Decimal
    net_payable: Decimal
    scheme_applied: bool
    scheme_description: str


def calculate_line_scheme(
    case_price: Decimal,
    paid_qty: int,
    scheme: Optional[Any] = None,
    order_date: Optional[date] = None,
) -> SchemeResult:
    """
    Calculates line pricing, scheme applicability, free goods and net payable.

    Parameters:
    - case_price: Wholesale price per full case (Decimal).
    - paid_qty: Number of cases the retailer is purchasing (int >= 1).
    - scheme: Scheme ORM model or object with attributes:
              (scheme_type, min_qty, free_qty, discount_pct, valid_from, valid_to, is_active).
    - order_date: Date to evaluate scheme validity against (defaults to date.today()).
    """
    if paid_qty < 1:
        raise ValueError(f"Quantity must be at least 1 case, got {paid_qty}")

    check_date = order_date or date.today()
    gross_amount = (case_price * paid_qty).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    # Base case: No scheme or inactive / invalid / outside date range
    if not scheme:
        return SchemeResult(
            paid_qty_cases=paid_qty,
            free_qty_cases=0,
            fulfilment_qty_cases=paid_qty,
            gross_amount=gross_amount,
            discount_amount=Decimal("0.00"),
            benefit_value=Decimal("0.00"),
            net_payable=gross_amount,
            scheme_applied=False,
            scheme_description="",
        )

    # Check active status
    is_active = getattr(scheme, "is_active", True)
    if not is_active:
        return SchemeResult(
            paid_qty_cases=paid_qty,
            free_qty_cases=0,
            fulfilment_qty_cases=paid_qty,
            gross_amount=gross_amount,
            discount_amount=Decimal("0.00"),
            benefit_value=Decimal("0.00"),
            net_payable=gross_amount,
            scheme_applied=False,
            scheme_description="Scheme inactive",
        )

    # Check date validity
    valid_from = getattr(scheme, "valid_from", None)
    valid_to = getattr(scheme, "valid_to", None)
    if valid_from and check_date < valid_from:
        return SchemeResult(
            paid_qty_cases=paid_qty,
            free_qty_cases=0,
            fulfilment_qty_cases=paid_qty,
            gross_amount=gross_amount,
            discount_amount=Decimal("0.00"),
            benefit_value=Decimal("0.00"),
            net_payable=gross_amount,
            scheme_applied=False,
            scheme_description="Scheme not yet active",
        )

    if valid_to and check_date > valid_to:
        return SchemeResult(
            paid_qty_cases=paid_qty,
            free_qty_cases=0,
            fulfilment_qty_cases=paid_qty,
            gross_amount=gross_amount,
            discount_amount=Decimal("0.00"),
            benefit_value=Decimal("0.00"),
            net_payable=gross_amount,
            scheme_applied=False,
            scheme_description="Scheme expired",
        )

    scheme_type = getattr(scheme, "scheme_type", "")
    raw_min_qty = getattr(scheme, "min_qty", 1)
    if raw_min_qty is None or raw_min_qty <= 0:
        return SchemeResult(
            paid_qty_cases=paid_qty,
            free_qty_cases=0,
            fulfilment_qty_cases=paid_qty,
            gross_amount=gross_amount,
            discount_amount=Decimal("0.00"),
            benefit_value=Decimal("0.00"),
            net_payable=gross_amount,
            scheme_applied=False,
            scheme_description="Invalid scheme configuration",
        )
    min_qty = raw_min_qty

    # Scheme 1: BUY_N_GET_M_FREE
    if scheme_type == "BUY_N_GET_M_FREE":
        free_per_set = getattr(scheme, "free_qty", None)
        if free_per_set is None or free_per_set <= 0:
            # Invalid configuration safeguard
            return SchemeResult(
                paid_qty_cases=paid_qty,
                free_qty_cases=0,
                fulfilment_qty_cases=paid_qty,
                gross_amount=gross_amount,
                discount_amount=Decimal("0.00"),
                benefit_value=Decimal("0.00"),
                net_payable=gross_amount,
                scheme_applied=False,
                scheme_description="Invalid scheme configuration",
            )

        sets_earned = paid_qty // min_qty
        free_qty = sets_earned * free_per_set
        fulfilment_qty = paid_qty + free_qty
        benefit_value = (case_price * free_qty).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        # IMPORTANT: Free goods value is informational; it is NOT deducted from retailer payable
        discount_amount = Decimal("0.00")
        net_payable = gross_amount
        scheme_applied = free_qty > 0

        desc = (
            f"Buy {min_qty} Get {free_per_set} Free (+{free_qty} case{'s' if free_qty > 1 else ''} free)"
            if scheme_applied
            else f"Buy {min_qty} Get {free_per_set} Free (min {min_qty} cases)"
        )

        return SchemeResult(
            paid_qty_cases=paid_qty,
            free_qty_cases=free_qty,
            fulfilment_qty_cases=fulfilment_qty,
            gross_amount=gross_amount,
            discount_amount=discount_amount,
            benefit_value=benefit_value,
            net_payable=net_payable,
            scheme_applied=scheme_applied,
            scheme_description=desc,
        )

    # Scheme 2: DISCOUNT_ON_MIN_QTY
    elif scheme_type == "DISCOUNT_ON_MIN_QTY":
        raw_pct = getattr(scheme, "discount_pct", None)
        if raw_pct is None or raw_pct <= 0:
            return SchemeResult(
                paid_qty_cases=paid_qty,
                free_qty_cases=0,
                fulfilment_qty_cases=paid_qty,
                gross_amount=gross_amount,
                discount_amount=Decimal("0.00"),
                benefit_value=Decimal("0.00"),
                net_payable=gross_amount,
                scheme_applied=False,
                scheme_description="Invalid discount percentage",
            )

        discount_pct = Decimal(str(raw_pct))
        if paid_qty >= min_qty:
            discount_amount = (gross_amount * discount_pct / Decimal("100")).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            net_payable = (gross_amount - discount_amount).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
            benefit_value = discount_amount
            scheme_applied = True
            desc = f"{discount_pct}% discount on {min_qty}+ cases (-₹{discount_amount})"
        else:
            discount_amount = Decimal("0.00")
            benefit_value = Decimal("0.00")
            net_payable = gross_amount
            scheme_applied = False
            desc = f"{discount_pct}% discount on {min_qty}+ cases (min {min_qty} cases)"

        return SchemeResult(
            paid_qty_cases=paid_qty,
            free_qty_cases=0,
            fulfilment_qty_cases=paid_qty,
            gross_amount=gross_amount,
            discount_amount=discount_amount,
            benefit_value=benefit_value,
            net_payable=net_payable,
            scheme_applied=scheme_applied,
            scheme_description=desc,
        )

    # Unknown scheme type fallback
    return SchemeResult(
        paid_qty_cases=paid_qty,
        free_qty_cases=0,
        fulfilment_qty_cases=paid_qty,
        gross_amount=gross_amount,
        discount_amount=Decimal("0.00"),
        benefit_value=Decimal("0.00"),
        net_payable=gross_amount,
        scheme_applied=False,
        scheme_description="Unknown scheme type",
    )
