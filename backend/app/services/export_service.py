"""
Export Service and Accounting Adapter Engine for DukaanFlow (Phase 8).

Handles:
- Configurable export profiles / adapters
- Formula injection protection (CWE-1236)
- Financial snapshot extraction (immutable, Decimal-precise)
- Strict eligibility enforcement (APPROVED orders only)
- Repeat export tracking via ExportBatch & ExportBatchLine
- Excel-friendly UTF-8 CSV generation with SHA-256 checksums
"""

import csv
import io
import uuid
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select, func, desc, or_
from sqlalchemy.orm import Session, selectinload

from app.models.order import Order, OrderLine
from app.models.auth import Retailer, OrderDeskUser
from app.models.export import ExportBatch, ExportBatchLine


def sanitize_csv_field(val: Any) -> str:
    """
    Sanitize text fields against CSV / Spreadsheet formula injection (CWE-1236).
    If a string starts with =, +, -, @, tab, or carriage return (even after leading spaces),
    prepend a single quote '.
    """
    if val is None:
        return ""
    text = str(val)
    stripped = text.lstrip(" ")
    if stripped and stripped[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{text}"
    return text


def format_decimal(val: Optional[Decimal]) -> str:
    """Formats Decimal value to standard 2-decimal string e.g. 7776.00."""
    if val is None:
        return "0.00"
    return f"{Decimal(str(val)):.2f}"


class BaseExportProfile(ABC):
    """Abstract base adapter for order export formats."""

    key: str
    display_name: str
    description: str
    is_preliminary: bool = True

    @abstractmethod
    def get_headers(self) -> List[str]:
        """Returns ordered list of CSV column header names."""
        pass

    @abstractmethod
    def format_row(self, order: Order, line: OrderLine) -> List[str]:
        """Maps an Order and OrderLine snapshot to a list of string cell values."""
        pass


class GenericAccountingExportProfile(BaseExportProfile):
    """
    Standard generic accounting CSV export profile.
    
    Exports immutable order and line financial snapshots.
    NOTE: Column headers and voucher layouts are generic. Once the client
    confirms official Tally Prime import column specifications, a dedicated
    Tally voucher adapter can be added without altering order storage.
    """

    key = "generic"
    display_name = "Generic Accounting CSV (Pre-Tally)"
    description = (
        "Standard multi-line accounting format exporting immutable order snapshots, "
        "case quantities, and separated benefit values. Format is unconfirmed for direct Tally import."
    )
    is_preliminary = True

    def get_headers(self) -> List[str]:
        return [
            "OrderID",
            "OrderNumber",
            "OrderDate",
            "RetailerID",
            "RetailerName",
            "PartyLedger",
            "SKU",
            "StockItem",
            "PackSize",
            "CaseQty",
            "QtyPaid",
            "QtyFree",
            "QtyFulfilment",
            "RatePerCase",
            "GrossAmount",
            "SchemeType",
            "BenefitValue",
            "DiscountAmount",
            "NetAmount",
            "OrderStatus",
            "GSTRate",
            "GSTAmount",
        ]

    def format_row(self, order: Order, line: OrderLine) -> List[str]:
        retailer = order.retailer
        order_date_str = order.created_at.strftime("%Y-%m-%d") if order.created_at else ""
        party_ledger = retailer.tally_ledger_name if retailer and retailer.tally_ledger_name else (retailer.name if retailer else "")
        scheme_type = line.scheme_type_snapshot or "NONE"

        return [
            str(order.id),
            sanitize_csv_field(order.order_number),
            order_date_str,
            str(retailer.id) if retailer else "",
            sanitize_csv_field(retailer.name) if retailer else "",
            sanitize_csv_field(party_ledger),
            sanitize_csv_field(line.sku_snapshot),
            sanitize_csv_field(line.name_snapshot),
            sanitize_csv_field(line.pack_size_snapshot),
            str(line.case_qty_snapshot),
            str(line.qty_cases),
            str(line.free_cases),
            str(line.fulfilment_qty_cases),
            format_decimal(line.unit_price or line.price_per_case_snapshot),
            format_decimal(line.gross_amount),
            sanitize_csv_field(scheme_type),
            format_decimal(line.benefit_value),
            format_decimal(line.discount_amount),
            format_decimal(line.net_amount),
            sanitize_csv_field(order.status),
            "",  # GSTRate: unconfirmed by client (Assumption A-2)
            "",  # GSTAmount: unconfirmed by client (Assumption A-2)
        ]


# Adapter Registry
AVAILABLE_PROFILES: Dict[str, BaseExportProfile] = {
    "generic": GenericAccountingExportProfile(),
}


class ExportService:
    """Service handling Order Desk exports and export history."""

    @classmethod
    def get_profile(cls, profile_key: str = "generic") -> BaseExportProfile:
        """Retrieves profile adapter by key, raising 400 if unsupported."""
        profile = AVAILABLE_PROFILES.get(profile_key)
        if not profile:
            supported = ", ".join(AVAILABLE_PROFILES.keys())
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported export profile '{profile_key}'. Available profiles: {supported}",
            )
        return profile

    @classmethod
    def list_exportable_orders(
        cls,
        db: Session,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Lists exportable approved orders with pagination and filters.
        Only orders with status APPROVED are returned.
        """
        query = (
            select(Order)
            .options(
                selectinload(Order.lines),
                selectinload(Order.retailer),
            )
            .where(Order.status == "APPROVED")
        )

        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.join(Order.retailer).where(
                or_(
                    Order.order_number.ilike(term),
                    Retailer.name.ilike(term),
                    Retailer.mobile.ilike(term),
                    Retailer.tally_ledger_name.ilike(term),
                )
            )

        if date_from:
            dt_from = datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc)
            query = query.where(Order.created_at >= dt_from)

        if date_to:
            dt_to = datetime.combine(date_to, datetime.max.time(), tzinfo=timezone.utc)
            query = query.where(Order.created_at <= dt_to)

        # Count total
        count_stmt = select(func.count()).select_from(query.subquery())
        total = db.execute(count_stmt).scalar() or 0

        # Paginated fetch
        orders = (
            db.execute(
                query.order_by(desc(Order.created_at))
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .scalars()
            .all()
        )

        # Fetch export counts for these orders
        order_ids = [o.id for o in orders]
        export_stats: Dict[uuid.UUID, Dict[str, Any]] = {}
        if order_ids:
            stats_query = (
                select(
                    ExportBatchLine.order_id,
                    func.count(ExportBatchLine.id).label("export_count"),
                    func.max(ExportBatchLine.created_at).label("last_exported_at"),
                )
                .where(ExportBatchLine.order_id.in_(order_ids))
                .group_by(ExportBatchLine.order_id)
            )
            for row in db.execute(stats_query):
                export_stats[row.order_id] = {
                    "export_count": row.export_count,
                    "last_exported_at": row.last_exported_at,
                }

        items = []
        for o in orders:
            stats_info = export_stats.get(o.id, {"export_count": 0, "last_exported_at": None})
            items.append({
                "id": o.id,
                "order_number": o.order_number,
                "created_at": o.created_at,
                "status": o.status,
                "retailer_id": o.retailer_id,
                "retailer_name": o.retailer.name if o.retailer else "",
                "retailer_mobile": o.retailer.mobile if o.retailer else "",
                "tally_ledger_name": o.retailer.tally_ledger_name if o.retailer else None,
                "total_cases": o.total_cases,
                "total_free_cases": o.total_free_cases,
                "total_fulfilment_cases": o.total_fulfilment_cases,
                "gross_total": o.gross_total,
                "discount_total": o.discount_total,
                "benefit_total": o.benefit_total,
                "net_total": o.net_total,
                "export_count": stats_info["export_count"],
                "last_exported_at": stats_info["last_exported_at"],
                "lines_count": len(o.lines),
            })

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    @classmethod
    def create_export_batch(
        cls,
        db: Session,
        desk_user_id: uuid.UUID,
        order_ids: List[uuid.UUID],
        profile_key: str = "generic",
    ) -> ExportBatch:
        """
        Validates orders, generates CSV according to the selected profile,
        records ExportBatch and ExportBatchLine entries in an atomic transaction.
        
        Strict rules:
        - Only APPROVED orders can be exported (raises 400/422 if not APPROVED).
        - Order financials must come strictly from immutable snapshot fields.
        - The export must never mutate order records, stock, or status.
        """
        if not order_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one order must be selected for export",
            )

        # Remove duplicate IDs while preserving order
        unique_order_ids = list(dict.fromkeys(order_ids))
        if len(unique_order_ids) > 500:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch size exceeds maximum limit of 500 orders per export.",
            )
        profile = cls.get_profile(profile_key)

        # Verify desk user exists
        user = db.execute(
            select(OrderDeskUser).where(OrderDeskUser.id == desk_user_id)
        ).scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order Desk user not found",
            )

        # Fetch requested orders with snapshots
        stmt = (
            select(Order)
            .options(
                selectinload(Order.lines),
                selectinload(Order.retailer),
            )
            .where(Order.id.in_(unique_order_ids))
        )
        orders = db.execute(stmt).scalars().all()
        found_map = {o.id: o for o in orders}

        # Validate that all requested order IDs exist
        missing_ids = [str(oid) for oid in unique_order_ids if oid not in found_map]
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Orders not found: {', '.join(missing_ids)}",
            )

        # Validate that all selected orders are APPROVED
        ineligible_orders = [
            f"{o.order_number} ({o.status})"
            for o in orders
            if o.status != "APPROVED"
        ]
        if ineligible_orders:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Only APPROVED orders can be exported. Ineligible orders: {', '.join(ineligible_orders)}"
                ),
            )

        # Sort orders in the order of the requested IDs
        ordered_list = [found_map[oid] for oid in unique_order_ids]

        # Calculate batch aggregate totals from immutable snapshots
        total_gross = Decimal("0.00")
        total_discount = Decimal("0.00")
        total_benefit = Decimal("0.00")
        total_net = Decimal("0.00")
        total_fulfilment_cases = 0
        record_count = 0

        # Generate CSV content using StringIO
        output = io.StringIO()
        # Add UTF-8 BOM so Excel opens Hindi / Unicode text correctly without mojibake
        output.write("\ufeff")
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")

        # Write header
        writer.writerow(profile.get_headers())

        # Write data rows
        for order in ordered_list:
            total_gross += order.gross_total
            total_discount += order.discount_total
            total_benefit += order.benefit_total
            total_net += order.net_total
            total_fulfilment_cases += order.total_fulfilment_cases

            for line in order.lines:
                row = profile.format_row(order, line)
                writer.writerow(row)
                record_count += 1

        csv_content = output.getvalue()
        output.close()

        # Compute SHA-256 checksum
        file_checksum = hashlib.sha256(csv_content.encode("utf-8")).hexdigest()

        # Generate unique batch number and filename
        now_utc = datetime.now(timezone.utc)
        batch_seq = uuid.uuid4().hex[:6].upper()
        batch_number = f"EXP-{now_utc.strftime('%Y%m%d')}-{batch_seq}"
        csv_filename = f"dukaanflow_{profile.key}_{batch_number}.csv"

        # Persist batch and batch lines atomically
        try:
            batch = ExportBatch(
                batch_number=batch_number,
                export_profile=profile.key,
                generated_by=desk_user_id,
                order_count=len(ordered_list),
                record_count=record_count,
                total_gross=total_gross,
                total_discount=total_discount,
                total_benefit=total_benefit,
                total_net=total_net,
                total_fulfilment_cases=total_fulfilment_cases,
                csv_filename=csv_filename,
                csv_content=csv_content,
                file_checksum=file_checksum,
            )
            db.add(batch)
            db.flush()  # allocate batch.id

            for order in ordered_list:
                line_entry = ExportBatchLine(
                    batch_id=batch.id,
                    order_id=order.id,
                    order_number_snapshot=order.order_number,
                    order_net_total=order.net_total,
                )
                db.add(line_entry)

            db.commit()
            db.refresh(batch)
            return batch
        except Exception:
            db.rollback()
            raise

    @classmethod
    def get_export_batch(cls, db: Session, batch_id: uuid.UUID) -> ExportBatch:
        """Retrieves single export batch with lines and generator user."""
        stmt = (
            select(ExportBatch)
            .options(
                selectinload(ExportBatch.generator),
                selectinload(ExportBatch.batch_lines),
            )
            .where(ExportBatch.id == batch_id)
        )
        batch = db.execute(stmt).scalar_one_or_none()
        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Export batch {batch_id} not found",
            )
        return batch

    @classmethod
    def list_export_batches(
        cls,
        db: Session,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Lists historical export batches with pagination."""
        query = (
            select(ExportBatch)
            .options(
                selectinload(ExportBatch.generator),
                selectinload(ExportBatch.batch_lines),
            )
        )
        count_stmt = select(func.count(ExportBatch.id))
        total = db.execute(count_stmt).scalar() or 0

        batches = (
            db.execute(
                query.order_by(desc(ExportBatch.generated_at))
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .scalars()
            .all()
        )

        items = []
        for b in batches:
            items.append({
                "id": b.id,
                "batch_number": b.batch_number,
                "export_profile": b.export_profile,
                "generated_by": b.generated_by,
                "generator_name": b.generator.full_name if b.generator else "Order Desk",
                "generated_at": b.generated_at,
                "order_count": b.order_count,
                "record_count": b.record_count,
                "total_gross": b.total_gross,
                "total_discount": b.total_discount,
                "total_benefit": b.total_benefit,
                "total_net": b.total_net,
                "total_fulfilment_cases": b.total_fulfilment_cases,
                "csv_filename": b.csv_filename,
                "file_checksum": b.file_checksum,
            })

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

