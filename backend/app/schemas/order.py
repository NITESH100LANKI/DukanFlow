"""
Pydantic schemas for Order Placement and Management (Phase 6).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class OrderRetailerInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    mobile: str
    address: Optional[str] = None


class OrderLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    sku_snapshot: str
    name_snapshot: str
    pack_size_snapshot: str
    case_qty_snapshot: int
    price_per_pack_snapshot: Decimal
    price_per_case_snapshot: Decimal

    # Scheme snapshots
    scheme_type_snapshot: Optional[str] = None
    min_qty_snapshot: Optional[int] = None
    free_qty_snapshot: Optional[int] = None
    discount_pct_snapshot: Optional[Decimal] = None
    description_snapshot: Optional[str] = None

    # Quantities
    qty_cases: int
    free_cases: int
    fulfilment_qty_cases: int

    # Financials
    unit_price: Decimal
    gross_amount: Decimal
    discount_amount: Decimal
    net_amount: Decimal
    raw_fragment: Optional[str] = None


class OrderAuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    actor_type: str
    actor_id: uuid.UUID
    action: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    note: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    created_at: datetime


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_number: str
    retailer_id: uuid.UUID
    reviewed_by: Optional[uuid.UUID] = None
    order_source: str
    status: str

    gross_total: Decimal
    scheme_total: Decimal
    net_total: Decimal

    total_cases: int
    total_free_cases: int
    total_fulfilment_cases: int

    remarks: Optional[str] = None
    rejection_reason: Optional[str] = None
    idempotency_key: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    lines: List[OrderLineRead]
    audit_logs: List[OrderAuditLogRead] = []
    retailer: Optional[OrderRetailerInfo] = None


class OrderListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_number: str
    retailer_id: uuid.UUID
    retailer_name: Optional[str] = None
    order_source: str
    status: str
    gross_total: Decimal
    scheme_total: Decimal
    net_total: Decimal
    total_cases: int
    total_free_cases: int
    total_fulfilment_cases: int
    line_count: int
    created_at: datetime


class OrderListResponse(BaseModel):
    items: List[OrderListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class CreateOrderRequest(BaseModel):
    remarks: Optional[str] = None


class DeskLineCorrectionRequest(BaseModel):
    qty_cases: int = Field(..., gt=0, description="Corrected case quantity (must be >= 1)")
    reason: str = Field(..., min_length=1, max_length=500, description="Mandatory reason for quantity correction")


class DeskOrderRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500, description="Mandatory reason for order rejection")


class DeskOrderApproveRequest(BaseModel):
    note: Optional[str] = Field(None, max_length=500, description="Optional approval remarks")
