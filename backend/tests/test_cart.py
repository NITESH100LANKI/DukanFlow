"""
Integration tests for Shopping Cart APIs and Scheme Engine integration.

Covers all 13 required test cases:
1. Empty cart creation.
2. Add product.
3. Update quantity.
4. Remove product.
5. Clear cart.
6. Persistent cart retrieval.
7. Biscuit free-goods calculation (Buy 10 Get 1).
8. Detergent discount calculation (3% on 5+).
9. Tea out-of-stock blocking.
10. Cart stock validation uses fulfilment quantity (10 cases + 1 free requires 11 stock).
11. Retailer cart isolation.
12. Order Desk access denied.
13. Backend recalculates totals after every mutation.
"""

import uuid
from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.auth import Retailer, OrderDeskUser
from app.models.catalogue import Product, Scheme
from app.models.cart import Cart, CartLine


client = TestClient(app)


@pytest.fixture(scope="module")
def retailer_a_token():
    """Provides a valid JWT token for Retailer A (9876543210)."""
    db = SessionLocal()
    try:
        retailer = db.execute(
            select(Retailer).where(Retailer.mobile == "9876543210")
        ).scalar_one_or_none()
        if not retailer:
            retailer = Retailer(
                mobile="9876543210",
                name="Gupta Kirana Store",
                address="Lordganj, Jabalpur",
                is_active=True,
            )
            db.add(retailer)
            db.commit()
            db.refresh(retailer)
        token, _, _ = create_access_token(str(retailer.id), role="retailer")
        return token
    finally:
        db.close()


@pytest.fixture(scope="module")
def retailer_b_token():
    """Provides a valid JWT token for a distinct Retailer B."""
    db = SessionLocal()
    try:
        retailer = db.execute(
            select(Retailer).where(Retailer.mobile == "9826112233")
        ).scalar_one_or_none()
        if not retailer:
            retailer = Retailer(
                mobile="9826112233",
                name="Agrawal Supermarket",
                address="Wright Town, Jabalpur",
                is_active=True,
            )
            db.add(retailer)
            db.commit()
            db.refresh(retailer)
        token, _, _ = create_access_token(str(retailer.id), role="retailer")
        return token
    finally:
        db.close()


@pytest.fixture(scope="module")
def desk_token():
    """Provides an Order Desk token."""
    db = SessionLocal()
    try:
        desk = db.execute(
            select(OrderDeskUser).where(OrderDeskUser.email == "desk@dukaanflow.in")
        ).scalar_one_or_none()
        if not desk:
            desk = OrderDeskUser(
                email="desk@dukaanflow.in",
                full_name="Rajesh Sharma",
                password_hash="testhash",
                is_active=True,
            )
            db.add(desk)
            db.commit()
            db.refresh(desk)
        token, _, _ = create_access_token(str(desk.id), role="order_desk")
        return token
    finally:
        db.close()


@pytest.fixture(scope="module")
def seeded_products():
    """Fetches seeded products dictionary keyed by SKU."""
    db = SessionLocal()
    try:
        prods = db.execute(select(Product)).scalars().all()
        return {p.sku: p for p in prods}
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clean_carts():
    """Cleans up cart lines before each test run."""
    db = SessionLocal()
    try:
        db.query(CartLine).delete()
        db.commit()
    finally:
        db.close()


