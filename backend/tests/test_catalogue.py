"""
Unit and integration tests for Phase 4: Product Catalogue and Schemes.

Tests cover:
- Authentication & Role authorization
- Product retrieval and details
- SKU uniqueness constraint
- Full search functionality (name, SKU, description)
- Category filter
- In-stock filter & out-of-stock badge calculation
- Active vs expired scheme filtering
- Accurate Decimal monetary serialization (pack price & derived case price)
- Category listing endpoint
- 404 on missing SKU
"""

import uuid
from decimal import Decimal
from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.auth import Retailer, OrderDeskUser
from app.models.catalogue import Product, Scheme


client = TestClient(app)


@pytest.fixture(scope="module")
def seeded_retailer_token():
    """Provides a valid JWT token for a seeded test retailer."""
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
def seeded_desk_token():
    """Provides a valid JWT token for a seeded test Order Desk staff member."""
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


def test_catalogue_requires_authentication():
    """Unauthenticated users must not see wholesale product listings or prices."""
    response = client.get("/api/v1/catalogue/products")
    assert response.status_code == 401
    assert "Authentication required" in response.json()["detail"]

    response_sku = client.get("/api/v1/catalogue/products/SKU-BS-075")
    assert response_sku.status_code == 401


def test_catalogue_accessible_by_both_retailer_and_desk(seeded_retailer_token, seeded_desk_token):
    """Both retailers and order desk operators can view the catalogue."""
    # Retailer access
    res_retailer = client.get(
        "/api/v1/catalogue/products",
        headers={"Authorization": f"Bearer {seeded_retailer_token}"},
    )
    assert res_retailer.status_code == 200
    data_retailer = res_retailer.json()
    assert "items" in data_retailer
    assert data_retailer["total"] >= 3

    # Order Desk access
    res_desk = client.get(
        "/api/v1/catalogue/products",
        headers={"Authorization": f"Bearer {seeded_desk_token}"},
    )
    assert res_desk.status_code == 200
    assert len(res_desk.json()["items"]) >= 3


def test_catalogue_rejects_invalid_role():
    """Tokens with unauthorized/unknown roles cannot access catalogue."""
    bad_token, _, _ = create_access_token("random-id", role="hacker")
    response = client.get(
        "/api/v1/catalogue/products",
        headers={"Authorization": f"Bearer {bad_token}"},
    )
    assert response.status_code in (401, 403)


def test_seeded_products_exist_with_correct_data(seeded_retailer_token):
    """Verifies all 3 sample products match specification exactly."""
    response = client.get(
        "/api/v1/catalogue/products",
        headers={"Authorization": f"Bearer {seeded_retailer_token}"},
    )
    assert response.status_code == 200
    items = {item["sku"]: item for item in response.json()["items"]}

    # 1. SKU-BS-075 (Glucose biscuit)
    assert "SKU-BS-075" in items
    biscuit = items["SKU-BS-075"]
    assert biscuit["name"] == "Glucose biscuit 75 g"
    assert biscuit["case_qty"] == 96
    assert Decimal(str(biscuit["dealer_price_per_pack"])) == Decimal("8.10")
    assert biscuit["price_unit"] == "per_pack"
    assert Decimal(str(biscuit["dealer_price_per_case"])) == Decimal("777.60")  # 8.10 * 96
    assert biscuit["stock_cases"] == 340
    assert biscuit["stock_status"] == "in_stock"
    assert biscuit["active_scheme"] is not None
    assert biscuit["active_scheme"]["scheme_type"] == "BUY_N_GET_M_FREE"
    assert biscuit["active_scheme"]["min_qty"] == 10
    assert biscuit["active_scheme"]["free_qty"] == 1
    assert "Buy 10 cases Get 1 Free" in biscuit["active_scheme"]["description"]

    # 2. SKU-DT-1KG (Detergent powder)
    assert "SKU-DT-1KG" in items
    detergent = items["SKU-DT-1KG"]
    assert detergent["name"] == "Detergent powder 1 kg"
    assert detergent["case_qty"] == 20
    assert Decimal(str(detergent["dealer_price_per_pack"])) == Decimal("101.50")
    assert Decimal(str(detergent["dealer_price_per_case"])) == Decimal("2030.00")  # 101.50 * 20
    assert detergent["stock_cases"] == 85
    assert detergent["stock_status"] == "in_stock"
    assert detergent["active_scheme"] is not None
    assert detergent["active_scheme"]["scheme_type"] == "DISCOUNT_ON_MIN_QTY"
    assert detergent["active_scheme"]["min_qty"] == 5
    assert Decimal(str(detergent["active_scheme"]["discount_pct"])) == Decimal("3.00")

    # 3. SKU-TE-250 (Tea leaf - Out of Stock)
    assert "SKU-TE-250" in items
    tea = items["SKU-TE-250"]
    assert tea["name"] == "Tea leaf 250 g"
    assert tea["case_qty"] == 40
    assert Decimal(str(tea["dealer_price_per_pack"])) == Decimal("118.00")
    assert Decimal(str(tea["dealer_price_per_case"])) == Decimal("4720.00")  # 118.00 * 40
    assert tea["stock_cases"] == 0
    assert tea["stock_status"] == "out_of_stock"
    assert tea["active_scheme"] is None


