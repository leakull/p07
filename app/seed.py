"""
Run: python seed.py
Idempotent seed (safe to run multiple times)
"""

import asyncio
import random
from datetime import datetime, timedelta, date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import settings
from app.models import (
    Department, Employee, Location, EquipmentType, Equipment,
    MaintenanceTask, Telemetry,
    EmployeeRole, EquipmentStatus, TaskType, TaskStatus,
)
from app.routers.auth import get_password_hash


# ─────────────────────────────────────────────
# 🔧 UNIVERSAL GET OR CREATE
# ─────────────────────────────────────────────
async def get_or_create(db, model, defaults=None, **kwargs):
    result = await db.execute(select(model).filter_by(**kwargs))
    instance = result.scalars().first()

    if instance:
        return instance

    params = {**kwargs}
    if defaults:
        params.update(defaults)

    instance = model(**params)
    db.add(instance)
    await db.flush()
    return instance


# ─────────────────────────────────────────────
# 🌱 SEED
# ─────────────────────────────────────────────

async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:

        # ── Departments
        dept_names = [
            "IT Department",
            "Production",
            "Warehouse",
            "Finance",
            "Quality Control",
        ]

        depts = []
        for name in dept_names:
            dept = await get_or_create(db, Department, name=name)
            depts.append(dept)

        # ── Employees
        employees_data = [
            ("Aleksei Petrov", "admin@company.com", EmployeeRole.admin, "admin123", 0),
            ("Maria Sokolova", "engineer@company.com", EmployeeRole.engineer, "eng123", 1),
            ("Ivan Kozlov", "store@company.com", EmployeeRole.storekeeper, "store123", 2),
            ("Olga Novikova", "auditor@company.com", EmployeeRole.auditor, "audit123", 3),
            ("Dmitry Volkov", "viewer@company.com", EmployeeRole.viewer, "view123", 4),
            ("Anna Lebedeva", "engineer2@company.com", EmployeeRole.engineer, "eng123", 1),
        ]

        employees = []
        for full_name, email, role, password, dept_idx in employees_data:
            employee = await get_or_create(
                db,
                Employee,
                email=email,
                defaults={
                    "full_name": full_name,
                    "role": role,
                    "password_hash": get_password_hash(password),
                    "department_id": depts[dept_idx].id,
                }
            )
            employees.append(employee)

        # ── Locations
        locations_data = [
            ("Main Warehouse", "Industrial Zone 1, Building A"),
            ("Production Hall", "Industrial Zone 1, Building B"),
            ("Server Room", "HQ, Floor 3"),
            ("Garage", "Industrial Zone 2"),
        ]

        locations = []
        for name, addr in locations_data:
            loc = await get_or_create(db, Location, name=name, defaults={"address": addr})
            locations.append(loc)

        # дочерняя локация
        storage_b = await get_or_create(
            db,
            Location,
            name="Storage Area B",
            defaults={
                "address": "Industrial Zone 1, Building A",
                "parent_location_id": locations[0].id
            }
        )
        locations.append(storage_b)

        # ── Equipment types
        eq_types_data = [
            ("CNC Machine", 500, "10.0"),
            ("Industrial Generator", 1000, "15.0"),
            ("Forklift", 250, "7.0"),
            ("Air Compressor", 2000, "8.0"),
            ("Server", 8760, "5.0"),
            ("Conveyor Belt", 750, "12.0"),
        ]

        eq_types = []
        for name, hours, years in eq_types_data:
            et = await get_or_create(
                db,
                EquipmentType,
                name=name,
                defaults={
                    "maintenance_interval_hours": hours,
                    "depreciation_years": Decimal(years)
                }
            )
            eq_types.append(et)

        # ── Equipment (по serial_number уникальность)
        equipment_data = [
            ("CNC-A100", "SN-CNC-001", 0, 1, EquipmentStatus.active, "150000"),
            ("CNC-A101", "SN-CNC-002", 0, 1, EquipmentStatus.in_repair, "150000"),
            ("GEN-5000", "SN-GEN-001", 1, 0, EquipmentStatus.active, "320000"),
            ("FORK-01", "SN-FRK-001", 2, 3, EquipmentStatus.active, "85000"),
        ]

        equipment_list = []

        for i, (name, sn, type_idx, loc_idx, status, cost) in enumerate(equipment_data):
            eq = await get_or_create(
                db,
                Equipment,
                serial_number=sn,
                defaults={
                    "name": name,
                    "inventory_number": f"INV-2024-{i+1:04d}",
                    "equipment_type_id": eq_types[type_idx].id,
                    "location_id": locations[loc_idx].id,
                    "responsible_employee_id": employees[1].id,
                    "status": status,
                    "purchase_cost": Decimal(cost),
                    "residual_value": Decimal(cost) * Decimal("0.6"),
                    "purchase_date": date(2022, 1, 1),
                    "operation_hours": random.randint(100, 5000),
                    "characteristics": {"demo": True},
                }
            )
            equipment_list.append(eq)

        # ── Tasks
        for eq in equipment_list:
            await get_or_create(
                db,
                MaintenanceTask,
                equipment_id=eq.id,
                task_type=TaskType.preventive,
                defaults={
                    "assigned_to": employees[1].id,
                    "status": TaskStatus.in_progress,
                    "description": f"Maintenance for {eq.name}",
                    "scheduled_at": datetime.utcnow() + timedelta(days=7),
                    "cost": Decimal("0"),
                }
            )

        # ── Telemetry (НЕ идемпотентно, но ограничим)
        existing = await db.execute(select(Telemetry).limit(1))
        if not existing.scalar():
            telemetry_records = []
            now = datetime.utcnow()

            for eq in equipment_list:
                for i in range(24):
                    telemetry_records.append(Telemetry(
                        equipment_id=eq.id,
                        metric_name="temperature",
                        value=Decimal(str(random.randint(20, 80))),
                        recorded_at=now - timedelta(hours=i),
                    ))

            db.add_all(telemetry_records)

        await db.commit()

        print("✅ Seed completed safely (idempotent)")


# ─────────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(seed())