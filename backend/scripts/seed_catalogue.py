"""
Seed realistic sample product catalogue and schemes:
1. SKU-BS-075: Glucose biscuit 75 g (Buy 10 Get 1 Free)
2. SKU-DT-1KG: Detergent powder 1 kg (3% discount on 5+ cases)
3. SKU-TE-250: Tea leaf 250 g (Out of Stock, no scheme)

IDEMPOTENT: Safe to run multiple times without creating duplicates.
"""

import sys
import os
from decimal import Decimal
from datetime import date, timedelta

# Ensure backend root is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from app.core.database import SessionLocal
from app.models.catalogue import Product, Scheme


def seed_catalogue() -> None:
    db = SessionLocal()
    today = date.today()
    valid_from = today - timedelta(days=30)
    valid_to = today + timedelta(days=365)

    sample_products = [
        {
            "sku": "SKU-BS-075",
            "name": "Glucose biscuit 75 g",
            "description": "Popular everyday energy glucose biscuits in tamper-proof moisture barrier wrap.",
            "pack_size": "75g",
            "case_qty": 96,
            "dealer_price_per_pack": Decimal("8.10"),
            "price_unit": "per_pack",
            "gst_rate_pct": None,  # GST unspecified per project requirements
            "stock_cases": 340,
            "category": "Biscuits",
            "is_active": True,
            "scheme": {
                "scheme_type": "BUY_N_GET_M_FREE",
                "min_qty": 10,
                "free_qty": 1,
                "discount_pct": None,
                "valid_from": valid_from,
                "valid_to": valid_to,
                "is_active": True,
            },
        },
        {
            "sku": "SKU-DT-1KG",
            "name": "Detergent powder 1 kg",
            "description": "High-foaming active stain-removal detergent powder for hand and top-load wash.",
            "pack_size": "1kg",
            "case_qty": 20,
            "dealer_price_per_pack": Decimal("101.50"),
            "price_unit": "per_pack",
            "gst_rate_pct": None,
            "stock_cases": 85,
            "category": "Detergents",
            "is_active": True,
            "scheme": {
                "scheme_type": "DISCOUNT_ON_MIN_QTY",
                "min_qty": 5,
                "free_qty": None,
                "discount_pct": Decimal("3.00"),
                "valid_from": valid_from,
                "valid_to": valid_to,
                "is_active": True,
            },
        },
        {
            "sku": "SKU-TE-250",
            "name": "Tea leaf 250 g",
            "description": "Premium CTC black tea blend offering robust colour and rich malty aroma.",
            "pack_size": "250g",
            "case_qty": 40,
            "dealer_price_per_pack": Decimal("118.00"),
            "price_unit": "per_pack",
            "gst_rate_pct": None,
            "stock_cases": 0,  # Out of stock
            "category": "Beverages",
            "is_active": True,
            "scheme": None,
        },
    ]

    try:
        print("[SEED] Seeding catalogue products and schemes...")
        for item in sample_products:
            sku = item["sku"]
            scheme_data = item.pop("scheme")

            stmt = select(Product).where(Product.sku == sku)
            product = db.execute(stmt).scalar_one_or_none()

            if product:
                print(f"  -> Updating existing product {sku}...")
                for k, v in item.items():
                    setattr(product, k, v)
            else:
                print(f"  -> Creating new product {sku} ({item['name']})...")
                product = Product(**item)
                db.add(product)
                db.flush()

            # Handle Schemes idempotently
            if scheme_data:
                scheme_stmt = select(Scheme).where(
                    Scheme.product_id == product.id,
                    Scheme.is_active.is_(True),
                )
                existing_scheme = db.execute(scheme_stmt).scalar_one_or_none()

                if existing_scheme:
                    for sk, sv in scheme_data.items():
                        setattr(existing_scheme, sk, sv)
                else:
                    new_scheme = Scheme(product_id=product.id, **scheme_data)
                    db.add(new_scheme)
            else:
                # If no scheme, ensure any existing active scheme for this product is deactivated
                active_schemes = db.execute(
                    select(Scheme).where(Scheme.product_id == product.id)
                ).scalars().all()
                for s in active_schemes:
                    s.is_active = False

        db.commit()
        print("[SUCCESS] Catalogue seed complete.")
        for p in db.execute(select(Product)).scalars().all():
            case_price = p.dealer_price_per_case
            print(f"   * {p.sku}: {p.name} | Pack: Rs {p.dealer_price_per_pack} | Case ({p.case_qty} packs): Rs {case_price} | Stock: {p.stock_cases} cases")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Seeding failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_catalogue()

