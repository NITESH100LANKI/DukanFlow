"""
Order Management Service (Phase 6):
- Order placement from active cart with price and scheme snapshots
- Idempotency support for duplicate submission protection
- Retailer and Order Desk order queries
- Order Desk line quantity corrections with snapshot-based recalculation
- Deterministic row-level locked stock validation and atomic deduction on approval
- Order rejection with mandatory reason and zero stock deduction
- Comprehensive immutable audit logging
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy import select, func, delete, desc
from sqlalchemy.orm import Session, selectinload

from app.models.auth import Retailer, OrderDeskUser
from app.models.catalogue import Product, Scheme
from app.models.cart import Cart, CartLine
from app.models.order import Order, OrderLine, OrderAuditLog
from app.models.ai import RetailerAlias
from app.services.ai_matcher import normalize_text
from app.services.scheme_engine import calculate_line_scheme, TWO_PLACES


class SnapshotSchemeWrapper:
    """Wrapper that mimics Scheme model attributes for calculation using saved snapshots."""
    def __init__(
        self,
        scheme_type: Optional[str],
        min_qty: Optional[int],
        free_qty: Optional[int],
        discount_pct: Optional[Decimal],
        description: Optional[str],
    ):
        self.scheme_type = scheme_type
        self.min_qty = min_qty
        self.free_qty = free_qty
        self.discount_pct = discount_pct
        self.description = description
        self.is_active = True
        self.valid_from = None
        self.valid_to = None


class OrderService:

    @staticmethod
    def generate_order_number(db: Session) -> str:
        """
        Generate a unique, human-readable order number: ORD-YYYYMMDD-XXXX
        """
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y%m%d")
        
        # Count orders placed today to derive sequential suffix
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        count_stmt = select(func.count(Order.id)).where(Order.created_at >= today_start)
        today_count = db.execute(count_stmt).scalar() or 0
        suffix = f"{today_count + 1:04d}"
        
        candidate = f"ORD-{date_str}-{suffix}"
        
        # Collision check
        exists = db.execute(select(Order.id).where(Order.order_number == candidate)).scalar_one_or_none()
        if exists:
            unique_hex = uuid.uuid4().hex[:4].upper()
            candidate = f"ORD-{date_str}-{unique_hex}"
        return candidate

    @classmethod
    def create_order_from_cart(
        cls,
        db: Session,
        retailer_id: uuid.UUID,
        remarks: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Order:
        """
        Transactionally create an order from the retailer's active cart.
        - Captures pricing and scheme snapshots on each OrderLine.
        - Inventory is NEVER deducted here (only on desk approval).
        - Clears the retailer's cart upon successful order creation.
        """
        # 1. Idempotency Check (Cross-retailer ownership security)
        if idempotency_key:
            existing_any = db.execute(
                select(Order)
                .options(
                    selectinload(Order.lines).selectinload(OrderLine.product),
                    selectinload(Order.audit_logs),
                    selectinload(Order.retailer),
                )
                .where(Order.idempotency_key == idempotency_key)
            ).scalar_one_or_none()
            if existing_any:
                if existing_any.retailer_id == retailer_id:
                    return existing_any
                else:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Idempotency key has already been used by another retailer",
                    )

        # 2. Fetch active cart
        cart_stmt = (
            select(Cart)
            .options(
                selectinload(Cart.lines).selectinload(CartLine.product),
            )
            .where(Cart.retailer_id == retailer_id)
        )
        cart = db.execute(cart_stmt).scalar_one_or_none()

        if not cart or not cart.lines:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot place order with an empty cart",
            )

        # 3. Fetch active schemes for products in cart
        product_ids = [line.product_id for line in cart.lines]
        schemes_stmt = (
            select(Scheme)
            .where(
                Scheme.product_id.in_(product_ids),
                Scheme.is_active == True,
            )
        )
        active_schemes = db.execute(schemes_stmt).scalars().all()
        scheme_map: Dict[uuid.UUID, Scheme] = {s.product_id: s for s in active_schemes}

        order_number = cls.generate_order_number(db)

        order = Order(
            order_number=order_number,
            retailer_id=retailer_id,
            status="SUBMITTED",
            order_source="manual",
            remarks=remarks,
            idempotency_key=idempotency_key,
        )
        db.add(order)
        db.flush()  # Allocate order.id

        total_gross = Decimal("0.00")
        total_discount = Decimal("0.00")
        total_benefit = Decimal("0.00")
        total_net = Decimal("0.00")
        total_cases = 0
        total_free_cases = 0
        total_fulfilment_cases = 0

        # 4. Build OrderLines with complete frozen snapshots
        for cart_line in cart.lines:
            product = cart_line.product
            if not product.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Product '{product.name}' is no longer active and cannot be ordered",
                )

            scheme = scheme_map.get(product.id)
            case_price = (product.dealer_price_per_pack * product.case_qty).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )

            calc_result = calculate_line_scheme(
                case_price=case_price,
                paid_qty=cart_line.qty_cases,
                scheme=scheme,
            )

            # Snapshots
            order_line = OrderLine(
                order_id=order.id,
                product_id=product.id,
                sku_snapshot=product.sku,
                name_snapshot=product.name,
                pack_size_snapshot=product.pack_size or "",
                case_qty_snapshot=product.case_qty,
                price_per_pack_snapshot=product.dealer_price_per_pack,
                price_per_case_snapshot=case_price,
                scheme_type_snapshot=scheme.scheme_type if scheme else None,
                min_qty_snapshot=scheme.min_qty if scheme else None,
                free_qty_snapshot=scheme.free_qty if scheme else None,
                discount_pct_snapshot=scheme.discount_pct if scheme else None,
                description_snapshot=scheme.description if scheme else None,
                qty_cases=cart_line.qty_cases,
                free_cases=calc_result.free_qty_cases,
                fulfilment_qty_cases=calc_result.fulfilment_qty_cases,
                unit_price=case_price,
                gross_amount=calc_result.gross_amount,
                discount_amount=calc_result.discount_amount,
                benefit_value=calc_result.benefit_value,
                net_amount=calc_result.net_payable,
            )
            db.add(order_line)

            total_gross += calc_result.gross_amount
            total_discount += calc_result.discount_amount
            total_benefit += calc_result.benefit_value
            total_net += calc_result.net_payable
            total_cases += cart_line.qty_cases
            total_free_cases += calc_result.free_qty_cases
            total_fulfilment_cases += calc_result.fulfilment_qty_cases

        order.gross_total = total_gross
        order.discount_total = total_discount
        order.benefit_total = total_benefit
        order.scheme_total = total_benefit
        order.net_total = total_net
        order.total_cases = total_cases
        order.total_free_cases = total_free_cases
        order.total_fulfilment_cases = total_fulfilment_cases

        # 5. Record submission audit log
        audit_entry = OrderAuditLog(
            order_id=order.id,
            actor_type="retailer",
            actor_id=retailer_id,
            action="SUBMITTED",
            from_status=None,
            to_status="SUBMITTED",
            note=f"Order submitted with {len(cart.lines)} line item(s)",
            details={
                "order_number": order.order_number,
                "lines_count": len(cart.lines),
                "total_cases": total_cases,
                "net_total": str(total_net),
            },
        )
        db.add(audit_entry)

        # 6. Clear retailer's active cart
        db.execute(delete(CartLine).where(CartLine.cart_id == cart.id))

        db.commit()

        # 7. Reload and return populated order
        return cls.get_order_by_id(db, order.id)

    @classmethod
    def get_order_by_id(cls, db: Session, order_id: uuid.UUID) -> Order:
        """Fetch order with lines, audit logs, and retailer populated."""
        stmt = (
            select(Order)
            .options(
                selectinload(Order.lines).selectinload(OrderLine.product),
                selectinload(Order.audit_logs),
                selectinload(Order.retailer),
            )
            .where(Order.id == order_id)
        )
        order = db.execute(stmt).scalar_one_or_none()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {order_id} not found",
            )
        return order

    @classmethod
    def get_retailer_order(
        cls, db: Session, retailer_id: uuid.UUID, order_id: uuid.UUID
    ) -> Order:
        """Fetch retailer's own order. Enforces tenant boundary."""
        order = cls.get_order_by_id(db, order_id)
        if order.retailer_id != retailer_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found or does not belong to you",
            )
        return order

    @classmethod
    def list_retailer_orders(
        cls,
        db: Session,
        retailer_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Paginated list of retailer's submitted orders."""
        if page < 1 or page_size < 1:
            raise HTTPException(status_code=400, detail="Invalid pagination parameters")

        count_stmt = select(func.count(Order.id)).where(Order.retailer_id == retailer_id)
        total = db.execute(count_stmt).scalar() or 0

        stmt = (
            select(Order)
            .options(selectinload(Order.lines), selectinload(Order.retailer))
            .where(Order.retailer_id == retailer_id)
            .order_by(desc(Order.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        orders = db.execute(stmt).scalars().all()

        items = []
        for o in orders:
            items.append({
                "id": o.id,
                "order_number": o.order_number,
                "retailer_id": o.retailer_id,
                "retailer_name": o.retailer.name if o.retailer else None,
                "order_source": o.order_source,
                "status": o.status,
                "gross_total": o.gross_total,
                "discount_total": o.discount_total,
                "benefit_total": o.benefit_total,
                "scheme_total": o.scheme_total,
                "net_total": o.net_total,
                "total_cases": o.total_cases,
                "total_free_cases": o.total_free_cases,
                "total_fulfilment_cases": o.total_fulfilment_cases,
                "line_count": len(o.lines),
                "created_at": o.created_at,
            })

        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    @classmethod
    def list_desk_orders(
        cls,
        db: Session,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Paginated list of orders for the Order Desk review queue."""
        if page < 1 or page_size < 1:
            raise HTTPException(status_code=400, detail="Invalid pagination parameters")

        query = select(Order)
        count_query = select(func.count(Order.id))

        if status_filter:
            status_upper = status_filter.upper()
            if status_upper not in ("SUBMITTED", "APPROVED", "REJECTED"):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid status filter. Must be SUBMITTED, APPROVED, or REJECTED",
                )
            query = query.where(Order.status == status_upper)
            count_query = count_query.where(Order.status == status_upper)

        total = db.execute(count_query).scalar() or 0

        query = (
            query.options(selectinload(Order.lines), selectinload(Order.retailer))
            .order_by(desc(Order.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        orders = db.execute(query).scalars().all()

        items = []
        for o in orders:
            items.append({
                "id": o.id,
                "order_number": o.order_number,
                "retailer_id": o.retailer_id,
                "retailer_name": o.retailer.name if o.retailer else None,
                "order_source": o.order_source,
                "status": o.status,
                "gross_total": o.gross_total,
                "discount_total": o.discount_total,
                "benefit_total": o.benefit_total,
                "scheme_total": o.scheme_total,
                "net_total": o.net_total,
                "total_cases": o.total_cases,
                "total_free_cases": o.total_free_cases,
                "total_fulfilment_cases": o.total_fulfilment_cases,
                "line_count": len(o.lines),
                "created_at": o.created_at,
            })

        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    @classmethod
    def correct_line_quantity(
        cls,
        db: Session,
        order_id: uuid.UUID,
        line_id: uuid.UUID,
        new_qty_cases: int,
        reason: str,
        desk_user_id: uuid.UUID,
    ) -> Order:
        """
        Order Desk quantity correction:
        - Locks the order row using SELECT ... FOR UPDATE.
        - Only permitted on orders in SUBMITTED status.
        - Recalculates scheme bonus, discount, and payable using SAVED SNAPSHOTS.
        - Updates line and re-aggregates order totals.
        - Records an immutable audit log entry.
        """
        order = db.execute(
            select(Order)
            .options(
                selectinload(Order.lines).selectinload(OrderLine.product),
                selectinload(Order.audit_logs),
                selectinload(Order.retailer),
            )
            .where(Order.id == order_id)
            .with_for_update()
        ).scalar_one_or_none()

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {order_id} not found",
            )

        if order.status != "SUBMITTED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot correct lines on an order with status '{order.status}' (only SUBMITTED permitted)",
            )

        target_line = next((l for l in order.lines if l.id == line_id), None)
        if not target_line:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Line item {line_id} not found on order {order_id}",
            )

        if new_qty_cases < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Case quantity must be at least 1",
            )

        old_qty = target_line.qty_cases

        # Build scheme wrapper using frozen line snapshots
        scheme_obj = None
        if target_line.scheme_type_snapshot:
            scheme_obj = SnapshotSchemeWrapper(
                scheme_type=target_line.scheme_type_snapshot,
                min_qty=target_line.min_qty_snapshot,
                free_qty=target_line.free_qty_snapshot,
                discount_pct=target_line.discount_pct_snapshot,
                description=target_line.description_snapshot,
            )

        calc_result = calculate_line_scheme(
            case_price=target_line.price_per_case_snapshot,
            paid_qty=new_qty_cases,
            scheme=scheme_obj,
        )

        # Update line item
        target_line.qty_cases = new_qty_cases
        target_line.free_cases = calc_result.free_qty_cases
        target_line.fulfilment_qty_cases = calc_result.fulfilment_qty_cases
        target_line.gross_amount = calc_result.gross_amount
        target_line.discount_amount = calc_result.discount_amount
        target_line.benefit_value = calc_result.benefit_value
        target_line.net_amount = calc_result.net_payable

        # Recalculate order totals
        total_gross = sum(l.gross_amount for l in order.lines)
        total_discount = sum(l.discount_amount for l in order.lines)
        total_benefit = sum(l.benefit_value for l in order.lines)
        total_net = sum(l.net_amount for l in order.lines)

        order.gross_total = total_gross
        order.discount_total = total_discount
        order.benefit_total = total_benefit
        order.scheme_total = total_benefit
        order.net_total = total_net
        order.total_cases = sum(l.qty_cases for l in order.lines)
        order.total_free_cases = sum(l.free_cases for l in order.lines)
        order.total_fulfilment_cases = sum(l.fulfilment_qty_cases for l in order.lines)
        order.reviewed_by = desk_user_id

        # Audit log entry
        audit_entry = OrderAuditLog(
            order_id=order.id,
            actor_type="order_desk",
            actor_id=desk_user_id,
            action="LINE_CORRECTED",
            from_status="SUBMITTED",
            to_status="SUBMITTED",
            note=reason,
            details={
                "line_id": str(line_id),
                "sku": target_line.sku_snapshot,
                "name": target_line.name_snapshot,
                "old_qty": old_qty,
                "new_qty": new_qty_cases,
                "new_free_cases": calc_result.free_qty_cases,
                "new_fulfilment_cases": calc_result.fulfilment_qty_cases,
                "reason": reason,
            },
        )
        db.add(audit_entry)
        db.commit()

        return cls.get_order_by_id(db, order.id)

    @classmethod
    def correct_line_product(
        cls,
        db: Session,
        order_id: uuid.UUID,
        line_id: uuid.UUID,
        new_product_id: uuid.UUID,
        reason: str,
        desk_user_id: uuid.UUID,
    ) -> Order:
        """
        Order Desk product correction on a SUBMITTED order:
        - Locks the order row using SELECT ... FOR UPDATE.
        - Loads active new product and its active scheme.
        - Re-snapshots product and scheme attributes on the order line.
        - Recalculates line pricing, free goods bonus, discount, and net payable.
        - Re-aggregates order totals.
        - Controlled Learning: Saves a retailer-specific alias (retailer_id, raw_fragment -> new_product_id, source='desk').
        - Records an immutable audit log entry.
        - Commits and returns updated order.
        """
        if not reason or not reason.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A non-empty correction reason is required",
            )

        order = db.execute(
            select(Order)
            .options(
                selectinload(Order.lines).selectinload(OrderLine.product),
                selectinload(Order.audit_logs),
                selectinload(Order.retailer),
            )
            .where(Order.id == order_id)
            .with_for_update()
        ).scalar_one_or_none()

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {order_id} not found",
            )

        if order.status != "SUBMITTED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot correct products on an order with status '{order.status}' (only SUBMITTED permitted)",
            )

        target_line = next((l for l in order.lines if l.id == line_id), None)
        if not target_line:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Line item {line_id} not found on order {order_id}",
            )

        new_product = db.execute(
            select(Product).where(Product.id == new_product_id, Product.is_active == True)
        ).scalar_one_or_none()

        if not new_product:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected replacement product not found or is inactive",
            )

        old_sku = target_line.sku_snapshot
        old_name = target_line.name_snapshot

        # Fetch active scheme for new product
        new_scheme = db.execute(
            select(Scheme).where(
                Scheme.product_id == new_product.id,
                Scheme.is_active == True,
            )
        ).scalars().first()

        new_case_price = (new_product.dealer_price_per_pack * new_product.case_qty).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )

        calc_result = calculate_line_scheme(
            case_price=new_case_price,
            paid_qty=target_line.qty_cases,
            scheme=new_scheme,
        )

        # Update line snapshots and values
        target_line.product_id = new_product.id
        target_line.sku_snapshot = new_product.sku
        target_line.name_snapshot = new_product.name
        target_line.pack_size_snapshot = new_product.pack_size or ""
        target_line.case_qty_snapshot = new_product.case_qty
        target_line.price_per_pack_snapshot = new_product.dealer_price_per_pack
        target_line.price_per_case_snapshot = new_case_price

        target_line.scheme_type_snapshot = new_scheme.scheme_type if new_scheme else None
        target_line.min_qty_snapshot = new_scheme.min_qty if new_scheme else None
        target_line.free_qty_snapshot = new_scheme.free_qty if new_scheme else None
        target_line.discount_pct_snapshot = new_scheme.discount_pct if new_scheme else None
        target_line.description_snapshot = new_scheme.description if new_scheme else None

        target_line.free_cases = calc_result.free_qty_cases
        target_line.fulfilment_qty_cases = calc_result.fulfilment_qty_cases
        target_line.unit_price = new_case_price
        target_line.gross_amount = calc_result.gross_amount
        target_line.discount_amount = calc_result.discount_amount
        target_line.benefit_value = calc_result.benefit_value
        target_line.net_amount = calc_result.net_payable

        # Recalculate order totals
        total_gross = sum(l.gross_amount for l in order.lines)
        total_discount = sum(l.discount_amount for l in order.lines)
        total_benefit = sum(l.benefit_value for l in order.lines)
        total_net = sum(l.net_amount for l in order.lines)

        order.gross_total = total_gross
        order.discount_total = total_discount
        order.benefit_total = total_benefit
        order.scheme_total = total_benefit
        order.net_total = total_net
        order.total_cases = sum(l.qty_cases for l in order.lines)
        order.total_free_cases = sum(l.free_cases for l in order.lines)
        order.total_fulfilment_cases = sum(l.fulfilment_qty_cases for l in order.lines)
        order.reviewed_by = desk_user_id

        # Controlled Desk Learning: Save retailer alias from raw_fragment
        if target_line.raw_fragment:
            clean_term = normalize_text(target_line.raw_fragment)
            if clean_term:
                existing_alias = db.execute(
                    select(RetailerAlias).where(
                        RetailerAlias.retailer_id == order.retailer_id,
                        RetailerAlias.raw_term == clean_term,
                    )
                ).scalar_one_or_none()

                if existing_alias:
                    existing_alias.product_id = new_product.id
                    existing_alias.source = "desk"
                else:
                    new_alias = RetailerAlias(
                        retailer_id=order.retailer_id,
                        product_id=new_product.id,
                        raw_term=clean_term,
                        source="desk",
                    )
                    db.add(new_alias)

        # Audit log entry
        audit_entry = OrderAuditLog(
            order_id=order.id,
            actor_type="order_desk",
            actor_id=desk_user_id,
            action="PRODUCT_CORRECTED",
            from_status="SUBMITTED",
            to_status="SUBMITTED",
            note=reason,
            details={
                "line_id": str(line_id),
                "old_sku": old_sku,
                "old_name": old_name,
                "new_sku": new_product.sku,
                "new_name": new_product.name,
                "reason": reason,
            },
        )
        db.add(audit_entry)
        db.commit()

        return cls.get_order_by_id(db, order.id)

    @classmethod
    def approve_order(
        cls,
        db: Session,
        order_id: uuid.UUID,
        desk_user_id: uuid.UUID,
        note: Optional[str] = None,
    ) -> Order:
        """
        Approve an order:
        - Locks the order row first using SELECT ... FOR UPDATE.
        - Re-checks that order status is SUBMITTED under the row lock.
        - Deterministically locks affected product rows in ascending order to prevent deadlocks.
        - Revalidates stock against physical fulfilment cases (including free scheme cases).
        - Atomically deducts inventory and transitions status to APPROVED.
        - On insufficient stock, rolls back atomically and raises HTTP 409 Conflict.
        """
        # 1. Lock the order row first
        order = db.execute(
            select(Order)
            .options(
                selectinload(Order.lines).selectinload(OrderLine.product),
                selectinload(Order.audit_logs),
                selectinload(Order.retailer),
            )
            .where(Order.id == order_id)
            .with_for_update()
        ).scalar_one_or_none()

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {order_id} not found",
            )

        if order.status != "SUBMITTED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Order cannot be approved: current status is '{order.status}' (expected SUBMITTED)",
            )

        # 2. Deterministic locking of product rows
        sorted_product_ids = sorted(list(set(line.product_id for line in order.lines)))
        locked_products = (
            db.execute(
                select(Product)
                .where(Product.id.in_(sorted_product_ids))
                .order_by(Product.id.asc())
                .with_for_update()
            )
            .scalars()
            .all()
        )
        product_map: Dict[uuid.UUID, Product] = {p.id: p for p in locked_products}

        # 3. Aggregate required fulfilment quantities per product
        needed_by_product: Dict[uuid.UUID, int] = {}
        for line in order.lines:
            needed_by_product[line.product_id] = (
                needed_by_product.get(line.product_id, 0) + line.fulfilment_qty_cases
            )

        # 4. Revalidate physical stock availability
        insufficient_items = []
        for pid, required_cases in needed_by_product.items():
            product = product_map.get(pid)
            if not product or product.stock_cases < required_cases:
                available = product.stock_cases if product else 0
                sku = product.sku if product else str(pid)
                name = product.name if product else "Unknown Product"
                insufficient_items.append({
                    "product_id": str(pid),
                    "sku": sku,
                    "name": name,
                    "required_cases": required_cases,
                    "available_cases": available,
                })

        if insufficient_items:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Insufficient inventory to approve order",
                    "insufficient_items": insufficient_items,
                },
            )

        # 5. Atomic inventory deduction
        deductions_detail = []
        for pid, required_cases in needed_by_product.items():
            product = product_map[pid]
            product.stock_cases -= required_cases
            deductions_detail.append({
                "sku": product.sku,
                "name": product.name,
                "deducted_cases": required_cases,
                "remaining_stock": product.stock_cases,
            })

        # 6. Transition status to APPROVED
        order.status = "APPROVED"
        order.reviewed_by = desk_user_id

        # 7. Audit log entry
        audit_entry = OrderAuditLog(
            order_id=order.id,
            actor_type="order_desk",
            actor_id=desk_user_id,
            action="APPROVED",
            from_status="SUBMITTED",
            to_status="APPROVED",
            note=note or "Order approved and stock deducted",
            details={
                "deductions": deductions_detail,
                "total_fulfilment_cases": order.total_fulfilment_cases,
            },
        )
        db.add(audit_entry)
        db.commit()

        return cls.get_order_by_id(db, order.id)

    @classmethod
    def reject_order(
        cls,
        db: Session,
        order_id: uuid.UUID,
        reason: str,
        desk_user_id: uuid.UUID,
    ) -> Order:
        """
        Reject an order:
        - Locks the order row first using SELECT ... FOR UPDATE.
        - Only permitted on orders in SUBMITTED status.
        - Requires a mandatory non-empty reason.
        - Transitions status to REJECTED.
        - Stock is NEVER deducted.
        """
        if not reason or not reason.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A non-empty rejection reason is required",
            )

        order = db.execute(
            select(Order)
            .options(
                selectinload(Order.lines).selectinload(OrderLine.product),
                selectinload(Order.audit_logs),
                selectinload(Order.retailer),
            )
            .where(Order.id == order_id)
            .with_for_update()
        ).scalar_one_or_none()

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {order_id} not found",
            )

        if order.status != "SUBMITTED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Order cannot be rejected: current status is '{order.status}' (expected SUBMITTED)",
            )

        order.status = "REJECTED"
        order.rejection_reason = reason.strip()
        order.reviewed_by = desk_user_id

        audit_entry = OrderAuditLog(
            order_id=order.id,
            actor_type="order_desk",
            actor_id=desk_user_id,
            action="REJECTED",
            from_status="SUBMITTED",
            to_status="REJECTED",
            note=reason.strip(),
            details={"rejection_reason": reason.strip()},
        )
        db.add(audit_entry)
        db.commit()

        return cls.get_order_by_id(db, order.id)

