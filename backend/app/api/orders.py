"""
API endpoints for Orders:
- POST /api/v1/orders (Retailer: submit cart to order)
- GET /api/v1/orders (Retailer / Order Desk: list orders)
- GET /api/v1/orders/{order_id} (Retailer: view own order / Order Desk: view order)
"""

import uuid
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user, require_role
from app.services.order import OrderService
from app.schemas.order import (
    OrderRead,
    OrderListResponse,
    CreateOrderRequest,
)

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post(
    "",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Submit current shopping cart as an order",
)
def place_order(
    request: Optional[CreateOrderRequest] = None,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: dict = Depends(require_role(["retailer"])),
    db: Session = Depends(get_db),
):
    """
    Submits the retailer's active shopping cart as an order:
    - Freezes price and scheme snapshots.
    - Leaves inventory intact (deduction happens on desk approval).
    - Clears the cart upon success.
    - Idempotency key avoids duplicate orders from network retries.
    """
    retailer_id = uuid.UUID(current_user["id"])
    remarks = request.remarks if request else None
    return OrderService.create_order_from_cart(
        db=db,
        retailer_id=retailer_id,
        remarks=remarks,
        idempotency_key=idempotency_key,
    )


@router.get(
    "",
    response_model=OrderListResponse,
    summary="List orders (Retailer views own; Desk views all)",
)
def list_orders(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns paginated orders:
    - Retailers receive their own order history sorted newest first.
    - Order Desk staff receive all orders in the system.
    """
    if current_user["role"] == "retailer":
        retailer_id = uuid.UUID(current_user["id"])
        return OrderService.list_retailer_orders(
            db=db,
            retailer_id=retailer_id,
            page=page,
            page_size=page_size,
        )
    else:
        return OrderService.list_desk_orders(
            db=db,
            status_filter=None,
            page=page,
            page_size=page_size,
        )


@router.get(
    "/{order_id}",
    response_model=OrderRead,
    summary="Get full order details by ID",
)
def get_order(
    order_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns full order details including line items with frozen snapshots and audit history:
    - Retailers can only view orders belonging to their account (404 otherwise).
    - Order Desk staff can view any order.
    """
    if current_user["role"] == "retailer":
        retailer_id = uuid.UUID(current_user["id"])
        return OrderService.get_retailer_order(
            db=db,
            retailer_id=retailer_id,
            order_id=order_id,
        )
    else:
        return OrderService.get_desk_order(
            db=db,
            order_id=order_id,
        )
