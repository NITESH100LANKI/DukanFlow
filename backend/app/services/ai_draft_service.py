"""
AI Order Draft Service for DukaanFlow (Phase 7).

Manages the lifecycle of AI order drafts:
- Extraction and multi-tier matching into persistent drafts
- Tenant isolation (retailers can only view and mutate their own drafts)
- Line resolution (ambiguity resolution, unit clarification, quantity edits)
- Automatic learning of retailer-specific aliases upon human confirmation
- Atomic confirmation into the existing Shopping Cart (CartService)
- Strict business rule: AI drafts NEVER directly create Orders or deduct stock!
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.catalogue import Product
from app.models.ai import RetailerAlias, AIOrderDraft, AIOrderDraftLine
from app.services.gemini_service import GeminiService
from app.services.ai_matcher import AIMatcher, normalize_text
from app.services.cart import CartService
from app.schemas.ai import (
    AIOrderDraftLineUpdate,
    DraftProductRead,
    AIDraftConfirmResponse,
)


class AIDraftService:

    @classmethod
    def create_draft_from_message(
        cls,
        db: Session,
        retailer_id: uuid.UUID,
        raw_text: str,
    ) -> AIOrderDraft:
        """
        Parses retailer message with Gemini and creates a persistent AIOrderDraft.
        Matches items against retailer aliases and active catalogue.
        """
        if not raw_text or not raw_text.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Order text cannot be empty",
            )

        # 1. Structured extraction via Gemini (with fallback)
        extraction_res = GeminiService.extract_from_text(raw_text)

        # 2. Fetch active catalogue products
        active_products = (
            db.execute(select(Product).where(Product.is_active == True))
            .scalars()
            .all()
        )

        parser_used = getattr(extraction_res, "parser_used", "gemini")
        draft = AIOrderDraft(
            retailer_id=retailer_id,
            original_message=raw_text.strip(),
            status="DRAFT",
            parser_used=parser_used,
            metadata_json={
                "parser_used": parser_used,
                "model": settings.GEMINI_MODEL,
                "unparsed_text": extraction_res.unparsed_text,
            },
        )
        db.add(draft)
        db.flush()  # allocate draft.id

        # 3. Match each extracted item (bounded to max 30 items)
        for item in extraction_res.items[:30]:
            match_outcome = AIMatcher.match_item(
                db=db,
                retailer_id=retailer_id,
                item=item,
                active_products=active_products,
            )

            matched_prod = match_outcome.get("matched_product")
            matched_prod_id = matched_prod.id if matched_prod else None
            match_status = match_outcome.get("match_status", "unmatched")
            norm_unit = match_outcome.get("normalized_unit", "unknown")
            clarification = match_outcome.get("clarification_reason")

            # Convert alternatives to json serializable dicts
            alts_raw = match_outcome.get("alternatives", [])
            alts_json = [
                AIMatcher.to_draft_product_read(p).model_dump(mode="json")
                for p in alts_raw
            ]

            # Initial auto-resolution if confirmed and unit is case
            is_valid_case = norm_unit == "case" and (item.quantity_value or 0) > 0
            is_auto_confirmed = (
                match_status == "confirmed"
                and matched_prod_id is not None
                and is_valid_case
                and (matched_prod.stock_cases > 0 if matched_prod else False)
            )

            resolved_prod_id = matched_prod_id if is_auto_confirmed else None
            resolved_qty = item.quantity_value if is_auto_confirmed else None

            line = AIOrderDraftLine(
                draft_id=draft.id,
                raw_fragment=item.raw_fragment,
                product_mention=item.product_mention,
                quantity_value=item.quantity_value,
                unit_text=item.unit_text,
                normalized_unit=norm_unit,
                matched_product_id=matched_prod_id,
                match_status=match_status,
                confidence=match_outcome.get("confidence"),
                clarification_reason=clarification,
                alternatives=alts_json,
                warning=match_outcome.get("warning"),
                resolved_product_id=resolved_prod_id,
                resolved_qty_cases=resolved_qty,
                is_confirmed=is_auto_confirmed,
            )
            db.add(line)

        db.commit()
        return cls.get_draft_by_id(db, retailer_id, draft.id)

    @classmethod
    def get_draft_by_id(
        cls,
        db: Session,
        retailer_id: uuid.UUID,
        draft_id: uuid.UUID,
    ) -> AIOrderDraft:
        """Fetch draft enforcing retailer tenant boundary."""
        stmt = (
            select(AIOrderDraft)
            .options(
                selectinload(AIOrderDraft.lines).selectinload(
                    AIOrderDraftLine.matched_product
                ),
                selectinload(AIOrderDraft.lines).selectinload(
                    AIOrderDraftLine.resolved_product
                ),
            )
            .where(AIOrderDraft.id == draft_id)
        )
        draft = db.execute(stmt).scalar_one_or_none()

        if not draft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"AI order draft {draft_id} not found",
            )

        if draft.retailer_id != retailer_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Draft not found or does not belong to you",
            )

        return draft

    @classmethod
    def list_drafts(
        cls,
        db: Session,
        retailer_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Paginated list of AI order drafts for retailer."""
        if page < 1 or page_size < 1:
            raise HTTPException(status_code=400, detail="Invalid pagination parameters")

        count_stmt = select(func.count(AIOrderDraft.id)).where(
            AIOrderDraft.retailer_id == retailer_id
        )
        total = db.execute(count_stmt).scalar() or 0

        stmt = (
            select(AIOrderDraft)
            .options(selectinload(AIOrderDraft.lines))
            .where(AIOrderDraft.retailer_id == retailer_id)
            .order_by(desc(AIOrderDraft.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        drafts = db.execute(stmt).scalars().all()
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        return {
            "items": drafts,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    @classmethod
    def update_draft_line(
        cls,
        db: Session,
        retailer_id: uuid.UUID,
        draft_id: uuid.UUID,
        line_id: uuid.UUID,
        update_data: AIOrderDraftLineUpdate,
    ) -> AIOrderDraft:
        """
        Retailer resolves ambiguity, clarifies unit, or edits quantity.
        Saves learned retailer alias if product was explicitly chosen.
        """
        draft = cls.get_draft_by_id(db, retailer_id, draft_id)

        if draft.status != "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot edit draft lines in status '{draft.status}'",
            )

        line = next((l for l in draft.lines if l.id == line_id), None)
        if not line:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Line item {line_id} not found on draft {draft_id}",
            )

        # 1. Update product selection if supplied
        if update_data.resolved_product_id:
            prod = db.execute(
                select(Product).where(
                    Product.id == update_data.resolved_product_id,
                    Product.is_active == True,
                )
            ).scalar_one_or_none()

            if not prod:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Selected product not found or is inactive",
                )

            line.resolved_product_id = prod.id
            line.match_status = "confirmed"
            line.confidence = "high"
            line.clarification_reason = None
            line.warning = "OUT_OF_STOCK" if prod.stock_cases <= 0 else None

            # Controlled Retailer Alias Learning
            raw_phrase = normalize_text(line.product_mention or line.raw_fragment)
            if raw_phrase:
                existing_alias = db.execute(
                    select(RetailerAlias).where(
                        RetailerAlias.retailer_id == retailer_id,
                        RetailerAlias.raw_term == raw_phrase,
                    )
                ).scalar_one_or_none()

                if existing_alias:
                    existing_alias.product_id = prod.id
                    existing_alias.source = "retailer"
                else:
                    new_alias = RetailerAlias(
                        retailer_id=retailer_id,
                        product_id=prod.id,
                        raw_term=raw_phrase,
                        source="retailer",
                    )
                    db.add(new_alias)

        # 2. Update quantity if supplied
        if update_data.resolved_qty_cases is not None:
            if update_data.resolved_qty_cases < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Quantity in cases must be at least 1",
                )
            line.resolved_qty_cases = update_data.resolved_qty_cases

        # 3. Update normalized unit if supplied
        if update_data.normalized_unit:
            line.normalized_unit = update_data.normalized_unit

        # Evaluate final confirmation eligibility of this line
        chosen_pid = line.resolved_product_id or line.matched_product_id
        chosen_qty = line.resolved_qty_cases or line.quantity_value

        prod_obj = None
        if chosen_pid:
            prod_obj = db.execute(
                select(Product).where(Product.id == chosen_pid)
            ).scalar_one_or_none()

        line.is_confirmed = (
            chosen_pid is not None
            and prod_obj is not None
            and prod_obj.is_active
            and prod_obj.stock_cases > 0
            and line.normalized_unit == "case"
            and chosen_qty is not None
            and chosen_qty > 0
        )

        db.commit()
        return cls.get_draft_by_id(db, retailer_id, draft.id)

    @classmethod
    def delete_draft_line(
        cls,
        db: Session,
        retailer_id: uuid.UUID,
        draft_id: uuid.UUID,
        line_id: uuid.UUID,
    ) -> AIOrderDraft:
        """Retailer discards an unintended extracted item."""
        draft = cls.get_draft_by_id(db, retailer_id, draft_id)

        if draft.status != "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot remove items from draft in status '{draft.status}'",
            )

        line = next((l for l in draft.lines if l.id == line_id), None)
        if not line:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Line item {line_id} not found on draft {draft_id}",
            )

        db.delete(line)
        db.commit()
        return cls.get_draft_by_id(db, retailer_id, draft.id)

    @classmethod
    def confirm_draft_to_cart(
        cls,
        db: Session,
        retailer_id: uuid.UUID,
        draft_id: uuid.UUID,
    ) -> AIDraftConfirmResponse:
        """
        Atomically transfers all confirmed items from an AI draft into the retailer's cart.
        - Validates all ambiguities are resolved.
        - Validates stock and catalogue status on all items.
        - Calls CartService atomically.
        - Does NOT create an order or deduct stock!
        - Marks draft status as CONFIRMED.
        """
        draft = cls.get_draft_by_id(db, retailer_id, draft_id)

        if draft.status == "CONFIRMED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Draft has already been confirmed and added to cart",
            )

        if draft.status != "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot confirm draft with status '{draft.status}'",
            )

        if not draft.lines:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot confirm an empty draft with no line items",
            )

        # 1. Validation of all lines before modifying cart
        lines_to_add = []
        for line in draft.lines:
            target_pid = line.resolved_product_id or line.matched_product_id
            if not target_pid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot confirm draft: line item '{line.raw_fragment}' has not been resolved to a product",
                )

            if line.normalized_unit != "case":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot confirm draft: line item '{line.raw_fragment}' has unresolved unit '{line.normalized_unit}'. Please clarify case quantity.",
                )

            cases = line.resolved_qty_cases or line.quantity_value
            if not cases or cases < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot confirm draft: line item '{line.raw_fragment}' has invalid quantity",
                )

            product = db.execute(
                select(Product).where(Product.id == target_pid)
            ).scalar_one_or_none()

            if not product or not product.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot confirm draft: product for line '{line.raw_fragment}' is inactive or unavailable",
                )

            if product.stock_cases <= 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot confirm draft: '{product.name}' is out of stock",
                )

            lines_to_add.append((product, cases))

        # 2. Atomically add items to existing retailer cart and mark draft confirmed
        try:
            for product, cases in lines_to_add:
                CartService.add_or_update_line(
                    db=db,
                    retailer_id=retailer_id,
                    product_id=product.id,
                    qty_cases=cases,
                    auto_commit=False,
                )

            # 3. Mark draft as CONFIRMED
            draft.status = "CONFIRMED"
            draft.confirmed_at = datetime.now(timezone.utc)
            db.commit()
        except Exception:
            db.rollback()
            raise

        # 4. Fetch updated cart summary
        cart_data = CartService.get_cart_data(db, retailer_id)
        summary = cart_data.get("summary") or {}

        return AIDraftConfirmResponse(
            draft_id=draft.id,
            status="CONFIRMED",
            confirmed_items_count=len(lines_to_add),
            cart_total_cases=summary.get("total_cases_paid", 0),
            cart_net_total=summary.get("net_total", Decimal("0.00")),
            message=f"Successfully added {len(lines_to_add)} item(s) to your cart",
        )
