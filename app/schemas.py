from __future__ import annotations
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Any, Dict, List
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models import EmployeeRole, EquipmentStatus, TaskType, TaskStatus, AuditOperation


# ── AUTH ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: str
    full_name: str


# ── DEPARTMENT ────────────────────────────────────────────────────────────────

class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    created_at: datetime


class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


# ── EMPLOYEE ──────────────────────────────────────────────────────────────────

class EmployeeCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=300)
    role: EmployeeRole
    email: EmailStr
    password: str = Field(..., min_length=6)
    department_id: Optional[UUID] = None
    is_active: bool = True


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[EmployeeRole] = None
    department_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    full_name: str
    role: EmployeeRole
    email: str
    department_id: Optional[UUID]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ── LOCATION ──────────────────────────────────────────────────────────────────

class LocationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    address: Optional[str] = None
    parent_location_id: Optional[UUID] = None


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    address: Optional[str]
    parent_location_id: Optional[UUID]


# ── EQUIPMENT TYPE ────────────────────────────────────────────────────────────

class EquipmentTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    maintenance_interval_hours: int = Field(2000, gt=0)
    depreciation_years: Decimal = Field(Decimal("5.0"), gt=0)


class EquipmentTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    maintenance_interval_hours: int
    depreciation_years: Decimal


# ── EQUIPMENT ─────────────────────────────────────────────────────────────────

class EquipmentCreate(BaseModel):
    serial_number: str = Field(..., min_length=1, max_length=100)
    inventory_number: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=300)
    equipment_type_id: UUID
    location_id: Optional[UUID] = None
    responsible_employee_id: Optional[UUID] = None
    status: EquipmentStatus = EquipmentStatus.active
    purchase_cost: Decimal = Field(..., ge=0)
    residual_value: Optional[Decimal] = None
    purchase_date: date
    operation_hours: int = 0
    characteristics: Dict[str, Any] = {}


class EquipmentUpdate(BaseModel):
    name: Optional[str] = None
    location_id: Optional[UUID] = None
    responsible_employee_id: Optional[UUID] = None
    status: Optional[EquipmentStatus] = None
    residual_value: Optional[Decimal] = None
    operation_hours: Optional[int] = None
    characteristics: Optional[Dict[str, Any]] = None


class EquipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    serial_number: str
    inventory_number: Optional[str]
    name: str
    equipment_type_id: UUID
    location_id: Optional[UUID]
    responsible_employee_id: Optional[UUID]
    status: EquipmentStatus
    purchase_cost: Decimal
    residual_value: Optional[Decimal]
    purchase_date: date
    operation_hours: int
    characteristics: Dict[str, Any]
    updated_at: datetime
    # Joined
    equipment_type_name: Optional[str] = None
    location_name: Optional[str] = None
    responsible_name: Optional[str] = None


class EquipmentMoveRequest(BaseModel):
    location_id: UUID
    reason: Optional[str] = None


class EquipmentDecommissionRequest(BaseModel):
    reason: str = Field(..., min_length=1)


# ── TELEMETRY ─────────────────────────────────────────────────────────────────

class TelemetryCreate(BaseModel):
    equipment_id: UUID
    metric_name: str = Field(..., min_length=1, max_length=100)
    value: Decimal
    recorded_at: Optional[datetime] = None


class TelemetryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    equipment_id: UUID
    metric_name: str
    value: Decimal
    recorded_at: datetime


class TelemetryChartPoint(BaseModel):
    timestamp: str
    value: float


class TelemetryChartData(BaseModel):
    metric_name: str
    equipment_name: str
    points: List[TelemetryChartPoint]


# ── MAINTENANCE TASK ──────────────────────────────────────────────────────────

class MaintenanceTaskCreate(BaseModel):
    equipment_id: UUID
    assigned_to: Optional[UUID] = None
    task_type: TaskType
    description: Optional[str] = None
    scheduled_at: datetime
    cost: Optional[Decimal] = Decimal("0")


class MaintenanceTaskUpdate(BaseModel):
    assigned_to: Optional[UUID] = None
    task_type: Optional[TaskType] = None
    status: Optional[TaskStatus] = None
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cost: Optional[Decimal] = None


class MaintenanceTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    equipment_id: UUID
    assigned_to: Optional[UUID]
    task_type: TaskType
    status: TaskStatus
    description: Optional[str]
    scheduled_at: datetime
    completed_at: Optional[datetime]
    cost: Optional[Decimal]
    # Joined
    equipment_name: Optional[str] = None
    assigned_name: Optional[str] = None


# ── AUDIT LOG ─────────────────────────────────────────────────────────────────

class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    schema_name: str
    table_name: str
    record_id: UUID
    operation: AuditOperation
    old_data: Optional[Dict[str, Any]]
    new_data: Optional[Dict[str, Any]]
    user_id: Optional[UUID]
    performed_at: datetime


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_equipment: int
    active_equipment: int
    in_repair: int
    requires_maintenance: int
    decommissioned: int
    open_tasks: int
    in_progress_tasks: int
    completed_tasks_month: int
    total_purchase_value: float
    total_residual_value: float
    equipment_by_status: Dict[str, int]
    equipment_by_type: Dict[str, int]
    tasks_by_type: Dict[str, int]
    recent_telemetry_metrics: List[str]


# ── PAGINATION ────────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    per_page: int
    pages: int
    