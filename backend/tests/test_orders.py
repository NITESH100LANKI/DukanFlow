"""
Integration tests for Phase 6: Order Placement & Management.

Covers:
1. Retailer places order from cart (order created, snapshots frozen, status SUBMITTED, cart cleared).
2. Stock is NOT deducted on order submission.
3. Placing order with empty cart fails (400).
4. Idempotency key prevents duplicate orders.
5. Retailer can list and view own orders.
6. Retailer cannot view another retailer's order (404/isolation).
7. Retailer cannot access Order Desk endpoints (403).
8. Order Desk cannot call place_order endpoint (403).
9. Order Desk view queue (status filtering and details).
10. Order Desk line quantity correction recalculates scheme and totals using saved snapshots.
11. Order Desk line correction requires mandatory reason.
12. Order Desk approval locks products deterministically and deducts inventory (fulfilment qty including free cases).
13. Order Desk approval fails atomically on insufficient stock (409 Conflict) and rolls back.
14. Approved or rejected orders cannot be modified, re-approved, or re-rejected (400).
15. Order Desk rejection transitions status to REJECTED with reason and leaves stock untouched.
"""

import uuid
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, delete

from app.main import app
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.auth import Retailer, OrderDeskUser
from app.models.catalogue import Product, Scheme
from app.models.cart import Cart, CartLine
from app.models.order import Order, OrderLine, OrderAuditLog

client = TestClient(app)


@pytest.fixture(scope="module")
def retailer_a():
    """Provides Retailer A object and token."""
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
        return {"id": retailer.id, "token": token, "name": retailer.name}
    finally:
        db.close()


@pytest.fixture(scope="module")
def retailer_b():
    """Provides distinct Retailer B object and token."""
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
        return {"id": retailer.id, "token": token, "name": retailer.name}
    finally:
        db.close()


@pytest.fixture(scope="module")
def desk_user():
    """Provides Order Desk user object and token."""
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
        return {"id": desk.id, "token": token, "name": desk.full_name}
    finally:
        db.close()


@pytest.fixture(scope="module")
def products():
    """Fetches seeded products and restores clean stock after tests complete."""
    db = SessionLocal()
    try:
        biscuit = db.execute(select(Product).where(Product.sku == "SKU-BS-075")).scalar_one()
        detergent = db.execute(select(Product).where(Product.sku == "SKU-DT-1KG")).scalar_one()
        tea = db.execute(select(Product).where(Product.sku == "SKU-TE-250")).scalar_one()

        biscuit.stock_cases = 340
        detergent.stock_cases = 85
        tea.stock_cases = 0
        db.commit()
        db.refresh(biscuit)
        db.refresh(detergent)
        db.refresh(tea)
        yield {"biscuit": biscuit, "detergent": detergent, "tea": tea}
    finally:
        # Restore canonical seeded stock with a clean session
        restore_db = SessionLocal()
        try:
            b = restore_db.execute(select(Product).where(Product.sku == "SKU-BS-075")).scalar_one_or_none()
            if b:
                b.stock_cases = 340
            d = restore_db.execute(select(Product).where(Product.sku == "SKU-DT-1KG")).scalar_one_or_none()
            if d:
                d.stock_cases = 85
            t = restore_db.execute(select(Product).where(Product.sku == "SKU-TE-250")).scalar_one_or_none()
            if t:
                t.stock_cases = 0
            restore_db.commit()
        finally:
            restore_db.close()
            db.close()


def test_empty_cart_order_placement_rejected(retailer_a):
    """Attempting to place an order when cart is empty returns 400 Bad Request."""
    headers = {"Authorization": f"Bearer {retailer_a['token']}"}
    client.delete("/api/v1/cart", headers=headers)

    res = client.post("/api/v1/orders", json={"remarks": "test"}, headers=headers)
    assert res.status_code == 400
    assert "empty cart" in res.json()["detail"].lower()


