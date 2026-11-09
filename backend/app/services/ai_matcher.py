"""
Product Matching Engine and Unit Normalizer for DukaanFlow (Phase 7).

Implements deterministic multi-tier product resolution:
- Tier 1: Retailer-specific exact alias lookup (isolated per retailer)
- Tier 2: Exact catalogue name, SKU, or descriptor match
- Tier 3: Substring / FMCG synonym match (single match -> medium confidence)
- Tier 4: Multiple candidates -> ambiguous with at most 2 alternatives
- Tier 5: Controlled fuzzy matching with qualitative confidence (high, medium, low)
- Unit normalization: recognizes case, peti, carton, piece, packet, nag
- Critical business safety: NEVER silently convert pieces into cases!
"""

import re
import difflib
from decimal import Decimal
from typing import Optional, List, Dict, Tuple, Any
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalogue import Product
from app.models.ai import RetailerAlias
from app.schemas.ai import DraftProductRead, ExtractedItem


# Explicit wholesale case synonyms
EXPLICIT_CASE_SYNONYMS = {
    "case",
    "cases",
    "peti",
    "petee",
    "पेटी",
    "carton",
    "cartons",
    "कार्टन",
}

# Ambiguous packaging synonyms: may refer to a wholesale case or a consumer box/tin
AMBIGUOUS_UNIT_SYNONYMS = {
    "box",
    "boxes",
    "dibba",
    "dibbe",
    "dabba",
    "dabbe",
    "डिब्बा",
    "डिब्बे",
    "डब्बा",
    "डब्बे",
}

# Consumer piece/packet unit synonyms
PIECE_SYNONYMS = {
    "piece",
    "pieces",
    "pcs",
    "pc",
    "पीस",
    "packet",
    "packets",
    "pkt",
    "pkts",
    "पैकेट",
    "नग",
    "nag",
}


def normalize_text(text: str) -> str:
    """Normalize text for consistent comparison: lowercase, remove punctuation, trim."""
    if not text:
        return ""
    # Replace punctuation with spaces
    cleaned = re.sub(r"[^\w\s\u0900-\u097F]", " ", text)
    # Collapse multiple whitespaces and lowercase
    return " ".join(cleaned.lower().split())


