"""
FastAPI router for AI Order Extraction and Draft Management (Phase 7).

Endpoints:
- POST /api/v1/ai/order-drafts: Extract message into persistent AI order draft
- POST /api/v1/ai/extract: Direct extraction endpoint returning populated draft
- GET /api/v1/ai/order-drafts: Paginated list of retailer's drafts
- GET /api/v1/ai/order-drafts/{draft_id}: Single draft detail with line resolutions
- PATCH /api/v1/ai/order-drafts/{draft_id}/lines/{line_id}: Resolve product/unit/quantity
- DELETE /api/v1/ai/order-drafts/{draft_id}/lines/{line_id}: Discard unintended draft line
- POST /api/v1/ai/order-drafts/{draft_id}/confirm: Atomically transfer confirmed draft into shopping cart
"""

import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_role
from app.models.auth import Retailer
from app.models.ai import AIOrderDraft
from app.services.ai_draft_service import AIDraftService
from app.services.ai_matcher import AIMatcher
from app.schemas.ai import (
    AIExtractRequest,
    AIOrderDraftRead,
    AIOrderDraftLineRead,
    AIOrderDraftLineUpdate,
    AIDraftConfirmResponse,
    DraftProductRead,
)

router = APIRouter(prefix="/ai", tags=["AI Order Capture"])


def _format_draft_response(draft: AIOrderDraft) -> dict:
    """Format AIOrderDraft model into response shape including nested alternative schemas."""
    lines_read = []
    all_resolved = len(draft.lines) > 0
    ready_to_confirm = len(draft.lines) > 0

    for l in draft.lines:
        matched_read = None
        if l.matched_product:
            matched_read = AIMatcher.to_draft_product_read(l.matched_product)

        resolved_read = None
        if l.resolved_product:
            resolved_read = AIMatcher.to_draft_product_read(l.resolved_product)

        # Parse alternatives json
        alts = []
        if isinstance(l.alternatives, list):
            for a in l.alternatives:
                if isinstance(a, dict):
                    alts.append(DraftProductRead(**a))

        line_dict = {
            "id": l.id,
            "draft_id": l.draft_id,
            "raw_fragment": l.raw_fragment,
            "product_mention": l.product_mention,
            "quantity_value": l.quantity_value,
            "unit_text": l.unit_text,
            "normalized_unit": l.normalized_unit,
            "matched_product_id": l.matched_product_id,
            "matched_product": matched_read,
            "match_status": l.match_status,
            "confidence": l.confidence,
            "clarification_reason": l.clarification_reason,
            "alternatives": alts,
            "warning": l.warning,
            "resolved_product_id": l.resolved_product_id,
            "resolved_product": resolved_read,
            "resolved_qty_cases": l.resolved_qty_cases,
            "is_confirmed": l.is_confirmed,
            "created_at": l.created_at,
        }
        lines_read.append(line_dict)

        if not l.is_confirmed:
            all_resolved = False
            ready_to_confirm = False

    return {
        "id": draft.id,
        "retailer_id": draft.retailer_id,
        "original_message": draft.original_message,
        "status": draft.status,
        "parser_used": getattr(draft, "parser_used", "gemini") or "gemini",
        "confirmed_at": draft.confirmed_at,
        "lines": lines_read,
        "metadata_json": draft.metadata_json,
        "all_resolved": all_resolved,
        "ready_to_confirm": ready_to_confirm,
        "created_at": draft.created_at,
        "updated_at": draft.updated_at,
    }


@router.post(
    "/order-drafts",
    response_model=AIOrderDraftRead,
    status_code=status.HTTP_201_CREATED,
    summary="Extract an informal retailer message into an editable AI order draft",
)
def create_order_draft(
    request: AIExtractRequest,
    current_user: dict = Depends(require_role(["retailer"])),
    db: Session = Depends(get_db),
):
    retailer_id = uuid.UUID(current_user["id"])
    draft = AIDraftService.create_draft_from_message(
        db=db,
        retailer_id=retailer_id,
        raw_text=request.raw_text,
    )
    return _format_draft_response(draft)


@router.post(
    "/extract",
    response_model=AIOrderDraftRead,
    status_code=status.HTTP_201_CREATED,
    summary="Direct extraction endpoint alias",
)
def extract_order_message(
    request: AIExtractRequest,
    current_user: dict = Depends(require_role(["retailer"])),
    db: Session = Depends(get_db),
):
    """Direct alias to create_order_draft per specifications."""
    return create_order_draft(request=request, current_user=current_user, db=db)


@router.get(
    "/order-drafts",
    summary="List retailer's AI order drafts",
)
def list_order_drafts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_role(["retailer"])),
    db: Session = Depends(get_db),
):
    retailer_id = uuid.UUID(current_user["id"])
    data = AIDraftService.list_drafts(
        db=db,
        retailer_id=retailer_id,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [_format_draft_response(d) for d in data["items"]],
        "total": data["total"],
        "page": data["page"],
        "page_size": data["page_size"],
        "total_pages": data["total_pages"],
    }


@router.get(
    "/order-drafts/{draft_id}",
    response_model=AIOrderDraftRead,
    summary="Get single AI order draft with lines",
)
def get_order_draft(
    draft_id: uuid.UUID,
    current_user: dict = Depends(require_role(["retailer"])),
    db: Session = Depends(get_db),
):
    retailer_id = uuid.UUID(current_user["id"])
    draft = AIDraftService.get_draft_by_id(
        db=db,
        retailer_id=retailer_id,
        draft_id=draft_id,
    )
    return _format_draft_response(draft)


@router.patch(
    "/order-drafts/{draft_id}/lines/{line_id}",
    response_model=AIOrderDraftRead,
    summary="Resolve ambiguous product, clarify unit, or edit quantity on a draft line",
)
def update_draft_line(
    draft_id: uuid.UUID,
    line_id: uuid.UUID,
    update_data: AIOrderDraftLineUpdate,
    current_user: dict = Depends(require_role(["retailer"])),
    db: Session = Depends(get_db),
):
    retailer_id = uuid.UUID(current_user["id"])
    draft = AIDraftService.update_draft_line(
        db=db,
        retailer_id=retailer_id,
        draft_id=draft_id,
        line_id=line_id,
        update_data=update_data,
    )
    return _format_draft_response(draft)


@router.delete(
    "/order-drafts/{draft_id}/lines/{line_id}",
    response_model=AIOrderDraftRead,
    summary="Remove an unintended line from a draft",
)
def delete_draft_line(
    draft_id: uuid.UUID,
    line_id: uuid.UUID,
    current_user: dict = Depends(require_role(["retailer"])),
    db: Session = Depends(get_db),
):
    retailer_id = uuid.UUID(current_user["id"])
    draft = AIDraftService.delete_draft_line(
        db=db,
        retailer_id=retailer_id,
        draft_id=draft_id,
        line_id=line_id,
    )
    return _format_draft_response(draft)


@router.post(
    "/order-drafts/{draft_id}/confirm",
    response_model=AIDraftConfirmResponse,
    summary="Atomically confirm draft items and add to active shopping cart",
)
def confirm_draft_to_cart(
    draft_id: uuid.UUID,
    current_user: dict = Depends(require_role(["retailer"])),
    db: Session = Depends(get_db),
):
    """
    Validates that all items in the draft are resolved and in stock,
    and atomically transfers them into the retailer's active shopping cart.
    Does NOT create an Order or deduct stock.
    """
    retailer_id = uuid.UUID(current_user["id"])
    return AIDraftService.confirm_draft_to_cart(
        db=db,
        retailer_id=retailer_id,
        draft_id=draft_id,
    )
