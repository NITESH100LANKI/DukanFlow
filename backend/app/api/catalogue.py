"""
Catalogue API endpoints:
- GET /api/v1/catalogue/products: Paginated, searchable product list with active schemes.
- GET /api/v1/catalogue/products/{sku}: Single product details by SKU.
- GET /api/v1/catalogue/categories: Distinct category list.

Access: Authenticated Retailers and Order Desk staff only.
Unauthenticated users cannot view wholesale prices.
"""

from typing import Annotated, Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import require_role
from app.schemas.catalogue import ProductListResponse, ProductRead
from app.services.catalogue import CatalogueService

router = APIRouter(prefix="/catalogue", tags=["catalogue"])


@router.get("/categories", response_model=List[str])
def list_categories(
    current_user: Annotated[dict, Depends(require_role(["retailer", "order_desk"]))],
    db: Session = Depends(get_db),
):
    """Returns all active product categories."""
    return CatalogueService.get_categories(db)


@router.get("/products", response_model=ProductListResponse)
def list_products(
    current_user: Annotated[dict, Depends(require_role(["retailer", "order_desk"]))],
    q: Optional[str] = Query(None, min_length=1, description="Search by name, SKU or description"),
    category: Optional[str] = Query(None, description="Filter by product category"),
    in_stock: bool = Query(False, description="Filter to only products with positive stock cases"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """
    List active products with pagination, search, category and in-stock filtering.
    Includes active promotional scheme information.
    """
    return CatalogueService.get_products(
        db=db,
        q=q,
        category=category,
        in_stock=in_stock,
        page=page,
        page_size=page_size,
    )


@router.get("/products/{sku}", response_model=ProductRead)
def get_product_detail(
    sku: str,
    current_user: Annotated[dict, Depends(require_role(["retailer", "order_desk"]))],
    db: Session = Depends(get_db),
):
    """
    Get full details for a single product by its SKU.
    """
    product = CatalogueService.get_product_by_sku(db=db, sku=sku)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with SKU '{sku}' not found or inactive",
        )
    return product

