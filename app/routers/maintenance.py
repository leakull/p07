from typing import Optional, List
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import MaintenanceTask, Equipment, Employee, TaskStatus
from app.schemas import (
    MaintenanceTaskCreate, MaintenanceTaskUpdate, MaintenanceTaskOut, PaginatedResponse
)
from app.routers.auth import require_permission

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


def _to_out(t: MaintenanceTask) -> MaintenanceTaskOut:
    out = MaintenanceTaskOut.model_validate(t)
    if t.equipment:
        out.equipment_name = t.equipment.name
    if t.assigned_employee:
        out.assigned_name = t.assigned_employee.full_name
    return out


@router.get("", response_model=PaginatedResponse)
async def list_tasks(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    equipment_id: Optional[UUID] = None,
    assigned_to: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(MaintenanceTask).options(
        selectinload(MaintenanceTask.equipment),
        selectinload(MaintenanceTask.assigned_employee),
    )
    if status:
        q = q.where(MaintenanceTask.status == status)
    if task_type:
        q = q.where(MaintenanceTask.task_type == task_type)
    if equipment_id:
        q = q.where(MaintenanceTask.equipment_id == equipment_id)
    if assigned_to:
        q = q.where(MaintenanceTask.assigned_to == assigned_to)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    q = q.offset((page - 1) * per_page).limit(per_page).order_by(MaintenanceTask.scheduled_at.desc())
    items = (await db.execute(q)).scalars().all()

    return PaginatedResponse(
        items=[_to_out(t) for t in items],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@router.post("", response_model=MaintenanceTaskOut, status_code=201)
async def create_task(
    body: MaintenanceTaskCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("maintenance", "write")),
):
    eq = await db.get(Equipment, body.equipment_id)
    if not eq:
        raise HTTPException(404, "Equipment not found")

    obj = MaintenanceTask(**body.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj, ["equipment", "assigned_employee"])
    return _to_out(obj)


@router.get("/stats")
async def task_stats(db: AsyncSession = Depends(get_db)):
    q = select(MaintenanceTask.status, func.count().label("cnt")).group_by(MaintenanceTask.status)
    rows = (await db.execute(q)).all()
    by_status = {r.status.value: r.cnt for r in rows}

    q2 = select(MaintenanceTask.task_type, func.count().label("cnt")).group_by(MaintenanceTask.task_type)
    rows2 = (await db.execute(q2)).all()
    by_type = {r.task_type.value: r.cnt for r in rows2}

    total_cost = (await db.execute(select(func.sum(MaintenanceTask.cost)).where(MaintenanceTask.status == TaskStatus.completed))).scalar_one()

    return {
        "by_status": by_status,
        "by_type": by_type,
        "total_completed_cost": float(total_cost or 0),
    }


@router.get("/{task_id}", response_model=MaintenanceTaskOut)
async def get_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    q = await db.execute(
        select(MaintenanceTask)
        .options(selectinload(MaintenanceTask.equipment), selectinload(MaintenanceTask.assigned_employee))
        .where(MaintenanceTask.id == task_id)
    )
    obj = q.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Task not found")
    return _to_out(obj)


@router.patch("/{task_id}", response_model=MaintenanceTaskOut)
async def update_task(
    task_id: UUID,
    body: MaintenanceTaskUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("maintenance", "write")),
):
    q = await db.execute(
        select(MaintenanceTask)
        .options(selectinload(MaintenanceTask.equipment), selectinload(MaintenanceTask.assigned_employee))
        .where(MaintenanceTask.id == task_id)
    )
    obj = q.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Task not found")

    updates = body.model_dump(exclude_none=True)
    if "status" in updates and updates["status"] == TaskStatus.completed.value and not obj.completed_at:
        obj.completed_at = datetime.utcnow()

    for k, v in updates.items():
        setattr(obj, k, v)

    await db.commit()
    await db.refresh(obj, ["equipment", "assigned_employee"])
    return _to_out(obj)


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("maintenance", "write")),
):
    q = await db.execute(select(MaintenanceTask).where(MaintenanceTask.id == task_id))
    obj = q.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Task not found")
    await db.delete(obj)
    await db.commit()
