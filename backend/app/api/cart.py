"""
Cart API endpoints:
- GET /api/v1/cart: Get current retailer's cart with recalculated totals and scheme benefits.
- POST /api/v1/cart/lines: Add or replace a product line in the cart.
- PATCH /api/v1/cart/lines/{line_id}: Update quantity for a cart line.
- PUT /api/v1/cart/lines/{line_id}: Update quantity for a cart line.
- DELETE /api/v1/cart/lines/{line_id}: Remove a line from the cart.
- DELETE /api/v1/cart: Clear all items from the cart.

Access: Authenticated Retailers only. Order Desk staff are denied access.
"""

import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_role
from app.schemas.cart import (
    CartRead,
    AddCartLineRequest,
    UpdateCartLineRequest,
)
from app.services.cart import CartService

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("", response_model=CartRead)
def get_cart(
    current_user: Annotated[dict, Depends(require_role(["retailer"]))],
    db: Session = Depends(get_db),
):
    """
    Retrieve the current retailer's active shopping cart.
    Recalculates all scheme benefits, gross total, and payable amounts.
    """
    retailer_id = uuid.UUID(current_user["id"])
    return CartService.get_cart_data(db=db, retailer_id=retailer_id)


@router.post("/lines", response_model=CartRead)
def add_or_update_cart_line(
    payload: AddCartLineRequest,
    current_user: Annotated[dict, Depends(require_role(["retailer"]))],
    db: Session = Depends(get_db),
):
    """
    Add a product line to the cart or update its quantity.
    Revalidates inventory using total scheme fulfilment quantity.
    """
    retailer_id = uuid.UUID(current_user["id"])
    return CartService.add_or_update_line(
        db=db,
        retailer_id=retailer_id,
        product_id=payload.product_id,
        qty_cases=payload.qty_cases,
    )


@router.patch("/lines/{line_id}", response_model=CartRead)
def patch_cart_line(
    line_id: uuid.UUID,
    payload: UpdateCartLineRequest,
    current_user: Annotated[dict, Depends(require_role(["retailer"]))],
    db: Session = Depends(get_db),
):
    """Update case quantity for an existing cart line."""
    retailer_id = uuid.UUID(current_user["id"])
    return CartService.update_line_qty(
        db=db,
        retailer_id=retailer_id,
        line_id=line_id,
        qty_cases=payload.qty_cases,
    )


@router.put("/lines/{line_id}", response_model=CartRead)
def put_cart_line(
    line_id: uuid.UUID,
    payload: UpdateCartLineRequest,
    current_user: Annotated[dict, Depends(require_role(["retailer"]))],
    db: Session = Depends(get_db),
):
    """Update case quantity for an existing cart line (PUT alternative)."""
    retailer_id = uuid.UUID(current_user["id"])
    return CartService.update_line_qty(
        db=db,
        retailer_id=retailer_id,
        line_id=line_id,
        qty_cases=payload.qty_cases,
    )


@router.delete("/lines/{line_id}", response_model=CartRead)
def delete_cart_line(
    line_id: uuid.UUID,
    current_user: Annotated[dict, Depends(require_role(["retailer"]))],
    db: Session = Depends(get_db),
):
    """Remove a specific line from the cart."""
    retailer_id = uuid.UUID(current_user["id"])
    return CartService.remove_line(
        db=db,
        retailer_id=retailer_id,
        line_id=line_id,
    )


@router.delete("", response_model=CartRead)
def clear_cart(
    current_user: Annotated[dict, Depends(require_role(["retailer"]))],
    db: Session = Depends(get_db),
):
    """Clear all lines from the cart."""
    retailer_id = uuid.UUID(current_user["id"])
    return CartService.clear_cart(db=db, retailer_id=retailer_id)
