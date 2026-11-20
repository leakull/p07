from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Equipment, EquipmentType, Location, Employee, AuditLog, AuditOperation, EquipmentStatus
from app.schemas import (
    EquipmentCreate, EquipmentUpdate, EquipmentOut,
    EquipmentMoveRequest, EquipmentDecommissionRequest,
    EquipmentTypeCreate, EquipmentTypeOut,
    LocationCreate, LocationOut,
    PaginatedResponse,
)
from app.routers.auth import require_user, require_permission
from datetime import datetime

router = APIRouter(prefix="/api/equipment", tags=["equipment"])


def _to_out(eq: Equipment) -> EquipmentOut:
    out = EquipmentOut.model_validate(eq)
    if eq.equipment_type:
        out.equipment_type_name = eq.equipment_type.name
    if eq.location:
        out.location_name = eq.location.name
    if eq.responsible_employee:
        out.responsible_name = eq.responsible_employee.full_name
    return out


async def _log_audit(db, table, record_id, op, old=None, new_data=None, user_id=None):
    log = AuditLog(
        schema_name="inventory",
        table_name=table,
        record_id=record_id,
        operation=op,
        old_data=old,
        new_data=new_data,
        user_id=user_id,
        performed_at=datetime.utcnow(),
    )
    db.add(log)


# ── EQUIPMENT TYPES ───────────────────────────────────────────────────────────

@router.get("/types", response_model=List[EquipmentTypeOut])
async def list_types(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EquipmentType))
    return [EquipmentTypeOut.model_validate(t) for t in result.scalars().all()]


@router.post("/types", response_model=EquipmentTypeOut)
async def create_type(
    body: EquipmentTypeCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("equipment", "write")),
):
    obj = EquipmentType(**body.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return EquipmentTypeOut.model_validate(obj)


# ── LOCATIONS ─────────────────────────────────────────────────────────────────

@router.get("/locations", response_model=List[LocationOut])
async def list_locations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Location))
    return [LocationOut.model_validate(l) for l in result.scalars().all()]


@router.post("/locations", response_model=LocationOut)
async def create_location(
    body: LocationCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("locations", "write")),
):
    obj = Location(**body.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return LocationOut.model_validate(obj)


# ── EQUIPMENT CRUD ────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedResponse)
async def list_equipment(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    type_id: Optional[UUID] = None,
    location_id: Optional[UUID] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Equipment).options(
        selectinload(Equipment.equipment_type),
        selectinload(Equipment.location),
        selectinload(Equipment.responsible_employee),
    )
    if status:
        q = q.where(Equipment.status == status)
    if type_id:
        q = q.where(Equipment.equipment_type_id == type_id)
    if location_id:
        q = q.where(Equipment.location_id == location_id)
    if search:
        q = q.where(
            Equipment.name.ilike(f"%{search}%") |
            Equipment.serial_number.ilike(f"%{search}%") |
            Equipment.inventory_number.ilike(f"%{search}%")
        )

    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar_one()

    q = q.offset((page - 1) * per_page).limit(per_page).order_by(Equipment.updated_at.desc())
    items = (await db.execute(q)).scalars().all()

    return PaginatedResponse(
        items=[_to_out(eq) for eq in items],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@router.post("", response_model=EquipmentOut, status_code=201)
async def create_equipment(
    body: EquipmentCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("equipment", "write")),
):
    obj = Equipment(**body.model_dump())
    db.add(obj)
    await db.flush()
    await _log_audit(db, "equipment", obj.id, AuditOperation.I, new_data=body.model_dump(mode="json"), user_id=user.id)
    await db.commit()
    await db.refresh(obj, ["equipment_type", "location", "responsible_employee"])
    return _to_out(obj)


@router.get("/{eq_id}", response_model=EquipmentOut)
async def get_equipment(eq_id: UUID, db: AsyncSession = Depends(get_db)):
    q = await db.execute(
        select(Equipment)
        .options(
            selectinload(Equipment.equipment_type),
            selectinload(Equipment.location),
            selectinload(Equipment.responsible_employee),
        )
        .where(Equipment.id == eq_id)
    )
    obj = q.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Equipment not found")
    return _to_out(obj)


@router.patch("/{eq_id}", response_model=EquipmentOut)
async def update_equipment(
    eq_id: UUID,
    body: EquipmentUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("equipment", "update")),
):
    q = await db.execute(select(Equipment).where(Equipment.id == eq_id))
    obj = q.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Equipment not found")

    old_data = {c.key: str(getattr(obj, c.key)) for c in obj.__table__.columns}
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()

    await _log_audit(db, "equipment", obj.id, AuditOperation.U, old=old_data, new_data=body.model_dump(mode="json", exclude_none=True), user_id=user.id)
    await db.commit()
    await db.refresh(obj, ["equipment_type", "location", "responsible_employee"])
    return _to_out(obj)


@router.post("/{eq_id}/move", response_model=EquipmentOut)
async def move_equipment(
    eq_id: UUID,
    body: EquipmentMoveRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("equipment", "move")),
):
    q = await db.execute(select(Equipment).where(Equipment.id == eq_id))
    obj = q.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Equipment not found")
    if obj.status == EquipmentStatus.decommissioned:
        raise HTTPException(400, "Cannot move decommissioned equipment")

    old_location = str(obj.location_id)
    obj.location_id = body.location_id
    obj.updated_at = datetime.utcnow()

    await _log_audit(db, "equipment", obj.id, AuditOperation.U,
                     old={"location_id": old_location, "reason": "move"},
                     new_data={"location_id": str(body.location_id), "reason": body.reason},
                     user_id=user.id)
    await db.commit()
    await db.refresh(obj, ["equipment_type", "location", "responsible_employee"])
    return _to_out(obj)


@router.post("/{eq_id}/decommission", response_model=EquipmentOut)
async def decommission_equipment(
    eq_id: UUID,
    body: EquipmentDecommissionRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("equipment", "decommission")),
):
    q = await db.execute(select(Equipment).where(Equipment.id == eq_id))
    obj = q.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Equipment not found")
    if obj.status == EquipmentStatus.decommissioned:
        raise HTTPException(400, "Already decommissioned")

    old_status = obj.status.value
    obj.status = EquipmentStatus.decommissioned
    obj.residual_value = 0
    obj.updated_at = datetime.utcnow()

    await _log_audit(db, "equipment", obj.id, AuditOperation.U,
                     old={"status": old_status},
                     new_data={"status": "decommissioned", "reason": body.reason},
                     user_id=user.id)
    await db.commit()
    await db.refresh(obj, ["equipment_type", "location", "responsible_employee"])
    return _to_out(obj)


@router.delete("/{eq_id}", status_code=204)
async def delete_equipment(
    eq_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("equipment", "write")),
):
    q = await db.execute(select(Equipment).where(Equipment.id == eq_id))
    obj = q.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Equipment not found")
    await _log_audit(db, "equipment", obj.id, AuditOperation.D,
                     old={c.key: str(getattr(obj, c.key)) for c in obj.__table__.columns},
                     user_id=user.id)
    await db.delete(obj)
    await db.commit()
