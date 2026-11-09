"""
Pydantic schemas for Shopping Cart and Cart Lines.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class AddCartLineRequest(BaseModel):
    """Payload to add or replace a product line in the cart."""
    product_id: uuid.UUID
    qty_cases: int = Field(..., ge=1, description="Number of wholesale cases (must be >= 1)")


class UpdateCartLineRequest(BaseModel):
    """Payload to update quantity for an existing cart line."""
    qty_cases: int = Field(..., ge=1, description="Updated number of wholesale cases (must be >= 1)")


class CartLineSchemeInfo(BaseModel):
    """Scheme benefit details applied to a specific cart line."""
    model_config = ConfigDict(from_attributes=True)

    scheme_type: str
    free_qty: int
    discount_amount: Decimal
    benefit_value: Decimal
    description: str


class CartLineRead(BaseModel):
    """Computed cart line details including scheme calculations."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    sku: str
    name: str
    pack_size: Optional[str] = None
    case_qty: int
    price_per_pack: Decimal
    price_per_case: Decimal
    qty_cases: int  # Paid cases
    qty_free: int  # Free bonus cases
    qty_fulfilment: int  # Total physical cases = paid + free
    gross_line_total: Decimal
    discount_amount: Decimal
    benefit_value: Decimal
    net_line_total: Decimal
    scheme_applied: Optional[CartLineSchemeInfo] = None
    created_at: datetime
    updated_at: datetime


class CartSummary(BaseModel):
    """Aggregated cart totals."""
    total_cases_paid: int
    total_cases_free: int
    total_cases_fulfilment: int
    gross_total: Decimal
    total_discount: Decimal
    total_benefit_value: Decimal
    net_total: Decimal
    item_count: int


class CartRead(BaseModel):
    """Full cart response including line details and computed summary."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    retailer_id: uuid.UUID
    lines: List[CartLineRead]
    summary: CartSummary
    created_at: datetime
    updated_at: datetime
