# Equipment Monitoring System (EMS)

Industrial-grade equipment tracking, telemetry monitoring, and maintenance management built with **FastAPI** + **PostgreSQL** + async SQLAlchemy.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.11+
- PostgreSQL 14+ (with schemas from `schema.sql`)
- [optional] `pgcrypto` extension

### 2. Database Setup
Run the provided schema SQL against your PostgreSQL instance:
```bash
psql -U postgres -d equipdb -f schema.sql
```

### 3. Install Dependencies
```bash
cd app
pip install -r requirements.txt
```

### 4. Configuration
Create `.env` in the `app/` directory:
```env
DATABASE_URL=postgresql+asyncpg://postgres:yourpassword@localhost:5432/equipdb
SECRET_KEY=your-secret-key-change-this
```

### 5. Seed Sample Data
```bash
cd app
python seed.py
```
This populates: 5 departments, 6 employees, 5 locations, 6 equipment types, 12 equipment units, ~20 maintenance tasks, and ~10,000 telemetry records.

### 6. Run
```bash
uvicorn main:app --reload --port 8000
```

Open: **http://localhost:8000**

---

## 👤 Demo Accounts

| Role        | Email                    | Password  |
|-------------|--------------------------|-----------|
| Admin       | admin@company.com        | admin123  |
| Engineer    | engineer@company.com     | eng123    |
| Storekeeper | store@company.com        | store123  |
| Auditor     | auditor@company.com      | audit123  |
| Viewer      | viewer@company.com       | view123   |

---

## 🔐 Role Permissions

| Resource   | Admin | Engineer | Storekeeper | Auditor | Viewer |
|------------|-------|----------|-------------|---------|--------|
| Equipment  | Full  | Read/Update | Full CRUD | Read | Read |
| Telemetry  | Read  | Read/Write  | –       | Read | Read |
| Maintenance| Full  | Full        | Read    | Read | Read |
| Audit Log  | Read  | –           | –       | Read | – |
| Employees  | Full  | –           | –       | Read | – |
| Costs      | Read  | –           | –       | Read | – |
| Locations  | Read  | Read        | Full    | Read | Read |

---

## 📡 API Reference

| Endpoint | Description |
|----------|-------------|
| `GET /api/dashboard/stats` | KPIs, counts, financial summary |
| `GET /api/equipment` | Paginated equipment list (search, filter) |
| `POST /api/equipment` | Register new equipment |
| `PATCH /api/equipment/{id}` | Update equipment |
| `POST /api/equipment/{id}/move` | Move to new location |
| `POST /api/equipment/{id}/decommission` | Write off equipment |
| `GET /api/telemetry/chart` | Time-series chart data |
| `GET /api/telemetry/summary` | Min/Max/Avg stats |
| `POST /api/telemetry/batch` | Bulk telemetry ingestion |
| `GET /api/maintenance` | Maintenance tasks list |
| `POST /api/maintenance` | Create task |
| `PATCH /api/maintenance/{id}` | Update task status/cost |
| `GET /api/audit` | Audit log (admin/auditor only) |
| `GET /api/auth/permissions` | Role-permission matrix |
| `GET /api/docs` | Swagger UI |

---

## 🏗 Architecture

```
app/
├── main.py           — FastAPI app, routing, CORS
├── database.py       — Async SQLAlchemy engine + settings
├── models.py         — ORM models (core/inventory/monitoring/archive schemas)
├── schemas.py        — Pydantic request/response models
├── seed.py           — Demo data generator
├── routers/
│   ├── auth.py       — JWT auth, role permissions
│   ├── equipment.py  — Equipment CRUD, move, decommission
│   ├── telemetry.py  — Sensor data ingestion + charting
│   ├── maintenance.py— Maintenance tasks management
│   └── extra.py      — Dashboard, audit, employees, departments
└── static/
    └── index.html    — Full SPA (1900+ lines, zero dependencies except Chart.js)
```

---

## 📊 Non-Functional Requirements

| Requirement | Implementation |
|-------------|----------------|
| **Performance** | Indexed queries on serial_number, equipment_id+recorded_at; async SQLAlchemy; pagination |
| **Storage (10+ years)** | Partitioned `telemetry` table by year (add partitions per year) |
| **99.9% uptime** | Stateless FastAPI; horizontal scaling via Gunicorn/uvicorn workers |
| **RPO < 15 min** | Configure PostgreSQL streaming replication + WAL archiving |
| **RTO < 1 hour** | Point-in-time recovery from WAL; tested restore procedures |
| **Audit trail** | Automatic DB triggers log every INSERT/UPDATE/DELETE on equipment |
| **RBAC** | JWT-based role claims; FastAPI dependency injection per endpoint |
| **Data confidentiality** | Cost/financial fields hidden for engineer/storekeeper/viewer roles |
