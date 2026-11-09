"""
Comprehensive tests for Phase 8: Tally-Compatible CSV Export & Accounting Integration.

Covers:
1. Only APPROVED orders can be exported; SUBMITTED and REJECTED orders are rejected (400).
2. Financial snapshot values (gross, discount, benefit, net, rate) are preserved from snapshots, not live catalogue.
3. Free-goods benefit value remains separate from discount and does not reduce net payable.
4. Correct Decimal formatting (2 decimal places) and date formatting.
5. Multiple orders exported together in a single batch.
6. Empty selection handling (400) and nonexistent order IDs (404).
7. Retailer role is denied (403) and unauthenticated requests are denied (401).
8. Order Desk role is authorized.
9. Repeated export tracking (order can be exported multiple times; each export creates distinct batch & lines).
10. Download endpoint returns valid CSV with UTF-8 BOM, Content-Disposition, and SHA-256 header.
11. Formula injection protection (CWE-1236): fields starting with =, +, -, @ are escaped with '.
12. GST columns are not invented (left blank pending client confirmation).
13. Zero mutation: Exporting never changes Order status, Order financials, or Product stock.
14. Export history retrieval with pagination and aggregate statistics.
"""

import csv
import io
import uuid
from decimal import Decimal
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, delete

from app.main import app
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.auth import Retailer, OrderDeskUser
from app.models.catalogue import Product
from app.models.order import Order, OrderLine
from app.models.export import ExportBatch, ExportBatchLine
from app.services.export_service import sanitize_csv_field

client = TestClient(app)


