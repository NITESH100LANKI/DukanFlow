"""
Pydantic schemas for Order Desk CSV Export & Accounting Integration (Phase 8).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class ExportProfileRead(BaseModel):
    """Metadata describing an export format profile."""
    key: str
    display_name: str
    description: str
    is_preliminary: bool = True


class ExportableOrderLineSummary(BaseModel):
    """Summary of line snapshots for previewing an exportable order."""
    sku_snapshot: str
    name_snapshot: str
    qty_cases: int
    free_cases: int
    fulfilment_qty_cases: int
    gross_amount: Decimal
    net_amount: Decimal

    model_config = ConfigDict(from_attributes=True)


class ExportableOrderItem(BaseModel):
    """Approved order available for export."""
    id: uuid.UUID
    order_number: str
    created_at: datetime
    status: str
    retailer_id: uuid.UUID
    retailer_name: str
    retailer_mobile: str
    tally_ledger_name: Optional[str] = None
    total_cases: int
    total_free_cases: int
    total_fulfilment_cases: int
    gross_total: Decimal
    discount_total: Decimal
    benefit_total: Decimal
    net_total: Decimal
    export_count: int = 0
    last_exported_at: Optional[datetime] = None
    lines_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ExportableOrderListResponse(BaseModel):
    """Paginated list of exportable approved orders."""
    items: List[ExportableOrderItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class CreateExportBatchRequest(BaseModel):
    """Request payload to export selected orders."""
    order_ids: List[uuid.UUID]
    profile: str = "generic"


class ExportBatchLineRead(BaseModel):
    """Record of an order included in an export batch."""
    id: uuid.UUID
    batch_id: uuid.UUID
    order_id: uuid.UUID
    order_number_snapshot: str
    order_net_total: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExportBatchRead(BaseModel):
    """Full detail of a generated export batch."""
    id: uuid.UUID
    batch_number: str
    export_profile: str
    generated_by: uuid.UUID
    generator_name: Optional[str] = "Order Desk"
    generated_at: datetime
    order_count: int
    record_count: int
    total_gross: Decimal
    total_discount: Decimal
    total_benefit: Decimal
    total_net: Decimal
    total_fulfilment_cases: int
    csv_filename: str
    file_checksum: str
    batch_lines: Optional[List[ExportBatchLineRead]] = None

    model_config = ConfigDict(from_attributes=True)


class ExportBatchListItem(BaseModel):
    """Item in the historical export batches list."""
    id: uuid.UUID
    batch_number: str
    export_profile: str
    generated_by: uuid.UUID
    generator_name: Optional[str] = "Order Desk"
    generated_at: datetime
    order_count: int
    record_count: int
    total_gross: Decimal
    total_discount: Decimal
    total_benefit: Decimal
    total_net: Decimal
    total_fulfilment_cases: int
    csv_filename: str
    file_checksum: str

    model_config = ConfigDict(from_attributes=True)


class ExportBatchListResponse(BaseModel):
    """Paginated list of past export batches."""
    items: List[ExportBatchListItem]
    total: int
    page: int
    page_size: int
    total_pages: int

