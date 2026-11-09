"""
API endpoints for Order Desk Order Management:
- GET /api/v1/desk/orders (Order Desk queue with status filtering)
- GET /api/v1/desk/orders/{order_id} (Order Desk detail review)
- PATCH /api/v1/desk/orders/{order_id}/lines/{line_id} (Line quantity correction with snapshot recalc)
- POST /api/v1/desk/orders/{order_id}/approve (Approve order with deterministic row locks & stock deduction)
- POST /api/v1/desk/orders/{order_id}/reject (Reject order with required reason; zero stock deduction)
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_role
from app.services.order import OrderService
from app.schemas.order import (
    OrderRead,
    OrderListResponse,
    DeskLineCorrectionRequest,
    DeskOrderRejectRequest,
    DeskOrderApproveRequest,
)

router = APIRouter(prefix="/desk/orders", tags=["desk-orders"])


@router.get(
    "",
    response_model=OrderListResponse,
    summary="Order Desk order queue with optional status filter",
)
def list_desk_queue(
    status: Optional[str] = Query(None, description="Filter by status: SUBMITTED, APPROVED, or REJECTED"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    current_user: dict = Depends(require_role(["order_desk"])),
    db: Session = Depends(get_db),
):
    """
    Returns the order review queue for Order Desk operators.
    Supports filtering by status (e.g. SUBMITTED).
    """
    return OrderService.list_desk_orders(
        db=db,
        status_filter=status,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{order_id}",
    response_model=OrderRead,
    summary="Order Desk order details with complete audit trail",
)
def get_desk_order_detail(
    order_id: uuid.UUID,
    current_user: dict = Depends(require_role(["order_desk"])),
    db: Session = Depends(get_db),
):
    """
    Returns comprehensive order details for review, including frozen snapshots and audit history.
    """
    return OrderService.get_desk_order(
        db=db,
        order_id=order_id,
    )


@router.patch(
    "/{order_id}/lines/{line_id}",
    response_model=OrderRead,
    summary="Correct line case quantity on a SUBMITTED order",
)
def correct_order_line(
    order_id: uuid.UUID,
    line_id: uuid.UUID,
    request: DeskLineCorrectionRequest,
    current_user: dict = Depends(require_role(["order_desk"])),
    db: Session = Depends(get_db),
):
    """
    Order Desk operator corrects requested case quantity:
    - Recalculates scheme bonus cases and discounts using frozen line snapshots.
    - Updates order totals and records an immutable audit log.
    - Requires a non-empty reason.
    """
    desk_user_id = uuid.UUID(current_user["id"])
    return OrderService.correct_line_quantity(
        db=db,
        order_id=order_id,
        line_id=line_id,
        new_qty_cases=request.qty_cases,
        reason=request.reason,
        desk_user_id=desk_user_id,
    )


@router.post(
    "/{order_id}/approve",
    response_model=OrderRead,
    summary="Approve order and deduct inventory atomically",
)
def approve_order(
    order_id: uuid.UUID,
    request: Optional[DeskOrderApproveRequest] = None,
    current_user: dict = Depends(require_role(["order_desk"])),
    db: Session = Depends(get_db),
):
    """
    Approve an order:
    - Order must be in SUBMITTED status.
    - Product rows are locked in deterministic order (prevents deadlocks).
    - Checks physical fulfilment quantities (including free scheme goods).
    - Deducts inventory and sets status to APPROVED.
    - If stock is insufficient, raises 409 Conflict with full details and rolls back.
    """
    desk_user_id = uuid.UUID(current_user["id"])
    note = request.note if request else None
    return OrderService.approve_order(
        db=db,
        order_id=order_id,
        desk_user_id=desk_user_id,
        note=note,
    )


@router.post(
    "/{order_id}/reject",
    response_model=OrderRead,
    summary="Reject order with mandatory reason (zero stock deduction)",
)
def reject_order(
    order_id: uuid.UUID,
    request: DeskOrderRejectRequest,
    current_user: dict = Depends(require_role(["order_desk"])),
    db: Session = Depends(get_db),
):
    """
    Reject an order:
    - Order must be in SUBMITTED status.
    - Requires mandatory reason.
    - Sets status to REJECTED.
    - Inventory is NOT deducted.
    """
    desk_user_id = uuid.UUID(current_user["id"])
    return OrderService.reject_order(
        db=db,
        order_id=order_id,
        reason=request.reason,
        desk_user_id=desk_user_id,
    )
