"""
Pydantic schemas for Catalogue and Schemes.
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class SchemeRead(BaseModel):
    """Scheme data embedded in product responses."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scheme_type: str
    min_qty: int
    free_qty: Optional[int] = None
    discount_pct: Optional[Decimal] = None
    valid_from: date
    valid_to: date
    is_active: bool
    description: str


class ProductRead(BaseModel):
    """Product summary and detail response with derived case pricing and active scheme."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    name: str
    description: Optional[str] = None
    pack_size: Optional[str] = None
    case_qty: int
    dealer_price_per_pack: Decimal = Field(..., description="Per-pack price (demo assumption)")
    price_unit: str = "per_pack"
    dealer_price_per_case: Decimal = Field(..., description="Derived: dealer_price_per_pack * case_qty")
    gst_rate_pct: Optional[Decimal] = None
    stock_cases: int
    stock_status: str = Field(..., description="'in_stock', 'low_stock', or 'out_of_stock'")
    category: Optional[str] = None
    is_active: bool
    active_scheme: Optional[SchemeRead] = None
    created_at: datetime
    updated_at: datetime


class ProductListResponse(BaseModel):
    """Paginated product list response."""
    model_config = ConfigDict(from_attributes=True)

    items: List[ProductRead]
    total: int
    page: int
    page_size: int
    total_pages: int

