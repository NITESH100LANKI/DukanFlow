"""
Service layer for Catalogue and Scheme retrieval.
Decouples database operations from HTTP route handlers.
"""

import math
from datetime import date
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from app.models.catalogue import Product, Scheme


class CatalogueService:
    @staticmethod
    def _calculate_stock_status(stock_cases: int) -> str:
        """Determines stock badge status."""
        if stock_cases <= 0:
            return "out_of_stock"
        elif stock_cases < 10:
            return "low_stock"
        return "in_stock"

    @classmethod
    def _find_active_scheme(cls, product: Product, on_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves the currently applicable active scheme for a product.
        MVP rule: At most one scheme is active at a time.
        """
        check_date = on_date or date.today()
        for scheme in product.schemes:
            if (
                scheme.is_active
                and scheme.valid_from <= check_date <= scheme.valid_to
            ):
                return {
                    "id": scheme.id,
                    "scheme_type": scheme.scheme_type,
                    "min_qty": scheme.min_qty,
                    "free_qty": scheme.free_qty,
                    "discount_pct": scheme.discount_pct,
                    "valid_from": scheme.valid_from,
                    "valid_to": scheme.valid_to,
                    "is_active": scheme.is_active,
                    "description": scheme.description,
                }
        return None

    @classmethod
    def format_product_dict(cls, product: Product, on_date: Optional[date] = None) -> Dict[str, Any]:
        """Formats a product ORM instance into an API-ready dictionary with derived values."""
        active_scheme = cls._find_active_scheme(product, on_date)
        stock_status = cls._calculate_stock_status(product.stock_cases)

        return {
            "id": product.id,
            "sku": product.sku,
            "name": product.name,
            "description": product.description,
            "pack_size": product.pack_size,
            "case_qty": product.case_qty,
            "dealer_price_per_pack": product.dealer_price_per_pack,
            "price_unit": product.price_unit,
            "dealer_price_per_case": product.dealer_price_per_case,
            "gst_rate_pct": product.gst_rate_pct,
            "stock_cases": product.stock_cases,
            "stock_status": stock_status,
            "category": product.category,
            "is_active": product.is_active,
            "active_scheme": active_scheme,
            "created_at": product.created_at,
            "updated_at": product.updated_at,
        }

    @classmethod
    def get_products(
        cls,
        db: Session,
        q: Optional[str] = None,
        category: Optional[str] = None,
        in_stock: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        Lists active products with search, filtering, and pagination.
        """
        base_query = select(Product).where(Product.is_active.is_(True))

        if q and q.strip():
            search_term = f"%{q.strip()}%"
            base_query = base_query.where(
                or_(
                    Product.name.ilike(search_term),
                    Product.sku.ilike(search_term),
                    Product.description.ilike(search_term),
                )
            )

        if category and category.strip():
            base_query = base_query.where(Product.category.ilike(category.strip()))

        if in_stock:
            base_query = base_query.where(Product.stock_cases > 0)

        # Count total items
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total = db.execute(count_stmt).scalar() or 0

        # Sort and paginate
        query = (
            base_query.order_by(Product.category.asc().nulls_last(), Product.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        products = db.execute(query).scalars().all()

        items = [cls.format_product_dict(p) for p in products]
        total_pages = math.ceil(total / page_size) if total > 0 else 1

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    @classmethod
    def get_product_by_sku(cls, db: Session, sku: str) -> Optional[Dict[str, Any]]:
        """
        Finds an active product by SKU.
        """
        stmt = select(Product).where(
            Product.sku == sku.strip(),
            Product.is_active.is_(True),
        )
        product = db.execute(stmt).scalar_one_or_none()
        if not product:
            return None

        return cls.format_product_dict(product)

    @staticmethod
    def get_categories(db: Session) -> List[str]:
        """
        Returns list of distinct active categories.
        """
        stmt = (
            select(Product.category)
            .where(Product.is_active.is_(True), Product.category.isnot(None))
            .distinct()
            .order_by(Product.category.asc())
        )
        results = db.execute(stmt).scalars().all()
        return [c for c in results if c]