def test_product_detail_by_sku(seeded_retailer_token):
    """GET /catalogue/products/{sku} returns product detail."""
    response = client.get(
        "/api/v1/catalogue/products/SKU-BS-075",
        headers={"Authorization": f"Bearer {seeded_retailer_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["sku"] == "SKU-BS-075"
    assert data["name"] == "Glucose biscuit 75 g"
    assert data["active_scheme"]["scheme_type"] == "BUY_N_GET_M_FREE"


def test_product_detail_not_found(seeded_retailer_token):
    """Requesting non-existent SKU returns 404."""
    response = client.get(
        "/api/v1/catalogue/products/NON-EXISTENT-SKU",
        headers={"Authorization": f"Bearer {seeded_retailer_token}"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_search_by_name_and_sku(seeded_retailer_token):
    """Search matches name and SKU fragments."""
    # Search by partial name: "biscuit"
    res1 = client.get(
        "/api/v1/catalogue/products?q=biscuit",
        headers={"Authorization": f"Bearer {seeded_retailer_token}"},
    )
    assert res1.status_code == 200
    skus1 = [p["sku"] for p in res1.json()["items"]]
    assert "SKU-BS-075" in skus1
    assert "SKU-DT-1KG" not in skus1

    # Search by SKU fragment: "DT-1KG"
    res2 = client.get(
        "/api/v1/catalogue/products?q=DT-1KG",
        headers={"Authorization": f"Bearer {seeded_retailer_token}"},
    )
    assert res2.status_code == 200
    skus2 = [p["sku"] for p in res2.json()["items"]]
    assert "SKU-DT-1KG" in skus2
    assert "SKU-BS-075" not in skus2


def test_category_filtering(seeded_retailer_token):
    """Filtering by category returns only products in that category."""
    res = client.get(
        "/api/v1/catalogue/products?category=Biscuits",
        headers={"Authorization": f"Bearer {seeded_retailer_token}"},
    )
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) >= 1
    for p in items:
        assert p["category"].lower() == "biscuits"


def test_in_stock_filtering(seeded_retailer_token):
    """in_stock=true must exclude out-of-stock products like SKU-TE-250."""
    res = client.get(
        "/api/v1/catalogue/products?in_stock=true",
        headers={"Authorization": f"Bearer {seeded_retailer_token}"},
    )
    assert res.status_code == 200
    items = res.json()["items"]
    skus = [p["sku"] for p in items]
    assert "SKU-BS-075" in skus
    assert "SKU-DT-1KG" in skus
    assert "SKU-TE-250" not in skus  # stock is 0, must be filtered out


def test_pagination(seeded_retailer_token):
    """Pagination splits items and reports total pages."""
    res = client.get(
        "/api/v1/catalogue/products?page=1&page_size=2",
        headers={"Authorization": f"Bearer {seeded_retailer_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["total"] >= 3
    assert data["total_pages"] >= 2


def test_expired_scheme_is_not_active(seeded_retailer_token):
    """Schemes where valid_to < today are excluded from active_scheme."""
    db = SessionLocal()
    test_sku = f"SKU-EXP-{uuid.uuid4().hex[:6].upper()}"
    try:
        # Create a test product with expired scheme
        prod = Product(
            sku=test_sku,
            name="Expired Scheme Test Item",
            case_qty=10,
            dealer_price_per_pack=Decimal("50.00"),
            stock_cases=20,
            is_active=True,
        )
        db.add(prod)
        db.flush()

        expired_scheme = Scheme(
            product_id=prod.id,
            scheme_type="BUY_N_GET_M_FREE",
            min_qty=5,
            free_qty=1,
            valid_from=date.today() - timedelta(days=60),
            valid_to=date.today() - timedelta(days=1),  # Expired yesterday
            is_active=True,
        )
        db.add(expired_scheme)
        db.commit()

        # Query via API
        response = client.get(
            f"/api/v1/catalogue/products/{test_sku}",
            headers={"Authorization": f"Bearer {seeded_retailer_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["active_scheme"] is None  # Scheme expired!
    finally:
        # Clean up test product
        p = db.execute(select(Product).where(Product.sku == test_sku)).scalar_one_or_none()
        if p:
            db.delete(p)
            db.commit()
        db.close()


def test_sku_uniqueness_constraint():
    """Database must reject duplicate SKU."""
    db = SessionLocal()
    try:
        duplicate = Product(
            sku="SKU-BS-075",  # Already exists
            name="Duplicate Biscuit",
            case_qty=50,
            dealer_price_per_pack=Decimal("10.00"),
        )
        db.add(duplicate)
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_list_categories_endpoint(seeded_retailer_token):
    """GET /catalogue/categories returns list of active product categories."""
    response = client.get(
        "/api/v1/catalogue/categories",
        headers={"Authorization": f"Bearer {seeded_retailer_token}"},
    )
    assert response.status_code == 200
    categories = response.json()
    assert isinstance(categories, list)
    assert "Biscuits" in categories
    assert "Detergents" in categories
    assert "Beverages" in categories