# 1. Empty cart creation
def test_empty_cart_creation(retailer_a_token):
    res = client.get("/api/v1/cart", headers={"Authorization": f"Bearer {retailer_a_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "lines" in data
    assert len(data["lines"]) == 0
    assert data["summary"]["item_count"] == 0
    assert Decimal(str(data["summary"]["gross_total"])) == Decimal("0.00")
    assert Decimal(str(data["summary"]["net_total"])) == Decimal("0.00")


# 2. Add product
def test_add_product_to_cart(retailer_a_token, seeded_products):
    biscuit = seeded_products["SKU-BS-075"]
    res = client.post(
        "/api/v1/cart/lines",
        headers={"Authorization": f"Bearer {retailer_a_token}"},
        json={"product_id": str(biscuit.id), "qty_cases": 2},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["lines"]) == 1
    line = data["lines"][0]
    assert line["sku"] == "SKU-BS-075"
    assert line["qty_cases"] == 2
    assert Decimal(str(line["gross_line_total"])) == Decimal("1555.20")  # 777.60 * 2
    assert Decimal(str(line["net_line_total"])) == Decimal("1555.20")


# 3. Update quantity
def test_update_cart_line_quantity(retailer_a_token, seeded_products):
    biscuit = seeded_products["SKU-BS-075"]
    add_res = client.post(
        "/api/v1/cart/lines",
        headers={"Authorization": f"Bearer {retailer_a_token}"},
        json={"product_id": str(biscuit.id), "qty_cases": 2},
    )
    line_id = add_res.json()["lines"][0]["id"]

    patch_res = client.patch(
        f"/api/v1/cart/lines/{line_id}",
        headers={"Authorization": f"Bearer {retailer_a_token}"},
        json={"qty_cases": 4},
    )
    assert patch_res.status_code == 200
    updated_line = patch_res.json()["lines"][0]
    assert updated_line["qty_cases"] == 4
    assert Decimal(str(updated_line["gross_line_total"])) == Decimal("3110.40")  # 777.60 * 4


# 4. Remove product
def test_remove_product_line(retailer_a_token, seeded_products):
    biscuit = seeded_products["SKU-BS-075"]
    add_res = client.post(
        "/api/v1/cart/lines",
        headers={"Authorization": f"Bearer {retailer_a_token}"},
        json={"product_id": str(biscuit.id), "qty_cases": 2},
    )
    line_id = add_res.json()["lines"][0]["id"]

    del_res = client.delete(
        f"/api/v1/cart/lines/{line_id}",
        headers={"Authorization": f"Bearer {retailer_a_token}"},
    )
    assert del_res.status_code == 200
    assert len(del_res.json()["lines"]) == 0
    assert del_res.json()["summary"]["item_count"] == 0


# 5. Clear cart
def test_clear_cart(retailer_a_token, seeded_products):
    biscuit = seeded_products["SKU-BS-075"]
    detergent = seeded_products["SKU-DT-1KG"]

    client.post(
        "/api/v1/cart/lines",
        headers={"Authorization": f"Bearer {retailer_a_token}"},
        json={"product_id": str(biscuit.id), "qty_cases": 2},
    )
    client.post(
        "/api/v1/cart/lines",
        headers={"Authorization": f"Bearer {retailer_a_token}"},
        json={"product_id": str(detergent.id), "qty_cases": 1},
    )

    clear_res = client.delete("/api/v1/cart", headers={"Authorization": f"Bearer {retailer_a_token}"})
    assert clear_res.status_code == 200
    assert len(clear_res.json()["lines"]) == 0
    assert clear_res.json()["summary"]["net_total"] == "0.00"


# 6. Persistent cart retrieval
def test_persistent_cart_retrieval(retailer_a_token, seeded_products):
    biscuit = seeded_products["SKU-BS-075"]
    client.post(
        "/api/v1/cart/lines",
        headers={"Authorization": f"Bearer {retailer_a_token}"},
        json={"product_id": str(biscuit.id), "qty_cases": 3},
    )

    # In a separate GET request, lines and totals must be intact
    res = client.get("/api/v1/cart", headers={"Authorization": f"Bearer {retailer_a_token}"})
    assert res.status_code == 200
    assert len(res.json()["lines"]) == 1
    assert res.json()["lines"][0]["qty_cases"] == 3


# 7. Biscuit free-goods calculation (Buy 10 Get 1)
def test_biscuit_free_goods_scheme(retailer_a_token, seeded_products):
    biscuit = seeded_products["SKU-BS-075"]
    res = client.post(
        "/api/v1/cart/lines",
        headers={"Authorization": f"Bearer {retailer_a_token}"},
        json={"product_id": str(biscuit.id), "qty_cases": 10},
    )
    assert res.status_code == 200
    line = res.json()["lines"][0]
    assert line["qty_cases"] == 10
    assert line["qty_free"] == 1
    assert line["qty_fulfilment"] == 11
    assert Decimal(str(line["gross_line_total"])) == Decimal("7776.00")
    assert Decimal(str(line["discount_amount"])) == Decimal("0.00")  # Free goods do NOT discount payable
    assert Decimal(str(line["benefit_value"])) == Decimal("777.60")
    assert Decimal(str(line["net_line_total"])) == Decimal("7776.00")
    assert line["scheme_applied"]["scheme_type"] == "BUY_N_GET_M_FREE"


# 8. Detergent discount calculation (3% on 5+)
def test_detergent_discount_scheme(retailer_a_token, seeded_products):
    detergent = seeded_products["SKU-DT-1KG"]
    res = client.post(
        "/api/v1/cart/lines",
        headers={"Authorization": f"Bearer {retailer_a_token}"},
        json={"product_id": str(detergent.id), "qty_cases": 5},
    )
    assert res.status_code == 200
    line = res.json()["lines"][0]
    assert line["qty_cases"] == 5
    assert line["qty_free"] == 0
    assert Decimal(str(line["gross_line_total"])) == Decimal("10150.00")
    assert Decimal(str(line["discount_amount"])) == Decimal("304.50")
    assert Decimal(str(line["benefit_value"])) == Decimal("304.50")
    assert Decimal(str(line["net_line_total"])) == Decimal("9845.50")
    assert line["scheme_applied"]["scheme_type"] == "DISCOUNT_ON_MIN_QTY"


# 9. Tea out-of-stock blocking
def test_tea_out_of_stock_blocking(retailer_a_token, seeded_products):
    tea = seeded_products["SKU-TE-250"]
    res = client.post(
        "/api/v1/cart/lines",
        headers={"Authorization": f"Bearer {retailer_a_token}"},
        json={"product_id": str(tea.id), "qty_cases": 1},
    )
    assert res.status_code == 422
    assert "out of stock" in res.json()["detail"].lower()


# 10. Cart stock validation uses fulfilment quantity
def test_stock_validation_uses_fulfilment_quantity(retailer_a_token):
    """
    If a product has 10 cases in inventory and Buy 10 Get 1 applies:
    Purchasing 10 paid cases requires 11 fulfilment cases -> must be rejected with 409!
    """
    db = SessionLocal()
    test_sku = f"SKU-LIM-{uuid.uuid4().hex[:6].upper()}"
    try:
        prod = Product(
            sku=test_sku,
            name="Limited Stock Biscuit",
            case_qty=10,
            dealer_price_per_pack=Decimal("10.00"),
            stock_cases=10,  # Exactly 10 cases in stock
            is_active=True,
        )
        db.add(prod)
        db.flush()

        scheme = Scheme(
            product_id=prod.id,
            scheme_type="BUY_N_GET_M_FREE",
            min_qty=10,
            free_qty=1,
            valid_from=date.today(),
            valid_to=date.today(),
            is_active=True,
        )
        db.add(scheme)
        db.commit()

        # Attempt to order 10 cases (which earns 1 free -> requires 11 cases)
        res = client.post(
            "/api/v1/cart/lines",
            headers={"Authorization": f"Bearer {retailer_a_token}"},
            json={"product_id": str(prod.id), "qty_cases": 10},
        )
        assert res.status_code == 409
        assert "requires 11 fulfilment cases" in res.json()["detail"]
    finally:
        p = db.execute(select(Product).where(Product.sku == test_sku)).scalar_one_or_none()
        if p:
            db.delete(p)
            db.commit()
        db.close()


# 11. Retailer cart isolation
def test_retailer_cart_isolation(retailer_a_token, retailer_b_token, seeded_products):
    biscuit = seeded_products["SKU-BS-075"]

    # Retailer A adds 2 biscuit cases
    client.post(
        "/api/v1/cart/lines",
        headers={"Authorization": f"Bearer {retailer_a_token}"},
        json={"product_id": str(biscuit.id), "qty_cases": 2},
    )

    # Retailer B checks their cart -> must be completely empty!
    res_b = client.get("/api/v1/cart", headers={"Authorization": f"Bearer {retailer_b_token}"})
    assert res_b.status_code == 200
    assert len(res_b.json()["lines"]) == 0
    assert res_b.json()["summary"]["item_count"] == 0


# 12. Order Desk access denied
def test_order_desk_cart_access_denied(desk_token):
    res = client.get("/api/v1/cart", headers={"Authorization": f"Bearer {desk_token}"})
    assert res.status_code == 403


# 13. Backend recalculates totals after every mutation
def test_recalculates_totals_after_mutations(retailer_a_token, seeded_products):
    biscuit = seeded_products["SKU-BS-075"]
    detergent = seeded_products["SKU-DT-1KG"]

    # Step 1: Add 10 biscuit cases (₹7,776.00 gross, ₹777.60 benefit, ₹7,776.00 net)
    res1 = client.post(
        "/api/v1/cart/lines",
        headers={"Authorization": f"Bearer {retailer_a_token}"},
        json={"product_id": str(biscuit.id), "qty_cases": 10},
    )
    s1 = res1.json()["summary"]
    assert Decimal(str(s1["gross_total"])) == Decimal("7776.00")
    assert Decimal(str(s1["net_total"])) == Decimal("7776.00")
    assert Decimal(str(s1["total_benefit_value"])) == Decimal("777.60")

    # Step 2: Add 5 detergent cases (₹10,150.00 gross, ₹304.50 discount, ₹9,845.50 net)
    res2 = client.post(
        "/api/v1/cart/lines",
        headers={"Authorization": f"Bearer {retailer_a_token}"},
        json={"product_id": str(detergent.id), "qty_cases": 5},
    )
    s2 = res2.json()["summary"]
    assert Decimal(str(s2["gross_total"])) == Decimal("17926.00")  # 7776 + 10150
    assert Decimal(str(s2["total_discount"])) == Decimal("304.50")
    assert Decimal(str(s2["total_benefit_value"])) == Decimal("1082.10")  # 777.60 + 304.50
    assert Decimal(str(s2["net_total"])) == Decimal("17621.50")  # 17926.00 - 304.50
    assert s2["item_count"] == 2
    assert s2["total_cases_paid"] == 15
    assert s2["total_cases_free"] == 1
    assert s2["total_cases_fulfilment"] == 16