def test_place_order_from_cart_success(retailer_a, products):
    """
    Retailer places order from cart:
    - Order is created with frozen snapshots
    - Status is SUBMITTED
    - Stock is NOT deducted
    - Cart is cleared
    """
    headers = {"Authorization": f"Bearer {retailer_a['token']}"}
    biscuit = products["biscuit"]

    # 1. Clear cart and add 10 cases of biscuit (Buy 10 Get 1 scheme)
    client.delete("/api/v1/cart", headers=headers)
    add_res = client.post(
        "/api/v1/cart/lines",
        json={"product_id": str(biscuit.id), "qty_cases": 10},
        headers=headers,
    )
    assert add_res.status_code == 200

    # Record product stock before order submission
    db = SessionLocal()
    prod_before = db.execute(select(Product).where(Product.id == biscuit.id)).scalar_one()
    stock_before = prod_before.stock_cases
    db.close()

    # 2. Place order
    res = client.post(
        "/api/v1/orders",
        json={"remarks": "Urgent morning delivery"},
        headers=headers,
    )
    assert res.status_code == 201
    order = res.json()

    assert order["status"] == "SUBMITTED"
    assert order["order_number"].startswith("ORD-")
    assert order["remarks"] == "Urgent morning delivery"
    assert order["total_cases"] == 10
    assert order["total_free_cases"] == 1
    assert order["total_fulfilment_cases"] == 11
    assert len(order["lines"]) == 1

    line = order["lines"][0]
    assert line["sku_snapshot"] == biscuit.sku
    assert line["name_snapshot"] == biscuit.name
    assert line["qty_cases"] == 10
    assert line["free_cases"] == 1
    assert line["fulfilment_qty_cases"] == 11
    assert line["scheme_type_snapshot"] == "BUY_N_GET_M_FREE"

    # Audit log check
    assert len(order["audit_logs"]) >= 1
    assert order["audit_logs"][0]["action"] == "SUBMITTED"

    # 3. Stock must NOT be deducted yet!
    db = SessionLocal()
    prod_after = db.execute(select(Product).where(Product.id == biscuit.id)).scalar_one()
    assert prod_after.stock_cases == stock_before, "Stock must NOT be deducted on order submission"
    db.close()

    # 4. Cart must now be empty
    cart_res = client.get("/api/v1/cart", headers=headers)
    assert cart_res.status_code == 200
    assert cart_res.json()["lines"] == []


def test_order_submission_idempotency(retailer_a, products):
    """Submitting order with same Idempotency-Key returns existing order and avoids duplicate."""
    headers = {"Authorization": f"Bearer {retailer_a['token']}"}
    biscuit = products["biscuit"]

    client.delete("/api/v1/cart", headers=headers)
    client.post(
        "/api/v1/cart/lines",
        json={"product_id": str(biscuit.id), "qty_cases": 5},
        headers=headers,
    )

    idem_key = f"test-key-{uuid.uuid4()}"
    headers_with_key = {**headers, "Idempotency-Key": idem_key}

    res1 = client.post("/api/v1/orders", json={"remarks": "First call"}, headers=headers_with_key)
    assert res1.status_code == 201
    order1 = res1.json()

    # Second call with same idempotency key (even though cart is now empty!)
    res2 = client.post("/api/v1/orders", json={"remarks": "Duplicate call"}, headers=headers_with_key)
    assert res2.status_code == 201 or res2.status_code == 200
    order2 = res2.json()

    assert order1["id"] == order2["id"]
    assert order1["order_number"] == order2["order_number"]


def test_retailer_order_isolation(retailer_a, retailer_b, products):
    """Retailer B cannot fetch or view Retailer A's order."""
    headers_a = {"Authorization": f"Bearer {retailer_a['token']}"}
    headers_b = {"Authorization": f"Bearer {retailer_b['token']}"}

    # Retailer A creates an order
    client.delete("/api/v1/cart", headers=headers_a)
    client.post(
        "/api/v1/cart/lines",
        json={"product_id": str(products["biscuit"].id), "qty_cases": 2},
        headers=headers_a,
    )
    res_a = client.post("/api/v1/orders", json={}, headers=headers_a)
    order_a_id = res_a.json()["id"]

    # Retailer B attempts to access Retailer A's order
    res_b = client.get(f"/api/v1/orders/{order_a_id}", headers=headers_b)
    assert res_b.status_code == 404


