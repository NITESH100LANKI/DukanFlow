"""
Cart service layer.
Handles shopping cart state, scheme engine integration, stock validation, and total recalculations.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from app.models.cart import Cart, CartLine
from app.models.catalogue import Product, Scheme
from app.services.scheme_engine import calculate_line_scheme, TWO_PLACES


class CartService:

    @classmethod
    def get_or_create_cart(cls, db: Session, retailer_id: uuid.UUID) -> Cart:
        """Retrieves an existing cart for the retailer or creates a new one."""
        stmt = select(Cart).where(Cart.retailer_id == retailer_id)
        cart = db.execute(stmt).scalar_one_or_none()
        if not cart:
            cart = Cart(retailer_id=retailer_id)
            db.add(cart)
            db.commit()
            db.refresh(cart)
        return cart

    @classmethod
    def _find_active_scheme(cls, product: Product, on_date: Optional[date] = None) -> Optional[Scheme]:
        """Finds currently active scheme for a product."""
        check_date = on_date or date.today()
        for scheme in product.schemes:
            if (
                scheme.is_active
                and scheme.valid_from <= check_date <= scheme.valid_to
            ):
                return scheme
        return None

    @classmethod
    def get_cart_data(cls, db: Session, retailer_id: uuid.UUID) -> Dict[str, Any]:
        """
        Recalculates and returns full cart data with scheme benefits and summary totals.
        Authoritative pricing is calculated server-side every time.
        """
        cart = cls.get_or_create_cart(db, retailer_id)

        # Query all cart lines with eager-loaded products and schemes
        stmt = (
            select(CartLine)
            .where(CartLine.cart_id == cart.id)
            .order_by(CartLine.created_at.asc())
        )
        lines = db.execute(stmt).scalars().all()

        computed_lines = []
        total_paid_cases = 0
        total_free_cases = 0
        total_fulfilment_cases = 0
        gross_total = Decimal("0.00")
        total_discount = Decimal("0.00")
        total_benefit_value = Decimal("0.00")
        net_total = Decimal("0.00")

        today = date.today()

        for line in lines:
            product = line.product
            case_price = product.dealer_price_per_case
            scheme = cls._find_active_scheme(product, today)

            # Calculate scheme
            calc = calculate_line_scheme(
                case_price=case_price,
                paid_qty=line.qty_cases,
                scheme=scheme,
                order_date=today,
            )

            scheme_info = None
            if calc.scheme_applied and scheme:
                scheme_info = {
                    "scheme_type": scheme.scheme_type,
                    "free_qty": calc.free_qty_cases,
                    "discount_amount": calc.discount_amount,
                    "benefit_value": calc.benefit_value,
                    "description": calc.scheme_description,
                }

            computed_line = {
                "id": line.id,
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "pack_size": product.pack_size,
                "case_qty": product.case_qty,
                "price_per_pack": product.dealer_price_per_pack,
                "price_per_case": case_price,
                "qty_cases": calc.paid_qty_cases,
                "qty_free": calc.free_qty_cases,
                "qty_fulfilment": calc.fulfilment_qty_cases,
                "gross_line_total": calc.gross_amount,
                "discount_amount": calc.discount_amount,
                "benefit_value": calc.benefit_value,
                "net_line_total": calc.net_payable,
                "scheme_applied": scheme_info,
                "created_at": line.created_at,
                "updated_at": line.updated_at,
            }
            computed_lines.append(computed_line)

            total_paid_cases += calc.paid_qty_cases
            total_free_cases += calc.free_qty_cases
            total_fulfilment_cases += calc.fulfilment_qty_cases
            gross_total += calc.gross_amount
            total_discount += calc.discount_amount
            total_benefit_value += calc.benefit_value
            net_total += calc.net_payable

        summary = {
            "total_cases_paid": total_paid_cases,
            "total_cases_free": total_free_cases,
            "total_cases_fulfilment": total_fulfilment_cases,
            "gross_total": gross_total.quantize(TWO_PLACES),
            "total_discount": total_discount.quantize(TWO_PLACES),
            "total_benefit_value": total_benefit_value.quantize(TWO_PLACES),
            "net_total": net_total.quantize(TWO_PLACES),
            "item_count": len(computed_lines),
        }

        return {
            "id": cart.id,
            "retailer_id": cart.retailer_id,
            "lines": computed_lines,
            "summary": summary,
            "created_at": cart.created_at,
            "updated_at": cart.updated_at,
        }

    @classmethod
    def add_or_update_line(
        cls,
        db: Session,
        retailer_id: uuid.UUID,
        product_id: uuid.UUID,
        qty_cases: int,
    ) -> Dict[str, Any]:
        """
        Adds or updates a product line in the retailer's cart.
        Validates inventory requirement using total fulfilment quantity.
        """
        if qty_cases < 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Quantity must be at least 1 case",
            )

        # Verify product existence and status
        stmt_prod = select(Product).where(
            Product.id == product_id, Product.is_active.is_(True)
        )
        product = db.execute(stmt_prod).scalar_one_or_none()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found or inactive",
            )

        # Check stock with scheme fulfilment quantity
        scheme = cls._find_active_scheme(product, date.today())
        calc = calculate_line_scheme(
            case_price=product.dealer_price_per_case,
            paid_qty=qty_cases,
            scheme=scheme,
            order_date=date.today(),
        )

        if product.stock_cases <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Product '{product.name}' is currently out of stock (0 cases available)",
            )

        if product.stock_cases < calc.fulfilment_qty_cases:
            free_msg = (
                f" (+{calc.free_qty_cases} free scheme case{'s' if calc.free_qty_cases > 1 else ''})"
                if calc.free_qty_cases > 0
                else ""
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Requested {qty_cases} cases{free_msg} requires {calc.fulfilment_qty_cases} "
                    f"fulfilment cases, but only {product.stock_cases} cases are in stock."
                ),
            )

        cart = cls.get_or_create_cart(db, retailer_id)

        # Check if line already exists
        stmt_line = select(CartLine).where(
            CartLine.cart_id == cart.id, CartLine.product_id == product_id
        )
        line = db.execute(stmt_line).scalar_one_or_none()

        if line:
            line.qty_cases = qty_cases
        else:
            line = CartLine(
                cart_id=cart.id, product_id=product_id, qty_cases=qty_cases
            )
            db.add(line)

        db.commit()
        return cls.get_cart_data(db, retailer_id)

    @classmethod
    def update_line_qty(
        cls,
        db: Session,
        retailer_id: uuid.UUID,
        line_id: uuid.UUID,
        qty_cases: int,
    ) -> Dict[str, Any]:
        """Updates quantity for an existing cart line."""
        if qty_cases < 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Quantity must be at least 1 case",
            )

        cart = cls.get_or_create_cart(db, retailer_id)
        stmt = select(CartLine).where(
            CartLine.id == line_id, CartLine.cart_id == cart.id
        )
        line = db.execute(stmt).scalar_one_or_none()
        if not line:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart line not found in your cart",
            )

        product = line.product
        scheme = cls._find_active_scheme(product, date.today())
        calc = calculate_line_scheme(
            case_price=product.dealer_price_per_case,
            paid_qty=qty_cases,
            scheme=scheme,
            order_date=date.today(),
        )

        if product.stock_cases < calc.fulfilment_qty_cases:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Requested {qty_cases} cases requires {calc.fulfilment_qty_cases} "
                    f"fulfilment cases, but only {product.stock_cases} cases are in stock."
                ),
            )

        line.qty_cases = qty_cases
        db.commit()
        return cls.get_cart_data(db, retailer_id)

    @classmethod
    def remove_line(
        cls, db: Session, retailer_id: uuid.UUID, line_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Removes a single line from the cart."""
        cart = cls.get_or_create_cart(db, retailer_id)
        stmt = select(CartLine).where(
            CartLine.id == line_id, CartLine.cart_id == cart.id
        )
        line = db.execute(stmt).scalar_one_or_none()
        if not line:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart line not found in your cart",
            )

        db.delete(line)
        db.commit()
        return cls.get_cart_data(db, retailer_id)

    @classmethod
    def clear_cart(cls, db: Session, retailer_id: uuid.UUID) -> Dict[str, Any]:
        """Removes all lines from the retailer's cart."""
        cart = cls.get_or_create_cart(db, retailer_id)
        stmt = delete(CartLine).where(CartLine.cart_id == cart.id)
        db.execute(stmt)
        db.commit()
        return cls.get_cart_data(db, retailer_id)
