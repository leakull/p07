from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Telemetry, Equipment
from app.schemas import TelemetryCreate, TelemetryOut, TelemetryChartData, TelemetryChartPoint

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


@router.post("", response_model=TelemetryOut, status_code=201)
async def record_telemetry(
    body: TelemetryCreate,
    db: AsyncSession = Depends(get_db),
):
    # Verify equipment exists
    eq = await db.get(Equipment, body.equipment_id)
    if not eq:
        raise HTTPException(404, "Equipment not found")

    obj = Telemetry(
        equipment_id=body.equipment_id,
        metric_name=body.metric_name,
        value=body.value,
        recorded_at=body.recorded_at or datetime.utcnow(),
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return TelemetryOut.model_validate(obj)


@router.post("/batch", status_code=201)
async def record_telemetry_batch(
    items: List[TelemetryCreate],
    db: AsyncSession = Depends(get_db),
):
    objs = [
        Telemetry(
            equipment_id=item.equipment_id,
            metric_name=item.metric_name,
            value=item.value,
            recorded_at=item.recorded_at or datetime.utcnow(),
        )
        for item in items
    ]
    db.add_all(objs)
    await db.commit()
    return {"inserted": len(objs)}


@router.get("/metrics", response_model=List[str])
async def list_metrics(
    equipment_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(distinct(Telemetry.metric_name))
    if equipment_id:
        q = q.where(Telemetry.equipment_id == equipment_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/chart", response_model=TelemetryChartData)
async def get_chart_data(
    equipment_id: UUID,
    metric_name: str,
    hours: int = Query(24, ge=1, le=8760),
    db: AsyncSession = Depends(get_db),
):
    eq = await db.get(Equipment, equipment_id)
    if not eq:
        raise HTTPException(404, "Equipment not found")

    since = datetime.utcnow() - timedelta(hours=hours)
    q = (
        select(Telemetry)
        .where(
            Telemetry.equipment_id == equipment_id,
            Telemetry.metric_name == metric_name,
            Telemetry.recorded_at >= since,
        )
        .order_by(Telemetry.recorded_at.asc())
        .limit(2000)
    )
    rows = (await db.execute(q)).scalars().all()
    points = [
        TelemetryChartPoint(
            timestamp=r.recorded_at.isoformat(),
            value=float(r.value),
        )
        for r in rows
    ]
    return TelemetryChartData(
        metric_name=metric_name,
        equipment_name=eq.name,
        points=points,
    )


@router.get("/latest")
async def get_latest_telemetry(
    equipment_id: Optional[UUID] = None,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get the latest telemetry readings across all equipment or for a specific one."""
    q = select(Telemetry)
    if equipment_id:
        q = q.where(Telemetry.equipment_id == equipment_id)
    q = q.order_by(Telemetry.recorded_at.desc()).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [TelemetryOut.model_validate(r) for r in rows]


@router.get("/summary")
async def get_telemetry_summary(
    equipment_id: UUID,
    metric_name: str,
    hours: int = Query(24, ge=1, le=8760),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate stats: min/max/avg for a metric."""
    since = datetime.utcnow() - timedelta(hours=hours)
    q = select(
        func.min(Telemetry.value).label("min"),
        func.max(Telemetry.value).label("max"),
        func.avg(Telemetry.value).label("avg"),
        func.count(Telemetry.value).label("count"),
    ).where(
        Telemetry.equipment_id == equipment_id,
        Telemetry.metric_name == metric_name,
        Telemetry.recorded_at >= since,
    )
    row = (await db.execute(q)).one()
    return {
        "equipment_id": str(equipment_id),
        "metric_name": metric_name,
        "hours": hours,
        "min": float(row.min) if row.min is not None else None,
        "max": float(row.max) if row.max is not None else None,
        "avg": float(row.avg) if row.avg is not None else None,
        "count": row.count,
    }