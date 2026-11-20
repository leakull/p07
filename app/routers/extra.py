"""Combined router module: dashboard, audit log, employees."""
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    Equipment, MaintenanceTask, AuditLog, Employee, Department,
    EquipmentStatus, TaskStatus
)
from app.schemas import (
    AuditLogOut, DashboardStats, EmployeeCreate, EmployeeUpdate, EmployeeOut,
    DepartmentCreate, DepartmentOut, PaginatedResponse
)
from app.routers.auth import require_permission, get_password_hash

# ── DASHBOARD ─────────────────────────────────────────────────────────────────
dashboard_router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@dashboard_router.get("/stats", response_model=DashboardStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    # Equipment counts by status
    eq_status_q = select(Equipment.status, func.count().label("cnt")).group_by(Equipment.status)
    eq_rows = (await db.execute(eq_status_q)).all()
    by_status = {r.status.value: r.cnt for r in eq_rows}

    total_eq = sum(by_status.values())

    # Equipment by type
    from app.models import EquipmentType
    eq_type_q = (
        select(EquipmentType.name, func.count(Equipment.id).label("cnt"))
        .join(Equipment, Equipment.equipment_type_id == EquipmentType.id)
        .group_by(EquipmentType.name)
    )
    eq_type_rows = (await db.execute(eq_type_q)).all()
    by_type = {r.name: r.cnt for r in eq_type_rows}

    # Task stats
    task_status_q = select(MaintenanceTask.status, func.count().label("cnt")).group_by(MaintenanceTask.status)
    task_rows = (await db.execute(task_status_q)).all()
    by_task_status = {r.status.value: r.cnt for r in task_rows}

    # Tasks by type
    task_type_q = select(MaintenanceTask.task_type, func.count().label("cnt")).group_by(MaintenanceTask.task_type)
    task_type_rows = (await db.execute(task_type_q)).all()
    by_task_type = {r.task_type.value: r.cnt for r in task_type_rows}

    # Financial
    fin_q = select(func.sum(Equipment.purchase_cost), func.sum(Equipment.residual_value))
    fin_row = (await db.execute(fin_q)).one()

    # Recent telemetry metrics
    from app.models import Telemetry
    from sqlalchemy import distinct
    metrics_q = select(distinct(Telemetry.metric_name)).limit(10)
    metrics = (await db.execute(metrics_q)).scalars().all()

    # Completed this month
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    completed_month = (await db.execute(
        select(func.count()).where(
            MaintenanceTask.status == TaskStatus.completed,
            MaintenanceTask.completed_at >= month_start,
        )
    )).scalar_one()

    return DashboardStats(
        total_equipment=total_eq,
        active_equipment=by_status.get("active", 0),
        in_repair=by_status.get("in_repair", 0),
        requires_maintenance=by_status.get("requires_maintenance", 0),
        decommissioned=by_status.get("decommissioned", 0),
        open_tasks=by_task_status.get("open", 0),
        in_progress_tasks=by_task_status.get("in_progress", 0),
        completed_tasks_month=completed_month,
        total_purchase_value=float(fin_row[0] or 0),
        total_residual_value=float(fin_row[1] or 0),
        equipment_by_status=by_status,
        equipment_by_type=by_type,
        tasks_by_type=by_task_type,
        recent_telemetry_metrics=list(metrics),
    )


# ── AUDIT LOG ─────────────────────────────────────────────────────────────────
audit_router = APIRouter(prefix="/api/audit", tags=["audit"])


@audit_router.get("", response_model=PaginatedResponse)
async def list_audit(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    table_name: Optional[str] = None,
    operation: Optional[str] = None,
    record_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    since: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("audit", "read")),
):
    q = select(AuditLog)
    if table_name:
        q = q.where(AuditLog.table_name == table_name)
    if operation:
        q = q.where(AuditLog.operation == operation)
    if record_id:
        q = q.where(AuditLog.record_id == record_id)
    if user_id:
        q = q.where(AuditLog.user_id == user_id)
    if since:
        q = q.where(AuditLog.performed_at >= since)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    q = q.offset((page - 1) * per_page).limit(per_page).order_by(AuditLog.performed_at.desc())
    items = (await db.execute(q)).scalars().all()

    return PaginatedResponse(
        items=[AuditLogOut.model_validate(a) for a in items],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


# ── EMPLOYEES ─────────────────────────────────────────────────────────────────
employees_router = APIRouter(prefix="/api/employees", tags=["employees"])
# БАГ ИСПРАВЛЕН: было passlib/bcrypt — но auth.py верифицирует через argon2.
# Пароли, установленные здесь, никогда не проходили проверку при логине.
# Теперь используем тот же get_password_hash из auth.py (argon2).


@employees_router.get("", response_model=List[EmployeeOut])
async def list_employees(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("employees", "read")),
):
    result = await db.execute(select(Employee))
    return [EmployeeOut.model_validate(e) for e in result.scalars().all()]


@employees_router.post("", response_model=EmployeeOut, status_code=201)
async def create_employee(
    body: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("employees", "write")),
):
    data = body.model_dump()
    data["password_hash"] = get_password_hash(data.pop("password"))
    obj = Employee(**data)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return EmployeeOut.model_validate(obj)


@employees_router.patch("/{emp_id}", response_model=EmployeeOut)
async def update_employee(
    emp_id: UUID,
    body: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("employees", "write")),
):
    obj = await db.get(Employee, emp_id)
    if not obj:
        raise HTTPException(404, "Employee not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(obj, k, v)
    await db.commit()
    await db.refresh(obj)
    return EmployeeOut.model_validate(obj)


# ── DEPARTMENTS ───────────────────────────────────────────────────────────────
departments_router = APIRouter(prefix="/api/departments", tags=["departments"])


@departments_router.get("", response_model=List[DepartmentOut])
async def list_departments(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Department))
    return [DepartmentOut.model_validate(d) for d in result.scalars().all()]


@departments_router.post("", response_model=DepartmentOut, status_code=201)
async def create_department(
    body: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("employees", "write")),
):
    obj = Department(name=body.name)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return DepartmentOut.model_validate(obj)
    