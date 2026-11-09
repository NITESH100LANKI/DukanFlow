"""
Seed script for initial authentication data:
- 2 test Kirana retailers
- 1 test Order Desk staff user
"""

import sys
import os

# Add backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.auth import Retailer, OrderDeskUser


def seed_auth():
    db = SessionLocal()
    try:
        # 1. Seed Retailer 1
        r1_mobile = "9876543210"
        r1 = db.execute(select(Retailer).where(Retailer.mobile == r1_mobile)).scalar_one_or_none()
        if not r1:
            r1 = Retailer(
                mobile=r1_mobile,
                name="Sharma Kirana Store",
                address="124 Gol Bazar, Jabalpur, MP",
                tally_ledger_name="Sharma Kirana Jabalpur",
                credit_limit=50000.0,
                is_active=True,
            )
            db.add(r1)
            print(f"Created Retailer 1: {r1.name} (+91 {r1.mobile})")
        else:
            print(f"Retailer 1 already exists: (+91 {r1.mobile})")

        # 2. Seed Retailer 2
        r2_mobile = "9826112233"
        r2 = db.execute(select(Retailer).where(Retailer.mobile == r2_mobile)).scalar_one_or_none()
        if not r2:
            r2 = Retailer(
                mobile=r2_mobile,
                name="Gupta General Stores",
                address="45 Gorakhpur Main Rd, Jabalpur, MP",
                tally_ledger_name="Gupta General Jabalpur",
                credit_limit=75000.0,
                is_active=True,
            )
            db.add(r2)
            print(f"Created Retailer 2: {r2.name} (+91 {r2.mobile})")
        else:
            print(f"Retailer 2 already exists: (+91 {r2.mobile})")

        # 3. Seed Order Desk User
        desk_email = "desk@dukaanflow.in"
        desk_user = db.execute(select(OrderDeskUser).where(OrderDeskUser.email == desk_email)).scalar_one_or_none()
        if not desk_user:
            desk_user = OrderDeskUser(
                email=desk_email,
                password_hash=get_password_hash("DeskSecret123"),
                full_name="Ramesh Verma (Order Desk Manager)",
                is_active=True,
            )
            db.add(desk_user)
            print(f"Created Order Desk user: {desk_user.email} (Password: DeskSecret123)")
        else:
            print(f"Order Desk user already exists: {desk_user.email}")

        db.commit()
        print("Seed completed successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_auth()