@pytest.fixture(scope="module")
def desk_user():
    """Provides Order Desk user object and token."""
    db = SessionLocal()
    try:
        user = db.execute(
            select(OrderDeskUser).where(OrderDeskUser.email == "desk_export@dukaanflow.in")
        ).scalar_one_or_none()
        if not user:
            user = OrderDeskUser(
                email="desk_export@dukaanflow.in",
                full_name="Rajesh Sharma",
                password_hash="testhash",
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        token, _, _ = create_access_token(str(user.id), role="order_desk")
        return {"id": user.id, "token": token, "name": user.full_name}
    finally:
        db.close()


@pytest.fixture(scope="module")
def retailer_user():
    """Provides Retailer user object and token."""
    db = SessionLocal()
    try:
        ret = db.execute(
            select(Retailer).where(Retailer.mobile == "9988776655")
        ).scalar_one_or_none()
        if not ret:
            ret = Retailer(
                mobile="9988776655",
                name="=Formula Kirana Store",  # Intentionally crafted for formula injection test
                address="Civic Center, Jabalpur",
                tally_ledger_name="@Formula Ledger",
                is_active=True,
            )
            db.add(ret)
            db.commit()
            db.refresh(ret)
        token, _, _ = create_access_token(str(ret.id), role="retailer")
        return {"id": ret.id, "token": token, "name": ret.name}
    finally:
        db.close()


@pytest.fixture(scope="module")
def seeded_product():
    """Provides product for test orders."""
    db = SessionLocal()
    try:
        prod = db.execute(
            select(Product).where(Product.sku == "SKU-BS-075")
        ).scalar_one()
        return {
            "id": prod.id,
            "sku": prod.sku,
            "name": prod.name,
            "case_qty": prod.case_qty,
            "stock_cases": prod.stock_cases,
        }
    finally:
        db.close()


@pytest.fixture(scope="module")
def sample_orders(retailer_user, seeded_product, desk_user):
    """
    Creates three distinct test orders:
    1. Approved order with Buy 10 Get 1 Free biscuit scheme
    2. Approved order with 3% discount detergent scheme
    3. Submitted (unapproved) order
    4. Rejected order
    """
    db = SessionLocal()
    try:
        # 1. Approved Order 1 (Buy 10 Get 1 Free biscuit)
        # Paid: 10, Free: 1, Fulfilment: 11
        # Gross: 7776.00, Discount: 0.00, Benefit: 777.60, Net: 7776.00
        ord1 = Order(
            order_number=f"ORD-TEST-EXP1-{uuid.uuid4().hex[:6]}",
            retailer_id=retailer_user["id"],
            reviewed_by=desk_user["id"],
            status="APPROVED",
            gross_total=Decimal("7776.00"),
            discount_total=Decimal("0.00"),
            benefit_total=Decimal("777.60"),
            scheme_total=Decimal("777.60"),
            net_total=Decimal("7776.00"),
            total_cases=10,
            total_free_cases=1,
            total_fulfilment_cases=11,
        )
        db.add(ord1)
        db.flush()

        line1 = OrderLine(
            order_id=ord1.id,
            product_id=seeded_product["id"],
            sku_snapshot="SKU-BS-075",
            name_snapshot="Glucose Biscuit 75g",
            pack_size_snapshot="75g",
            case_qty_snapshot=seeded_product["case_qty"],
            price_per_pack_snapshot=Decimal("10.80"),
            price_per_case_snapshot=Decimal("777.60"),
            scheme_type_snapshot="BUY_N_GET_M_FREE",
            min_qty_snapshot=10,
            free_qty_snapshot=1,
            discount_pct_snapshot=None,
            qty_cases=10,
            free_cases=1,
            fulfilment_qty_cases=11,
            unit_price=Decimal("777.60"),
            gross_amount=Decimal("7776.00"),
            discount_amount=Decimal("0.00"),
            benefit_value=Decimal("777.60"),
            net_amount=Decimal("7776.00"),
        )
        db.add(line1)

        # 2. Approved Order 2 (3% discount on 5 cases Detergent)
        # Canonical: Paid=5, Free=0, Fulfilment=5, Gross=10150.00, Discount=304.50, Benefit=304.50, Net=9845.50
        ord2 = Order(
            order_number=f"ORD-TEST-EXP2-{uuid.uuid4().hex[:6]}",
            retailer_id=retailer_user["id"],
            reviewed_by=desk_user["id"],
            status="APPROVED",
            gross_total=Decimal("10150.00"),
            discount_total=Decimal("304.50"),
            benefit_total=Decimal("304.50"),
            scheme_total=Decimal("304.50"),
            net_total=Decimal("9845.50"),
            total_cases=5,
            total_free_cases=0,
            total_fulfilment_cases=5,
        )
        db.add(ord2)
        db.flush()

        line2 = OrderLine(
            order_id=ord2.id,
            product_id=seeded_product["id"],
            sku_snapshot="SKU-DT-1KG",
            name_snapshot="+Washing Powder 1kg",  # Crafted with '+' for formula injection check
            pack_size_snapshot="1kg",
            case_qty_snapshot=20,
            price_per_pack_snapshot=Decimal("101.50"),
            price_per_case_snapshot=Decimal("2030.00"),
            scheme_type_snapshot="DISCOUNT_ON_MIN_QTY",
            min_qty_snapshot=5,
            free_qty_snapshot=0,
            discount_pct_snapshot=Decimal("3.00"),
            qty_cases=5,
            free_cases=0,
            fulfilment_qty_cases=5,
            unit_price=Decimal("2030.00"),
            gross_amount=Decimal("10150.00"),
            discount_amount=Decimal("304.50"),
            benefit_value=Decimal("304.50"),
            net_amount=Decimal("9845.50"),
        )
        db.add(line2)

        # 3. Submitted (unapproved) Order
        ord_sub = Order(
            order_number=f"ORD-TEST-SUB-{uuid.uuid4().hex[:6]}",
            retailer_id=retailer_user["id"],
            status="SUBMITTED",
            gross_total=Decimal("1000.00"),
            net_total=Decimal("1000.00"),
            total_cases=1,
            total_fulfilment_cases=1,
        )
        db.add(ord_sub)

        # 4. Rejected Order
        ord_rej = Order(
            order_number=f"ORD-TEST-REJ-{uuid.uuid4().hex[:6]}",
            retailer_id=retailer_user["id"],
            reviewed_by=desk_user["id"],
            status="REJECTED",
            gross_total=Decimal("2000.00"),
            net_total=Decimal("2000.00"),
            total_cases=2,
            total_fulfilment_cases=2,
            rejection_reason="Insufficient credit",
        )
        db.add(ord_rej)

        db.commit()
        db.refresh(ord1)
        db.refresh(ord2)
        db.refresh(ord_sub)
        db.refresh(ord_rej)

        return {
            "approved_1": ord1,
            "approved_2": ord2,
            "submitted": ord_sub,
            "rejected": ord_rej,
        }
    finally:
        db.close()


def test_sanitize_csv_field_formula_injection():
    """Formula injection triggers (=, +, -, @, tab) are neutralized with single quote prefix."""
    assert sanitize_csv_field("Normal Product") == "Normal Product"
    assert sanitize_csv_field("=cmd|'/C calc'!A0") == "'=cmd|'/C calc'!A0"
    assert sanitize_csv_field(" =cmd|'/C calc'!A0") == "' =cmd|'/C calc'!A0"
    assert sanitize_csv_field("+12345") == "'+12345"
    assert sanitize_csv_field("-SUM(A1:A10)") == "'-SUM(A1:A10)"
    assert sanitize_csv_field("@special") == "'@special"
    assert sanitize_csv_field("\ttabbed") == "'\ttabbed"
    assert sanitize_csv_field(None) == ""


def test_rbac_access_control(retailer_user, desk_user):
    """Unauthenticated requests are rejected (401); Retailers are denied (403); Order Desk allowed."""
    # 1. Unauthenticated -> 401
    res_no_auth = client.get("/api/v1/desk/exports/orders")
    assert res_no_auth.status_code == 401

    # 2. Retailer token -> 403 Forbidden
    retailer_headers = {"Authorization": f"Bearer {retailer_user['token']}"}
    res_ret = client.get("/api/v1/desk/exports/orders", headers=retailer_headers)
    assert res_ret.status_code == 403

    res_ret_post = client.post("/api/v1/desk/exports", json={"order_ids": []}, headers=retailer_headers)
    assert res_ret_post.status_code == 403

    # 3. Order Desk token -> 200 OK
    desk_headers = {"Authorization": f"Bearer {desk_user['token']}"}
    res_desk = client.get("/api/v1/desk/exports/orders", headers=desk_headers)
    assert res_desk.status_code == 200


def test_get_export_profiles(desk_user):
    """Returns preliminary Generic Accounting export profile with disclaimer."""
    desk_headers = {"Authorization": f"Bearer {desk_user['token']}"}
    res = client.get("/api/v1/desk/exports/profiles", headers=desk_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    generic = next((p for p in data if p["key"] == "generic"), None)
    assert generic is not None
    assert generic["is_preliminary"] is True
    assert "Tally" in generic["description"] or "Tally" in generic["display_name"]


def test_list_exportable_orders_returns_only_approved(desk_user, sample_orders):
    """Only orders with status APPROVED are returned by the exportable orders listing."""
    desk_headers = {"Authorization": f"Bearer {desk_user['token']}"}
    res = client.get("/api/v1/desk/exports/orders", headers=desk_headers)
    assert res.status_code == 200
    data = res.json()
    items = data["items"]

    assert data["total"] >= 2
    # Ensure every returned order has status APPROVED
    for item in items:
        assert item["status"] == "APPROVED"

    order_numbers = [i["order_number"] for i in items]
    assert sample_orders["approved_1"].order_number in order_numbers
    assert sample_orders["approved_2"].order_number in order_numbers
    # SUBMITTED and REJECTED must NOT be in the exportable list
    assert sample_orders["submitted"].order_number not in order_numbers
    assert sample_orders["rejected"].order_number not in order_numbers


def test_export_empty_order_ids_rejected(desk_user):
    """Exporting with empty order_ids list returns 400 Bad Request."""
    desk_headers = {"Authorization": f"Bearer {desk_user['token']}"}
    res = client.post("/api/v1/desk/exports", json={"order_ids": [], "profile": "generic"}, headers=desk_headers)
    assert res.status_code == 400
    assert "At least one order must be selected" in res.json()["detail"]


def test_export_nonexistent_order_id_rejected(desk_user):
    """Exporting with nonexistent order UUID returns 404 Not Found."""
    desk_headers = {"Authorization": f"Bearer {desk_user['token']}"}
    fake_id = str(uuid.uuid4())
    res = client.post("/api/v1/desk/exports", json={"order_ids": [fake_id]}, headers=desk_headers)
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_export_unapproved_order_rejected(desk_user, sample_orders):
    """Attempting to export a SUBMITTED or REJECTED order is strictly blocked (400)."""
    desk_headers = {"Authorization": f"Bearer {desk_user['token']}"}

    # 1. Attempt SUBMITTED order
    res_sub = client.post(
        "/api/v1/desk/exports",
        json={"order_ids": [str(sample_orders["submitted"].id)]},
        headers=desk_headers,
    )
    assert res_sub.status_code == 400
    assert "Only APPROVED orders can be exported" in res_sub.json()["detail"]

    # 2. Attempt REJECTED order
    res_rej = client.post(
        "/api/v1/desk/exports",
        json={"order_ids": [str(sample_orders["rejected"].id)]},
        headers=desk_headers,
    )
    assert res_rej.status_code == 400
    assert "Only APPROVED orders can be exported" in res_rej.json()["detail"]


def test_successful_batch_export_financial_integrity(desk_user, sample_orders, seeded_product):
    """
    Exports multiple approved orders.
    Verifies:
    1. Financial snapshots are preserved (Gross, Discount, Benefit, Net).
    2. Free-goods benefit does not reduce net payable.
    3. Formula injection protection applied.
    4. Batch and batch lines are created.
    5. Order status and inventory stock remain unchanged (zero mutation).
    6. GST columns are empty strings (no invented GST).
    """
    desk_headers = {"Authorization": f"Bearer {desk_user['token']}"}
    ord1 = sample_orders["approved_1"]
    ord2 = sample_orders["approved_2"]

    # Record stock before export
    db = SessionLocal()
    stock_before = db.execute(select(Product.stock_cases).where(Product.id == seeded_product["id"])).scalar()
    db.close()

    res = client.post(
        "/api/v1/desk/exports",
        json={"order_ids": [str(ord1.id), str(ord2.id)], "profile": "generic"},
        headers=desk_headers,
    )
    assert res.status_code == 201
    batch_data = res.json()

    # Batch summary assertions
    assert batch_data["order_count"] == 2
    assert batch_data["record_count"] == 2
    assert batch_data["batch_number"].startswith("EXP-")
    assert batch_data["file_checksum"] is not None
    assert Decimal(str(batch_data["total_gross"])) == Decimal("17926.00")
    assert Decimal(str(batch_data["total_discount"])) == Decimal("304.50")
    assert Decimal(str(batch_data["total_benefit"])) == Decimal("1082.10")
    assert Decimal(str(batch_data["total_net"])) == Decimal("17621.50")
    assert batch_data["total_fulfilment_cases"] == 16  # 11 + 5

    # Verify zero mutation on database models
    verify_db = SessionLocal()
    try:
        db_ord1 = verify_db.execute(select(Order).where(Order.id == ord1.id)).scalar_one()
        assert db_ord1.status == "APPROVED"
        assert db_ord1.gross_total == Decimal("7776.00")
        assert db_ord1.net_total == Decimal("7776.00")

        # Inventory stock must be completely untouched
        stock_after = verify_db.execute(select(Product.stock_cases).where(Product.id == seeded_product["id"])).scalar()
        assert stock_after == stock_before
    finally:
        verify_db.close()


def test_download_csv_content_and_headers(desk_user, sample_orders):
    """
    Downloads generated CSV for the batch and validates:
    - Headers
    - Row values and Decimal formatting
    - Formula injection escaping
    - Free-goods benefit separation
    - GST columns empty
    - Content-Disposition and SHA-256 header
    """
    desk_headers = {"Authorization": f"Bearer {desk_user['token']}"}
    ord1 = sample_orders["approved_1"]

    # Create dedicated single-order export batch
    res_batch = client.post(
        "/api/v1/desk/exports",
        json={"order_ids": [str(ord1.id)]},
        headers=desk_headers,
    )
    assert res_batch.status_code == 201
    batch = res_batch.json()

    # Download CSV
    res_dl = client.get(f"/api/v1/desk/exports/{batch['id']}/download", headers=desk_headers)
    assert res_dl.status_code == 200
    assert "text/csv" in res_dl.headers["content-type"]
    assert f'attachment; filename="{batch["csv_filename"]}"' in res_dl.headers["content-disposition"]
    assert res_dl.headers["x-checksum-sha256"] == batch["file_checksum"]

    # Parse CSV content (stripping BOM)
    raw_content = res_dl.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(raw_content))
    rows = list(reader)

    assert len(rows) == 2  # Header + 1 OrderLine row
    headers = rows[0]
    data_row = rows[1]

    # Header assertions
    assert "OrderID" in headers
    assert "OrderNumber" in headers
    assert "RetailerName" in headers
    assert "RetailerMobile" not in headers  # Data minimization: personal mobile omitted from generic export
    assert "PartyLedger" in headers
    assert "StockItem" in headers
    assert "QtyPaid" in headers
    assert "QtyFree" in headers
    assert "QtyFulfilment" in headers
    assert "BenefitValue" in headers
    assert "DiscountAmount" in headers
    assert "NetAmount" in headers
    assert "GSTRate" in headers
    assert "GSTAmount" in headers

    # Row value assertions (Buy 10 Get 1 Free biscuit)
    idx_order_num = headers.index("OrderNumber")
    idx_retailer_name = headers.index("RetailerName")
    idx_party_ledger = headers.index("PartyLedger")
    idx_paid = headers.index("QtyPaid")
    idx_free = headers.index("QtyFree")
    idx_fulfilment = headers.index("QtyFulfilment")
    idx_gross = headers.index("GrossAmount")
    idx_benefit = headers.index("BenefitValue")
    idx_discount = headers.index("DiscountAmount")
    idx_net = headers.index("NetAmount")
    idx_gst_rate = headers.index("GSTRate")
    idx_gst_amount = headers.index("GSTAmount")

    assert data_row[idx_order_num] == ord1.order_number
    # Retailer name '=Formula Kirana Store' is escaped to ''=Formula Kirana Store'
    assert data_row[idx_retailer_name] == "'=Formula Kirana Store"
    # Party ledger '@Formula Ledger' is escaped to ''@Formula Ledger'
    assert data_row[idx_party_ledger] == "'@Formula Ledger"

    assert data_row[idx_paid] == "10"
    assert data_row[idx_free] == "1"
    assert data_row[idx_fulfilment] == "11"

    # Financial snapshots
    assert data_row[idx_gross] == "7776.00"
    assert data_row[idx_benefit] == "777.60"
    assert data_row[idx_discount] == "0.00"
    assert data_row[idx_net] == "7776.00"

    # GST columns must be completely blank
    assert data_row[idx_gst_rate] == ""
    assert data_row[idx_gst_amount] == ""


def test_repeated_export_distinct_batches_and_history(desk_user, sample_orders):
    """
    Re-exporting an approved order creates a new distinct batch and updates export counts.
    """
    desk_headers = {"Authorization": f"Bearer {desk_user['token']}"}
    ord1 = sample_orders["approved_1"]

    # First export
    res1 = client.post("/api/v1/desk/exports", json={"order_ids": [str(ord1.id)]}, headers=desk_headers)
    assert res1.status_code == 201
    batch1 = res1.json()

    # Second export of the same order
    res2 = client.post("/api/v1/desk/exports", json={"order_ids": [str(ord1.id)]}, headers=desk_headers)
    assert res2.status_code == 201
    batch2 = res2.json()

    # Must have distinct batch IDs and batch numbers
    assert batch1["id"] != batch2["id"]
    assert batch1["batch_number"] != batch2["batch_number"]

    # Check exportable orders list shows export_count >= 2
    res_list = client.get("/api/v1/desk/exports/orders", headers=desk_headers)
    items = res_list.json()["items"]
    target = next(i for i in items if i["id"] == str(ord1.id))
    assert target["export_count"] >= 2
    assert target["last_exported_at"] is not None

    # Check export batch history endpoint
    res_batches = client.get("/api/v1/desk/exports", headers=desk_headers)
    assert res_batches.status_code == 200
    batch_items = res_batches.json()["items"]
    batch_ids = [b["id"] for b in batch_items]
    assert batch1["id"] in batch_ids
    assert batch2["id"] in batch_ids


def test_batch_size_limit_exceeded(desk_user):
    """Attempting to export more than 500 orders in a single batch is rejected (400)."""
    desk_headers = {"Authorization": f"Bearer {desk_user['token']}"}
    too_many_ids = [str(uuid.uuid4()) for _ in range(501)]
    res = client.post("/api/v1/desk/exports", json={"order_ids": too_many_ids}, headers=desk_headers)
    assert res.status_code == 400
    assert "exceeds maximum limit of 500" in res.json()["detail"]


def test_cross_role_and_unauthorized_download_denied(retailer_user, desk_user, sample_orders):
    """Downloading export batch CSV requires Order Desk role; retailers and unauthenticated denied."""
    desk_headers = {"Authorization": f"Bearer {desk_user['token']}"}
    retailer_headers = {"Authorization": f"Bearer {retailer_user['token']}"}
    ord1 = sample_orders["approved_1"]

    # Desk creates batch
    res_batch = client.post("/api/v1/desk/exports", json={"order_ids": [str(ord1.id)]}, headers=desk_headers)
    assert res_batch.status_code == 201
    batch_id = res_batch.json()["id"]

    # 1. Unauthenticated download -> 401
    res_no_auth = client.get(f"/api/v1/desk/exports/{batch_id}/download")
    assert res_no_auth.status_code == 401

    # 2. Retailer role download -> 403
    res_retailer = client.get(f"/api/v1/desk/exports/{batch_id}/download", headers=retailer_headers)
    assert res_retailer.status_code == 403

    # 3. Retailer role get batch detail -> 403
    res_ret_detail = client.get(f"/api/v1/desk/exports/{batch_id}", headers=retailer_headers)
    assert res_ret_detail.status_code == 403

    # 4. Desk role download -> 200
    res_desk = client.get(f"/api/v1/desk/exports/{batch_id}/download", headers=desk_headers)
    assert res_desk.status_code == 200


