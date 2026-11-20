"""
Equipment Monitoring System — FastAPI Application
Run: uvicorn main:app --reload --port 8000
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from app.database import init_db, engine
from app.routers.auth import router as auth_router
from app.routers.equipment import router as equipment_router
from app.routers.telemetry import router as telemetry_router
from app.routers.maintenance import router as maintenance_router
from app.routers.extra import (
    dashboard_router, audit_router, employees_router, departments_router
)

app = FastAPI(
    title="Equipment Monitoring System",
    description="Industrial equipment tracking, telemetry, and maintenance management",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router)
app.include_router(equipment_router)
app.include_router(telemetry_router)
app.include_router(maintenance_router)
app.include_router(dashboard_router)
app.include_router(audit_router)
app.include_router(employees_router)
app.include_router(departments_router)

# Serve static files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)


Instrumentator().instrument(app).expose(app)


@app.on_event("startup")
async def startup():
    from app.seed import seed
    await init_db(engine)
    await seed()


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    index_path = static_dir / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Frontend not built. Place index.html in static/</h1>")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