def test_role_enforcement_on_order_endpoints(retailer_a, desk_user):
    """Retailers cannot call Desk endpoints; Desk cannot place orders directly."""
    retailer_headers = {"Authorization": f"Bearer {retailer_a['token']}"}
    desk_headers = {"Authorization": f"Bearer {desk_user['token']}"}

    # Retailer denied from Desk queue
    res = client.get("/api/v1/desk/orders", headers=retailer_headers)
    assert res.status_code == 403

    # Desk user denied from placing cart order
    res2 = client.post("/api/v1/orders", json={}, headers=desk_headers)
    assert res2.status_code == 403


def test_desk_order_queue_and_status_filter(retailer_a, desk_user, products):
    """Order Desk can query all orders with pagination and status filters."""
    desk_headers = {"Authorization": f"Bearer {desk_user['token']}"}

    res = client.get("/api/v1/desk/orders?status=SUBMITTED", headers=desk_headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert all(item["status"] == "SUBMITTED" for item in data["items"])


def test_desk_line_quantity_correction_with_snapshot_recalculation(retailer_a, desk_user, products):
    """
    Order Desk operator corrects case quantity:
    - Recalculates scheme bonus and totals using frozen line snapshots.
    - Records an audit log with reason and previous vs new quantities.
    """
    retailer_headers = {"Authorization": f"Bearer {retailer_a['token']}"}
    desk_headers = {"Authorization": f"Bearer {desk_user['token']}"}
    biscuit = products["biscuit"]

    # Retailer orders 10 cases (1 free case)
    client.delete("/api/v1/cart", headers=retailer_headers)
    client.post(
        "/api/v1/cart/lines",
        json={"product_id": str(biscuit.id), "qty_cases": 10},
        headers=retailer_headers,
    )
    order_res = client.post("/api/v1/orders", json={}, headers=retailer_headers)
    order = order_res.json()
    order_id = order["id"]
    line_id = order["lines"][0]["id"]

    assert order["lines"][0]["qty_cases"] == 10
    assert order["lines"][0]["free_cases"] == 1

    # Order Desk corrects quantity to 20 cases (Buy 10 Get 1 -> should yield 2 free cases, total 22 fulfilment)
    patch_res = client.patch(
        f"/api/v1/desk/orders/{order_id}/lines/{line_id}",
        json={"qty_cases": 20, "reason": "Customer called to increase quantity"},
        headers=desk_headers,
    )
    assert patch_res.status_code == 200
    updated_order = patch_res.json()

    assert updated_order["lines"][0]["qty_cases"] == 20
    assert updated_order["lines"][0]["free_cases"] == 2
    assert updated_order["lines"][0]["fulfilment_qty_cases"] == 22
    assert updated_order["total_cases"] == 20
    assert updated_order["total_free_cases"] == 2
    assert updated_order["total_fulfilment_cases"] == 22

    # Verify audit log recorded correction
    audit_actions = [a["action"] for a in updated_order["audit_logs"]]
    assert "LINE_CORRECTED" in audit_actions
    correction_log = next(a for a in updated_order["audit_logs"] if a["action"] == "LINE_CORRECTED")
    assert correction_log["note"] == "Customer called to increase quantity"
    assert correction_log["details"]["old_qty"] == 10
    assert correction_log["details"]["new_qty"] == 20


def test_desk_line_quantity_correction_requires_reason(retailer_a, desk_user, products):
    """Line correction fails with 422 if reason is empty."""
    retailer_headers = {"Authorization": f"Bearer {retailer_a['token']}"}
    desk_headers = {"Authorization": f"Bearer {desk_user['token']}"}

    client.delete("/api/v1/cart", headers=retailer_headers)
    client.post(
        "/api/v1/cart/lines",
        json={"product_id": str(products["biscuit"].id), "qty_cases": 1},
        headers=retailer_headers,
    )
    order = client.post("/api/v1/orders", json={}, headers=retailer_headers).json()

    res = client.patch(
        f"/api/v1/desk/orders/{order['id']}/lines/{order['lines'][0]['id']}",
        json={"qty_cases": 5, "reason": ""},
        headers=desk_headers,
    )
    assert res.status_code == 422


def test_desk_approval_with_inventory_deduction(retailer_a, desk_user, products):
    """
    Order Desk approves order:
    - Atomically deducts physical fulfilment cases (including scheme bonus cases) from stock.
    - Status transitions to APPROVED.
    - Records audit log.
    """
    retailer_headers = {"Authorization": f"Bearer {retailer_a['token']}"}
    desk_headers = {"Authorization": f"Bearer {desk_user['token']}"}
    biscuit = products["biscuit"]

    # 1. Place order for 10 cases (fulfilment = 11 cases)
    client.delete("/api/v1/cart", headers=retailer_headers)
    client.post(
        "/api/v1/cart/lines",
        json={"product_id": str(biscuit.id), "qty_cases": 10},
        headers=retailer_headers,
    )
    order = client.post("/api/v1/orders", json={}, headers=retailer_headers).json()
    order_id = order["id"]

    db = SessionLocal()
    stock_before = db.execute(select(Product.stock_cases).where(Product.id == biscuit.id)).scalar()
    db.close()

    # 2. Approve order
    approve_res = client.post(
        f"/api/v1/desk/orders/{order_id}/approve",
        json={"note": "Approved for dispatch"},
        headers=desk_headers,
    )
    assert approve_res.status_code == 200
    approved_order = approve_res.json()
    assert approved_order["status"] == "APPROVED"

    # 3. Verify stock deducted by 11 cases (10 paid + 1 free)
    db = SessionLocal()
    stock_after = db.execute(select(Product.stock_cases).where(Product.id == biscuit.id)).scalar()
    db.close()

    assert stock_after == stock_before - 11, f"Expected {stock_before - 11}, got {stock_after}"


def test_desk_approval_fails_on_insufficient_stock_and_rolls_back(retailer_a, desk_user, products):
    """
    When available inventory < fulfilment_qty_cases:
    - Approval returns 409 Conflict.
    - Transaction is rolled back: stock is NOT modified.
    - Order status remains SUBMITTED.
    """
    retailer_headers = {"Authorization": f"Bearer {retailer_a['token']}"}
    desk_headers = {"Authorization": f"Bearer {desk_user['token']}"}
    detergent = products["detergent"]

    # 1. Place order for 10 cases
    client.delete("/api/v1/cart", headers=retailer_headers)
    client.post(
        "/api/v1/cart/lines",
        json={"product_id": str(detergent.id), "qty_cases": 10},
        headers=retailer_headers,
    )
    order = client.post("/api/v1/orders", json={}, headers=retailer_headers).json()
    order_id = order["id"]

    # 2. Artificially set stock to only 5 cases in database
    db = SessionLocal()
    p = db.execute(select(Product).where(Product.id == detergent.id)).scalar_one()
    p.stock_cases = 5
    db.commit()
    db.close()

    # 3. Attempt approval
    res = client.post(
        f"/api/v1/desk/orders/{order_id}/approve",
        json={"note": "Should fail"},
        headers=desk_headers,
    )
    assert res.status_code == 409
    error_data = res.json()["detail"]
    assert "insufficient" in error_data["message"].lower()

    # 4. Verify stock and order status remain untouched
    db = SessionLocal()
    stock_check = db.execute(select(Product.stock_cases).where(Product.id == detergent.id)).scalar()
    order_check = db.execute(select(Order.status).where(Order.id == order_id)).scalar()
    # Reset stock for remaining tests
    p = db.execute(select(Product).where(Product.id == detergent.id)).scalar_one()
    p.stock_cases = 120
    db.commit()
    db.close()

    assert stock_check == 5
    assert order_check == "SUBMITTED"


def test_desk_rejection_leaves_stock_untouched(retailer_a, desk_user, products):
    """
    Order rejection:
    - Requires mandatory reason.
    - Status transitions to REJECTED.
    - Stock is NOT deducted.
    """
    retailer_headers = {"Authorization": f"Bearer {retailer_a['token']}"}
    desk_headers = {"Authorization": f"Bearer {desk_user['token']}"}
    biscuit = products["biscuit"]

    client.delete("/api/v1/cart", headers=retailer_headers)
    client.post(
        "/api/v1/cart/lines",
        json={"product_id": str(biscuit.id), "qty_cases": 5},
        headers=retailer_headers,
    )
    order = client.post("/api/v1/orders", json={}, headers=retailer_headers).json()
    order_id = order["id"]

    db = SessionLocal()
    stock_before = db.execute(select(Product.stock_cases).where(Product.id == biscuit.id)).scalar()
    db.close()

    # Reject order
    res = client.post(
        f"/api/v1/desk/orders/{order_id}/reject",
        json={"reason": "Store permanently closed"},
        headers=desk_headers,
    )
    assert res.status_code == 200
    rejected_order = res.json()
    assert rejected_order["status"] == "REJECTED"
    assert rejected_order["rejection_reason"] == "Store permanently closed"

    # Stock must be untouched
    db = SessionLocal()
    stock_after = db.execute(select(Product.stock_cases).where(Product.id == biscuit.id)).scalar()
    db.close()
    assert stock_after == stock_before


def test_cannot_modify_or_reapprove_finalized_orders(retailer_a, desk_user, products):
    """Approved or Rejected orders cannot be approved again, rejected again, or have lines edited."""
    retailer_headers = {"Authorization": f"Bearer {retailer_a['token']}"}
    desk_headers = {"Authorization": f"Bearer {desk_user['token']}"}
    biscuit = products["biscuit"]

    # 1. Place and approve an order
    client.delete("/api/v1/cart", headers=retailer_headers)
    client.post(
        "/api/v1/cart/lines",
        json={"product_id": str(biscuit.id), "qty_cases": 1},
        headers=retailer_headers,
    )
    order = client.post("/api/v1/orders", json={}, headers=retailer_headers).json()
    order_id = order["id"]
    line_id = order["lines"][0]["id"]

    client.post(f"/api/v1/desk/orders/{order_id}/approve", headers=desk_headers)

    # Re-approve fails
    res_reapprove = client.post(f"/api/v1/desk/orders/{order_id}/approve", headers=desk_headers)
    assert res_reapprove.status_code == 400

    # Reject approved fails
    res_reject = client.post(
        f"/api/v1/desk/orders/{order_id}/reject",
        json={"reason": "Too late"},
        headers=desk_headers,
    )
    assert res_reject.status_code == 400

    # Line edit fails
    res_edit = client.patch(
        f"/api/v1/desk/orders/{order_id}/lines/{line_id}",
        json={"qty_cases": 2, "reason": "Edit after approval"},
        headers=desk_headers,
    )
    assert res_edit.status_code == 400


def test_concurrent_order_approvals_prevent_double_deduction(retailer_a, desk_user, products):
    """
    Two concurrent approval requests attempting to approve the same submitted order:
    - Order row is locked using SELECT ... FOR UPDATE.
    - Exactly ONE request succeeds (status 200).
    - The concurrent request fails with status 400 (order status is already APPROVED).
    - Physical stock is deducted EXACTLY ONCE for fulfilment cases.
    """
    import concurrent.futures

    retailer_headers = {"Authorization": f"Bearer {retailer_a['token']}"}
    desk_headers = {"Authorization": f"Bearer {desk_user['token']}"}
    biscuit = products["biscuit"]

    # 1. Ensure product has known stock
    db = SessionLocal()
    p = db.execute(select(Product).where(Product.id == biscuit.id)).scalar_one()
    initial_stock = 340
    p.stock_cases = initial_stock
    db.commit()
    db.close()

    # 2. Place an order for 10 cases of biscuits (Buy 10 get 1 free -> 11 fulfilment cases)
    client.delete("/api/v1/cart", headers=retailer_headers)
    client.post(
        "/api/v1/cart/lines",
        json={"product_id": str(biscuit.id), "qty_cases": 10},
        headers=retailer_headers,
    )
    res = client.post("/api/v1/orders", json={}, headers=retailer_headers)
    assert res.status_code == 201
    order_id = res.json()["id"]

    # 3. Concurrently invoke approve endpoint using 2 separate worker threads
    def do_approve():
        with TestClient(app) as thread_client:
            return thread_client.post(
                f"/api/v1/desk/orders/{order_id}/approve",
                headers=desk_headers,
                json={"note": "Concurrent approval test"},
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(do_approve)
        f2 = executor.submit(do_approve)
        r1 = f1.result()
        r2 = f2.result()

    status_codes = sorted([r1.status_code, r2.status_code])
    # Exactly one must succeed (200) and the other must fail (400)
    assert status_codes == [200, 400]

    # Verify inventory was deducted exactly ONCE (340 - 11 = 329)
    db = SessionLocal()
    p = db.execute(select(Product).where(Product.id == biscuit.id)).scalar_one()
    assert p.stock_cases == initial_stock - 11
    # Restore stock
    p.stock_cases = initial_stock
    db.commit()
    db.close()


def test_free_goods_benefit_and_monetary_discount_separation(retailer_a, desk_user, products):
    """
    Verifies that:
    - Buy 10 Get 1 Free Biscuit:
      Gross: 7776.00, Discount: 0.00, Benefit: 777.60, Net: 7776.00
      (free goods benefit value is NOT subtracted from net payable).
    - 3% Discount Detergent (5 cases @ 2030.00 = 10150.00):
      Gross: 10150.00, Discount: 304.50, Benefit: 304.50, Net: 9845.50.
    - Order summary:
      Gross: 17926.00, Discount total: 304.50, Benefit total: 1082.10, Scheme total: 1082.10, Net total: 17621.50.
    - Values are preserved on Order and OrderLine models and API outputs.
    """
    retailer_headers = {"Authorization": f"Bearer {retailer_a['token']}"}
    biscuit = products["biscuit"]
    detergent = products["detergent"]

    client.delete("/api/v1/cart", headers=retailer_headers)
    # 10 cases of biscuits
    client.post(
        "/api/v1/cart/lines",
        json={"product_id": str(biscuit.id), "qty_cases": 10},
        headers=retailer_headers,
    )
    # 5 cases of detergent
    client.post(
        "/api/v1/cart/lines",
        json={"product_id": str(detergent.id), "qty_cases": 5},
        headers=retailer_headers,
    )

    res = client.post("/api/v1/orders", json={}, headers=retailer_headers)
    assert res.status_code == 201
    data = res.json()

    assert Decimal(str(data["gross_total"])) == Decimal("17926.00")
    assert Decimal(str(data["discount_total"])) == Decimal("304.50")
    assert Decimal(str(data["benefit_total"])) == Decimal("1082.10")
    assert Decimal(str(data["net_total"])) == Decimal("17621.50")

    # Inspect individual lines
    lines_by_sku = {l["sku_snapshot"]: l for l in data["lines"]}
    biscuit_line = lines_by_sku["SKU-BS-075"]
    assert biscuit_line["qty_cases"] == 10
    assert biscuit_line["free_cases"] == 1
    assert biscuit_line["fulfilment_qty_cases"] == 11
    assert Decimal(str(biscuit_line["gross_amount"])) == Decimal("7776.00")
    assert Decimal(str(biscuit_line["discount_amount"])) == Decimal("0.00")
    assert Decimal(str(biscuit_line["benefit_value"])) == Decimal("777.60")
    assert Decimal(str(biscuit_line["net_amount"])) == Decimal("7776.00")

    det_line = lines_by_sku["SKU-DT-1KG"]
    assert det_line["qty_cases"] == 5
    assert det_line["free_cases"] == 0
    assert det_line["fulfilment_qty_cases"] == 5
    assert Decimal(str(det_line["gross_amount"])) == Decimal("10150.00")
    assert Decimal(str(det_line["discount_amount"])) == Decimal("304.50")
    assert Decimal(str(det_line["benefit_value"])) == Decimal("304.50")
    assert Decimal(str(det_line["net_amount"])) == Decimal("9845.50")


def test_cross_retailer_idempotency_isolation(retailer_a, retailer_b, products):
    """
    If Retailer B sends an order placement request using an Idempotency-Key
    already used by Retailer A:
    - Return 409 Conflict.
    - Do NOT return Retailer A's order to Retailer B.
    - Retailer B's cart remains unchanged.
    """
    retailer_a_headers = {
        "Authorization": f"Bearer {retailer_a['token']}",
        "Idempotency-Key": "SHARED-KEY-ATTEMPT-001",
    }
    retailer_b_headers = {
        "Authorization": f"Bearer {retailer_b['token']}",
        "Idempotency-Key": "SHARED-KEY-ATTEMPT-001",
    }
    biscuit = products["biscuit"]

    # Retailer A places order with key
    client.delete("/api/v1/cart", headers=retailer_a_headers)
    client.post(
        "/api/v1/cart/lines",
        json={"product_id": str(biscuit.id), "qty_cases": 1},
        headers=retailer_a_headers,
    )
    res_a = client.post("/api/v1/orders", json={}, headers=retailer_a_headers)
    assert res_a.status_code == 201

    # Retailer B attempts to use the same idempotency key
    client.delete("/api/v1/cart", headers=retailer_b_headers)
    client.post(
        "/api/v1/cart/lines",
        json={"product_id": str(biscuit.id), "qty_cases": 2},
        headers=retailer_b_headers,
    )
    res_b = client.post("/api/v1/orders", json={}, headers=retailer_b_headers)
    assert res_b.status_code == 409
    assert "another retailer" in res_b.json()["detail"].lower()

    # Confirm Retailer B cart was NOT cleared
    cart_b = client.get("/api/v1/cart", headers=retailer_b_headers).json()
    assert len(cart_b["lines"]) == 1


def test_failed_submission_preserves_cart(retailer_a, products):
    """
    If an order creation fails (e.g. inactive product in cart),
    the cart is not cleared and remains intact for the retailer.
    """
    retailer_headers = {"Authorization": f"Bearer {retailer_a['token']}"}
    biscuit = products["biscuit"]

    client.delete("/api/v1/cart", headers=retailer_headers)
    client.post(
        "/api/v1/cart/lines",
        json={"product_id": str(biscuit.id), "qty_cases": 2},
        headers=retailer_headers,
    )

    # Deactivate biscuit temporarily
    db = SessionLocal()
    p = db.execute(select(Product).where(Product.id == biscuit.id)).scalar_one()
    p.is_active = False
    db.commit()

    try:
        res = client.post("/api/v1/orders", json={}, headers=retailer_headers)
        assert res.status_code == 400
        assert "no longer active" in res.json()["detail"].lower()

        # Cart lines must still be present
        cart = client.get("/api/v1/cart", headers=retailer_headers).json()
        assert len(cart["lines"]) == 1
        assert cart["lines"][0]["qty_cases"] == 2
    finally:
        p.is_active = True
        db.commit()
        db.close()