class AIMatcher:
    """Deterministic product matching engine."""

    @classmethod
    def normalize_unit(cls, unit_text: Optional[str]) -> Tuple[str, bool, Optional[str]]:
        """
        Normalize unit expression into standard category: 'case', 'piece', or 'unknown'.
        Returns: (normalized_unit, unit_unclear, clarification_reason)
        """
        if not unit_text or not unit_text.strip():
            return "unknown", True, "Unit not specified. Please verify number of cases."

        clean_unit = normalize_text(unit_text)
        words = clean_unit.split()

        # 1. Explicit wholesale case synonyms (unambiguous)
        for term in EXPLICIT_CASE_SYNONYMS:
            if term in words or clean_unit == term:
                return "case", False, None

        # 2. Generic 'box' and 'dibba' are ambiguous between wholesale case and inner consumer box
        for term in AMBIGUOUS_UNIT_SYNONYMS:
            if term in words or clean_unit == term:
                return (
                    "unknown",
                    True,
                    f"Unit '{unit_text}' is ambiguous between wholesale case and retail box. Please confirm full case quantity.",
                )

        # 3. Explicit piece/packet consumer units
        for term in PIECE_SYNONYMS:
            if term in words or clean_unit == term:
                return (
                    "piece",
                    True,
                    f"Ordered in pieces/packets ('{unit_text}'). Wholesale orders require full cases. Please clarify case quantity.",
                )

        # 4. Unrecognized unit expression
        return "unknown", True, f"Unrecognized unit '{unit_text}'. Please confirm number of cases."

    @classmethod
    def match_item(
        cls,
        db: Session,
        retailer_id: uuid.UUID,
        item: ExtractedItem,
        active_products: List[Product],
    ) -> Dict[str, Any]:
        """
        Resolve an extracted item against retailer aliases and active catalogue products.
        Returns dictionary with match_status, confidence, matched_product, alternatives, warnings, etc.
        """
        normalized_frag = normalize_text(item.raw_fragment)
        normalized_mention = normalize_text(item.product_mention)

        # 1. Normalize unit
        norm_unit, unit_unclear, unit_reason = cls.normalize_unit(item.unit_text)

        # 2. Check quantity
        qty_unclear = item.quantity_value is None or item.quantity_value <= 0
        qty_reason = "Order quantity is missing or invalid" if qty_unclear else None

        # Build product map by id and sku
        product_by_id = {p.id: p for p in active_products}

        # Step 1: Retailer-specific exact alias lookup (Tenant Isolated)
        alias = (
            db.execute(
                select(RetailerAlias).where(
                    RetailerAlias.retailer_id == retailer_id,
                    RetailerAlias.raw_term.in_([normalized_frag, normalized_mention]),
                )
            )
            .scalars()
            .first()
        )

        if alias and alias.product_id in product_by_id:
            matched = product_by_id[alias.product_id]
            clarifications = []
            if unit_reason:
                clarifications.append(unit_reason)
            if qty_reason:
                clarifications.append(qty_reason)

            warning = "OUT_OF_STOCK" if matched.stock_cases <= 0 else None

            return {
                "matched_product": matched,
                "matched_product_id": matched.id,
                "match_status": "confirmed",
                "confidence": "high",
                "normalized_unit": norm_unit,
                "clarification_reason": " — ".join(clarifications) if clarifications else None,
                "alternatives": [],
                "warning": warning,
            }

        # Step 2: Exact Catalogue SKU or Product Name Match
        for p in active_products:
            norm_name = normalize_text(p.name)
            norm_sku = normalize_text(p.sku)
            if normalized_mention in (norm_name, norm_sku) or normalized_frag in (norm_name, norm_sku):
                clarifications = []
                if unit_reason:
                    clarifications.append(unit_reason)
                if qty_reason:
                    clarifications.append(qty_reason)
                warning = "OUT_OF_STOCK" if p.stock_cases <= 0 else None

                return {
                    "matched_product": p,
                    "matched_product_id": p.id,
                    "match_status": "confirmed",
                    "confidence": "high",
                    "normalized_unit": norm_unit,
                    "clarification_reason": " — ".join(clarifications) if clarifications else None,
                    "alternatives": [],
                    "warning": warning,
                }

        # Step 3: Substring & FMCG Keyword Heuristics
        # FMCG common associations
        fmcg_keywords = {
            "biscuit": ["SKU-BS-075"],
            "glucose": ["SKU-BS-075"],
            "parle": ["SKU-BS-075"],
            "detergent": ["SKU-DT-1KG"],
            "washing": ["SKU-DT-1KG"],
            "surf": ["SKU-DT-1KG"],
            "powder": ["SKU-DT-1KG"],
            "tea": ["SKU-TE-250"],
            "chai": ["SKU-TE-250"],
            "patti": ["SKU-TE-250"],
        }

        matched_skus = set()
        mention_tokens = set(normalized_mention.split()) | set(normalized_frag.split())

        for token in mention_tokens:
            if token in fmcg_keywords:
                matched_skus.update(fmcg_keywords[token])

        # Also check substring match against all active products
        substring_candidates = []
        for p in active_products:
            norm_name = normalize_text(p.name)
            if normalized_mention and normalized_mention in norm_name:
                substring_candidates.append(p)
            elif any(t in norm_name.split() for t in mention_tokens if len(t) >= 4):
                substring_candidates.append(p)

        candidate_products = list({p.id: p for p in substring_candidates}.values())
        if not candidate_products and matched_skus:
            candidate_products = [p for p in active_products if p.sku in matched_skus]

        # Evaluate candidate count
        if len(candidate_products) == 1:
            p = candidate_products[0]
            clarifications = []
            if unit_reason:
                clarifications.append(unit_reason)
            if qty_reason:
                clarifications.append(qty_reason)
            warning = "OUT_OF_STOCK" if p.stock_cases <= 0 else None

            return {
                "matched_product": p,
                "matched_product_id": p.id,
                "match_status": "confirmed",
                "confidence": "medium",
                "normalized_unit": norm_unit,
                "clarification_reason": " — ".join(clarifications) if clarifications else None,
                "alternatives": [],
                "warning": warning,
            }

        elif len(candidate_products) >= 2:
            # Ambiguous: limit to top 2 alternatives
            alts = candidate_products[:2]
            return {
                "matched_product": None,
                "matched_product_id": None,
                "match_status": "ambiguous",
                "confidence": None,
                "normalized_unit": norm_unit,
                "clarification_reason": "Multiple matching catalogue products found. Please select one.",
                "alternatives": alts,
                "warning": None,
            }

        # Step 4: Fuzzy Matching
        best_match = None
        best_score = 0.0

        for p in active_products:
            norm_name = normalize_text(p.name)
            score = difflib.SequenceMatcher(None, normalized_mention, norm_name).ratio()
            if score > best_score:
                best_score = score
                best_match = p

        if best_match and best_score >= 0.90:
            clarifications = []
            if unit_reason:
                clarifications.append(unit_reason)
            if qty_reason:
                clarifications.append(qty_reason)
            warning = "OUT_OF_STOCK" if best_match.stock_cases <= 0 else None

            return {
                "matched_product": best_match,
                "matched_product_id": best_match.id,
                "match_status": "confirmed",
                "confidence": "high",
                "normalized_unit": norm_unit,
                "clarification_reason": " — ".join(clarifications) if clarifications else None,
                "alternatives": [],
                "warning": warning,
            }
        elif best_match and best_score >= 0.40:
            # Below 0.90 similarity is treated as ambiguous — never silently promote weak match to confirmed
            alts = [best_match]
            return {
                "matched_product": None,
                "matched_product_id": None,
                "match_status": "ambiguous",
                "confidence": "low",
                "normalized_unit": norm_unit,
                "clarification_reason": "Close name match found, but not exact. Please confirm product selection.",
                "alternatives": alts,
                "warning": None,
            }

        # Step 5: Unmatched
        return {
            "matched_product": None,
            "matched_product_id": None,
            "match_status": "unmatched",
            "confidence": None,
            "normalized_unit": norm_unit,
            "clarification_reason": "No reliable catalogue match found for this item.",
            "alternatives": [],
            "warning": None,
        }

    @staticmethod
    def to_draft_product_read(p: Product) -> DraftProductRead:
        """Helper to convert Product model to DraftProductRead schema."""
        stock_status = "in_stock" if p.stock_cases > 0 else "out_of_stock"
        dealer_price_per_case = (p.dealer_price_per_pack * p.case_qty).quantize(Decimal("0.01"))
        return DraftProductRead(
            id=p.id,
            sku=p.sku,
            name=p.name,
            pack_size=p.pack_size or "",
            case_qty=p.case_qty,
            dealer_price_per_pack=p.dealer_price_per_pack,
            dealer_price_per_case=dealer_price_per_case,
            stock_cases=p.stock_cases,
            stock_status=stock_status,
            category=p.category,
        )

