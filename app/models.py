import uuid
import enum
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey,
    Numeric, Integer, Date, Text, Enum as SAEnum, BigInteger,
    CheckConstraint, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


# ── ENUMS ────────────────────────────────────────────────────────────────────

class EmployeeRole(str, enum.Enum):
    admin = "admin"
    engineer = "engineer"
    storekeeper = "storekeeper"
    viewer = "viewer"
    auditor = "auditor"


class EquipmentStatus(str, enum.Enum):
    active = "active"
    maintenance = "maintenance"
    requires_maintenance = "requires_maintenance"
    decommissioned = "decommissioned"
    in_repair = "in_repair"
    storage = "storage"


class TaskType(str, enum.Enum):
    preventive = "preventive"
    corrective = "corrective"
    inspection = "inspection"


class TaskStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class AuditOperation(str, enum.Enum):
    I = "I"
    U = "U"
    D = "D"


# ── CORE SCHEMA ──────────────────────────────────────────────────────────────

class Department(Base):
    __tablename__ = "departments"
    __table_args__ = {"schema": "core"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    employees = relationship("Employee", back_populates="department")
    managers = relationship("DepartmentManager", back_populates="department")


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = {"schema": "core"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String(300), nullable=False)
    role = Column(SAEnum(EmployeeRole, schema="core", name="employee_role"), nullable=False)
    email = Column(String(254), nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    department_id = Column(UUID(as_uuid=True), ForeignKey("core.departments.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    department = relationship("Department", back_populates="employees")
    managed_departments = relationship("DepartmentManager", back_populates="employee")
    assigned_tasks = relationship("MaintenanceTask", back_populates="assigned_employee")
    responsible_equipment = relationship("Equipment", back_populates="responsible_employee")


class DepartmentManager(Base):
    __tablename__ = "department_managers"
    __table_args__ = {"schema": "core"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_id = Column(UUID(as_uuid=True), ForeignKey("core.departments.id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("core.employees.id", ondelete="CASCADE"), nullable=False)
    effective_from = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    effective_to = Column(DateTime(timezone=True), nullable=True)

    department = relationship("Department", back_populates="managers")
    employee = relationship("Employee", back_populates="managed_departments")


# ── INVENTORY SCHEMA ─────────────────────────────────────────────────────────

class Location(Base):
    __tablename__ = "locations"
    __table_args__ = {"schema": "inventory"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(300), nullable=False)
    address = Column(Text, nullable=True)
    parent_location_id = Column(UUID(as_uuid=True), ForeignKey("inventory.locations.id", ondelete="SET NULL"), nullable=True)

    children = relationship("Location", backref="parent", remote_side=[id])
    equipment = relationship("Equipment", back_populates="location")


class EquipmentType(Base):
    __tablename__ = "equipment_types"
    __table_args__ = {"schema": "inventory"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False, unique=True)
    maintenance_interval_hours = Column(Integer, nullable=False, default=2000)
    depreciation_years = Column(Numeric(4, 1), nullable=False, default=5.0)

    equipment = relationship("Equipment", back_populates="equipment_type")


class Equipment(Base):
    __tablename__ = "equipment"
    __table_args__ = {"schema": "inventory"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    serial_number = Column(String(100), nullable=False, unique=True)
    inventory_number = Column(String(100), nullable=True, unique=True)
    name = Column(String(300), nullable=False)
    equipment_type_id = Column(UUID(as_uuid=True), ForeignKey("inventory.equipment_types.id"), nullable=False)
    location_id = Column(UUID(as_uuid=True), ForeignKey("inventory.locations.id"), nullable=True)
    responsible_employee_id = Column(UUID(as_uuid=True), ForeignKey("core.employees.id"), nullable=True)
    status = Column(
        SAEnum(EquipmentStatus, schema="inventory", name="equipment_status"),
        nullable=False, default=EquipmentStatus.active
    )
    purchase_cost = Column(Numeric(15, 2), nullable=False)
    residual_value = Column(Numeric(15, 2), nullable=True)
    purchase_date = Column(Date, nullable=False)
    operation_hours = Column(Integer, nullable=False, default=0)
    characteristics = Column(JSONB, nullable=False, default=dict)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    equipment_type = relationship("EquipmentType", back_populates="equipment")
    location = relationship("Location", back_populates="equipment")
    responsible_employee = relationship("Employee", back_populates="responsible_equipment")
    telemetry = relationship("Telemetry", back_populates="equipment", cascade="all, delete-orphan")
    maintenance_tasks = relationship("MaintenanceTask", back_populates="equipment", cascade="all, delete-orphan")


# ── MONITORING SCHEMA ─────────────────────────────────────────────────────────

class Telemetry(Base):
    # БАГ ИСПРАВЛЕН: было "telemetry_y2026" — это партиция, а не родительская таблица.
    # SQLAlchemy должен работать с родительской таблицей monitoring.telemetry,
    # PostgreSQL сам маршрутизирует INSERT в нужную партицию.
    __tablename__ = "telemetry"
    __table_args__ = {"schema": "monitoring"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    equipment_id = Column(UUID(as_uuid=True), ForeignKey("inventory.equipment.id", ondelete="CASCADE"), nullable=False)
    metric_name = Column(String(100), nullable=False)
    value = Column(Numeric(20, 6), nullable=False)
    recorded_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    equipment = relationship("Equipment", back_populates="telemetry")


class MaintenanceTask(Base):
    __tablename__ = "maintenance_tasks"
    __table_args__ = {"schema": "monitoring"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    equipment_id = Column(UUID(as_uuid=True), ForeignKey("inventory.equipment.id", ondelete="CASCADE"), nullable=False)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("core.employees.id"), nullable=True)
    task_type = Column(SAEnum(TaskType, schema="monitoring", name="task_type"), nullable=False)
    status = Column(SAEnum(TaskStatus, schema="monitoring", name="task_status"), nullable=False, default=TaskStatus.open)
    description = Column(Text, nullable=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    cost = Column(Numeric(15, 2), nullable=True, default=0)

    equipment = relationship("Equipment", back_populates="maintenance_tasks")
    assigned_employee = relationship("Employee", back_populates="assigned_tasks")


# ── ARCHIVE SCHEMA ────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "archive"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    schema_name = Column(String(63), nullable=False)
    table_name = Column(String(63), nullable=False)
    record_id = Column(UUID(as_uuid=True), nullable=False)
    operation = Column(SAEnum(AuditOperation, schema="archive", name="audit_operation"), nullable=False)
    old_data = Column(JSONB, nullable=True)
    new_data = Column(JSONB, nullable=True)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    performed_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
