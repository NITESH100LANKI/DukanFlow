"""
Pydantic schemas for AI Order Extraction and Draft Management:
- AIExtractRequest (raw text input)
- GeminiExtractionResult & ExtractedItem (Gemini structured output validation)
- AIOrderDraftLineRead & AIOrderDraftLineUpdate (line items, alternatives, resolution)
- AIOrderDraftRead (full draft with lines and status)
- AIDraftConfirmResponse (cart addition confirmation summary)
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict


class AIExtractRequest(BaseModel):
    """Retailer raw unstructured order message in Hindi, Hinglish, or English."""
    raw_text: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Informal retailer message e.g. '5 peti Parle-G, 2 case detergent'",
    )


class ExtractedItem(BaseModel):
    """Pydantic model for structured Gemini extraction of a single item mention."""
    raw_fragment: str = Field(
        ...,
        description="Exact portion of retailer text corresponding to this line item",
    )
    product_mention: str = Field(
        ...,
        description="Product name or description extracted from the message",
    )
    quantity_value: Optional[int] = Field(
        None,
        description="Explicit quantity stated in the message, or null if unspecified",
    )
    unit_text: Optional[str] = Field(
        None,
        description="Original unit expression e.g. 'peti', 'case', 'dibba', 'packet', 'piece'",
    )
    additional_description: Optional[str] = Field(
        None,
        description="Additional variant, size, packaging, or brand descriptors",
    )


class GeminiExtractionResult(BaseModel):
    """Root Pydantic schema passed to Gemini for structured JSON generation."""
    items: List[ExtractedItem] = Field(
        default_factory=list,
        description="List of detected item intents in the message",
    )
    unparsed_text: Optional[str] = Field(
        None,
        description="Any portion of the message that could not confidently be assigned to an item",
    )
    parser_used: str = Field(
        default="gemini",
        description="Engine used to parse: 'gemini' or 'fallback'",
    )


class DraftProductRead(BaseModel):
    """Lightweight product representation attached to draft lines and candidate alternatives."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    name: str
    pack_size: Optional[str] = ""
    case_qty: int
    dealer_price_per_pack: Decimal
    dealer_price_per_case: Decimal
    stock_cases: int
    stock_status: str  # in_stock | out_of_stock
    category: Optional[str] = None


class AIOrderDraftLineUpdate(BaseModel):
    """Retailer mutation to resolve an ambiguous or unit-unclear draft line."""
    resolved_product_id: Optional[uuid.UUID] = Field(
        None, description="Chosen product ID from alternatives or catalogue"
    )
    resolved_qty_cases: Optional[int] = Field(
        None, ge=1, description="Explicit number of cases to add to cart"
    )
    normalized_unit: Optional[str] = Field(
        None, pattern="^(case|piece|unknown)$", description="Resolved unit type"
    )


class AIOrderDraftLineRead(BaseModel):
    """Single line item representation for draft review."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    draft_id: uuid.UUID
    raw_fragment: str
    product_mention: str
    quantity_value: Optional[int] = None
    unit_text: Optional[str] = None
    normalized_unit: str  # case | piece | unknown

    matched_product_id: Optional[uuid.UUID] = None
    matched_product: Optional[DraftProductRead] = None
    match_status: str  # confirmed | ambiguous | unmatched
    confidence: Optional[str] = None  # high | medium | low | None
    clarification_reason: Optional[str] = None
    alternatives: List[DraftProductRead] = []
    warning: Optional[str] = None  # e.g. OUT_OF_STOCK

    resolved_product_id: Optional[uuid.UUID] = None
    resolved_product: Optional[DraftProductRead] = None
    resolved_qty_cases: Optional[int] = None
    is_confirmed: bool = False

    created_at: datetime


class AIOrderDraftRead(BaseModel):
    """Full AI order draft with review lines and overall resolution state."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    retailer_id: uuid.UUID
    original_message: str
    status: str  # DRAFT | CONFIRMED | DISCARDED
    parser_used: str = "gemini"  # gemini | fallback
    confirmed_at: Optional[datetime] = None
    lines: List[AIOrderDraftLineRead] = []
    metadata_json: Optional[dict] = None
    all_resolved: bool = False
    ready_to_confirm: bool = False
    created_at: datetime
    updated_at: datetime


class AIDraftConfirmResponse(BaseModel):
    """Response returned upon atomically sending a confirmed draft to the cart."""
    draft_id: uuid.UUID
    status: str
    confirmed_items_count: int
    cart_total_cases: int
    cart_net_total: Decimal
    message: str


class DeskCorrectProductRequest(BaseModel):
    """Order Desk product correction request, establishing a learned retailer alias."""
    product_id: uuid.UUID = Field(
        ..., description="Canonical product ID to assign to this order line"
    )
    reason: str = Field(
        ..., min_length=3, max_length=500, description="Reason for product correction"
    )

