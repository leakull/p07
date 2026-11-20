-- ======================================================
-- 0. ПОДГОТОВКА СРЕДЫ
-- ======================================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

DROP SCHEMA IF EXISTS core CASCADE;
DROP SCHEMA IF EXISTS inventory CASCADE;
DROP SCHEMA IF EXISTS monitoring CASCADE;
DROP SCHEMA IF EXISTS archive CASCADE;

CREATE SCHEMA core;       -- Сотрудники, отделы
CREATE SCHEMA inventory;  -- Оборудование, склады
CREATE SCHEMA monitoring; -- Телеметрия, задачи
CREATE SCHEMA archive;    -- Аудит и история

-- ======================================================
-- 1. ТИПЫ И ПЕРЕЧИСЛЕНИЯ
-- ======================================================
CREATE TYPE core.employee_role AS ENUM ('admin', 'engineer', 'storekeeper', 'viewer', 'auditor');
CREATE TYPE inventory.equipment_status AS ENUM ('active', 'maintenance', 'requires_maintenance', 'decommissioned', 'in_repair', 'storage');
CREATE TYPE monitoring.task_type AS ENUM ('preventive', 'corrective', 'inspection');
CREATE TYPE monitoring.task_status AS ENUM ('open', 'in_progress', 'completed', 'cancelled');
CREATE TYPE archive.audit_operation AS ENUM ('I', 'U', 'D');

-- ======================================================
-- 2. СХЕМА CORE (ОРГСТРУКТУРА)
-- ======================================================
CREATE TABLE core.departments (
    id         UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    name       VARCHAR(200) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE core.employees (
    id            UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name     VARCHAR(300)  NOT NULL,
    role          core.employee_role NOT NULL,
    email         VARCHAR(254)  NOT NULL UNIQUE,
    password_hash TEXT          NOT NULL,
    department_id UUID          REFERENCES core.departments(id) ON DELETE SET NULL,
    is_active     BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE TABLE core.department_managers (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    department_id  UUID        NOT NULL REFERENCES core.departments(id) ON DELETE CASCADE,
    employee_id    UUID        NOT NULL REFERENCES core.employees(id) ON DELETE CASCADE,
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_to   TIMESTAMPTZ,
    CONSTRAINT chk_dates CHECK (effective_to IS NULL OR effective_to > effective_from)
);

CREATE UNIQUE INDEX uidx_dept_manager_current ON core.department_managers (department_id) WHERE effective_to IS NULL;

-- ======================================================
-- 3. СХЕМА INVENTORY (ОБОРУДОВАНИЕ)
-- ======================================================
CREATE TABLE inventory.locations (
    id                 UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    name               VARCHAR(300) NOT NULL,
    address            TEXT,
    parent_location_id UUID         REFERENCES inventory.locations(id) ON DELETE SET NULL
);

CREATE TABLE inventory.equipment_types (
    id                         UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    name                       VARCHAR(200) NOT NULL UNIQUE,
    maintenance_interval_hours INTEGER      NOT NULL DEFAULT 2000 CHECK (maintenance_interval_hours > 0),
    depreciation_years         NUMERIC(4,1) NOT NULL DEFAULT 5.0 CHECK (depreciation_years > 0)
);

CREATE TABLE inventory.equipment (
    id                      UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    serial_number           VARCHAR(100)     NOT NULL UNIQUE,
    inventory_number        VARCHAR(100)     UNIQUE,
    name                    VARCHAR(300)     NOT NULL,
    equipment_type_id       UUID             NOT NULL REFERENCES inventory.equipment_types(id),
    location_id             UUID             REFERENCES inventory.locations(id),
    responsible_employee_id UUID             REFERENCES core.employees(id),
    status                  inventory.equipment_status NOT NULL DEFAULT 'active',
    purchase_cost           NUMERIC(15,2)    NOT NULL CHECK (purchase_cost >= 0),
    residual_value          NUMERIC(15,2),
    purchase_date           DATE             NOT NULL,
    warranty_expires_at     DATE,                        -- ДОБАВЛЕНО: дата окончания гарантии
    operation_hours         INTEGER          NOT NULL DEFAULT 0,
    characteristics         JSONB            NOT NULL DEFAULT '{}',
    updated_at              TIMESTAMPTZ      NOT NULL DEFAULT NOW()
);

-- История перемещений оборудования (журнал, требуемый дипломом §3.2.3)
CREATE TABLE inventory.equipment_movements (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_id UUID        NOT NULL REFERENCES inventory.equipment(id) ON DELETE CASCADE,
    from_location_id UUID    REFERENCES inventory.locations(id),
    to_location_id   UUID    REFERENCES inventory.locations(id),
    moved_by     UUID        REFERENCES core.employees(id),
    moved_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reason       TEXT
);

-- ======================================================
-- 4. СХЕМА MONITORING (ТЕЛЕМЕТРИЯ И ЗАДАЧИ)
-- ======================================================
-- ИСПРАВЛЕНО: телеметрия как партиционированная таблица (родительская)
-- SQLAlchemy маппится на эту таблицу, PostgreSQL сам маршрутизирует INSERT в партицию
CREATE TABLE monitoring.telemetry (
    id           UUID          NOT NULL DEFAULT gen_random_uuid(),
    equipment_id UUID          NOT NULL REFERENCES inventory.equipment(id) ON DELETE CASCADE,
    metric_name  VARCHAR(100)  NOT NULL,
    value        NUMERIC(20,6) NOT NULL,
    recorded_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, recorded_at)
) PARTITION BY RANGE (recorded_at);

-- Партиция на 2026 год
CREATE TABLE monitoring.telemetry_y2026 PARTITION OF monitoring.telemetry
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');

-- ДОБАВЛЕНО: Партиция на 2027 год (была только 2026)
CREATE TABLE monitoring.telemetry_y2027 PARTITION OF monitoring.telemetry
    FOR VALUES FROM ('2027-01-01') TO ('2028-01-01');

CREATE TABLE monitoring.maintenance_tasks (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_id UUID         NOT NULL REFERENCES inventory.equipment(id) ON DELETE CASCADE,
    assigned_to  UUID         REFERENCES core.employees(id),
    task_type    monitoring.task_type NOT NULL,
    status       monitoring.task_status NOT NULL DEFAULT 'open',
    description  TEXT,
    scheduled_at TIMESTAMPTZ  NOT NULL,
    completed_at TIMESTAMPTZ,
    cost         NUMERIC(15,2) DEFAULT 0,
    CONSTRAINT chk_completed CHECK (completed_at IS NULL OR completed_at >= scheduled_at)
);

-- ======================================================
-- 5. СХЕМА ARCHIVE (АУДИТ)
-- ======================================================
CREATE TABLE archive.audit_log (
    id           BIGSERIAL       PRIMARY KEY,
    schema_name  VARCHAR(63)     NOT NULL,
    table_name   VARCHAR(63)     NOT NULL,
    record_id    UUID            NOT NULL,
    operation    archive.audit_operation NOT NULL,
    old_data     JSONB,
    new_data     JSONB,
    user_id      UUID,
    performed_at TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Индекс для быстрого поиска по объекту
CREATE INDEX idx_audit_record ON archive.audit_log (record_id, performed_at DESC);
CREATE INDEX idx_audit_table   ON archive.audit_log (table_name, performed_at DESC);

-- ======================================================
-- 6. ТРИГГЕРЫ И ФУНКЦИИ (§3.2.1, §3.2.2)
-- ======================================================

-- 6.1 Автоматическое обновление updated_at
CREATE OR REPLACE FUNCTION core.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_employees_updated_at
    BEFORE UPDATE ON core.employees
    FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();

CREATE TRIGGER trg_equipment_updated_at
    BEFORE UPDATE ON inventory.equipment
    FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();

-- 6.2 Функция аудита (универсальная)
CREATE OR REPLACE FUNCTION archive.fn_audit_tracker()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        INSERT INTO archive.audit_log (schema_name, table_name, record_id, operation, old_data, new_data)
        VALUES (TG_TABLE_SCHEMA, TG_TABLE_NAME, OLD.id::uuid, 'U', to_jsonb(OLD), to_jsonb(NEW));
    ELSIF (TG_OP = 'DELETE') THEN
        INSERT INTO archive.audit_log (schema_name, table_name, record_id, operation, old_data)
        VALUES (TG_TABLE_SCHEMA, TG_TABLE_NAME, OLD.id::uuid, 'D', to_jsonb(OLD));
    ELSIF (TG_OP = 'INSERT') THEN
        INSERT INTO archive.audit_log (schema_name, table_name, record_id, operation, new_data)
        VALUES (TG_TABLE_SCHEMA, TG_TABLE_NAME, NEW.id::uuid, 'I', to_jsonb(NEW));
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_equipment
    AFTER INSERT OR UPDATE OR DELETE ON inventory.equipment
    FOR EACH ROW EXECUTE FUNCTION archive.fn_audit_tracker();

CREATE TRIGGER trg_audit_employees
    AFTER INSERT OR UPDATE OR DELETE ON core.employees
    FOR EACH ROW EXECUTE FUNCTION archive.fn_audit_tracker();

CREATE TRIGGER trg_audit_maintenance_tasks
    AFTER INSERT OR UPDATE OR DELETE ON monitoring.maintenance_tasks
    FOR EACH ROW EXECUTE FUNCTION archive.fn_audit_tracker();

-- 6.3 НОВОЕ §3.2.2: Автоматическое изменение статуса оборудования
-- при превышении нормы часов эксплуатации
CREATE OR REPLACE FUNCTION monitoring.fn_check_maintenance_due()
RETURNS TRIGGER AS $$
DECLARE
    v_interval INTEGER;
BEGIN
    -- Получаем интервал ТО для данного типа оборудования
    SELECT et.maintenance_interval_hours
    INTO v_interval
    FROM inventory.equipment_types et
    WHERE et.id = NEW.equipment_type_id;

    -- Если часы работы превысили интервал и статус "active" — переводим в "requires_maintenance"
    IF NEW.operation_hours >= v_interval AND NEW.status = 'active' THEN
        NEW.status := 'requires_maintenance';
        RAISE NOTICE 'Оборудование % требует технического обслуживания', NEW.serial_number;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_equipment_maintenance_check
    BEFORE INSERT OR UPDATE OF operation_hours ON inventory.equipment
    FOR EACH ROW EXECUTE FUNCTION monitoring.fn_check_maintenance_due();

-- 6.4 НОВОЕ §3.2.2: Уведомление при истечении гарантии
CREATE OR REPLACE FUNCTION inventory.fn_check_warranty_expiry()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.warranty_expires_at IS NOT NULL
       AND NEW.warranty_expires_at <= CURRENT_DATE
       AND (OLD.warranty_expires_at IS NULL OR OLD.warranty_expires_at > CURRENT_DATE) THEN
        INSERT INTO archive.audit_log (
            schema_name, table_name, record_id, operation, new_data
        ) VALUES (
            'inventory', 'equipment', NEW.id, 'U',
            jsonb_build_object(
                'event', 'warranty_expired',
                'equipment_id', NEW.id,
                'serial_number', NEW.serial_number,
                'warranty_expires_at', NEW.warranty_expires_at
            )
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_warranty_expiry_check
    AFTER INSERT OR UPDATE OF warranty_expires_at ON inventory.equipment
    FOR EACH ROW EXECUTE FUNCTION inventory.fn_check_warranty_expiry();

-- 6.5 Автоматическая запись перемещения при смене location_id
CREATE OR REPLACE FUNCTION inventory.fn_track_movement()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.location_id IS DISTINCT FROM NEW.location_id THEN
        INSERT INTO inventory.equipment_movements
            (equipment_id, from_location_id, to_location_id, moved_by)
        VALUES
            (NEW.id, OLD.location_id, NEW.location_id, NEW.responsible_employee_id);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_equipment_movement
    AFTER UPDATE OF location_id ON inventory.equipment
    FOR EACH ROW EXECUTE FUNCTION inventory.fn_track_movement();

-- ======================================================
-- 7. ХРАНИМЫЕ ПРОЦЕДУРЫ (§3.2.1)
-- ======================================================

-- 7.1 Расчёт амортизации и обновление остаточной стоимости
-- Линейный метод: ежегодное списание = (purchase_cost - salvage) / depreciation_years
-- Вызывается вручную или по расписанию (cron)
CREATE OR REPLACE PROCEDURE inventory.recalculate_depreciation()
LANGUAGE plpgsql AS $$
DECLARE
    rec RECORD;
    v_annual_depreciation NUMERIC(15,2);
    v_years_elapsed       NUMERIC(10,4);
    v_residual            NUMERIC(15,2);
    v_salvage_pct         NUMERIC(5,4) := 0.10; -- 10% ликвидационная стоимость
BEGIN
    FOR rec IN
        SELECT e.id, e.purchase_cost, e.purchase_date, et.depreciation_years
        FROM inventory.equipment e
        JOIN inventory.equipment_types et ON et.id = e.equipment_type_id
        WHERE e.status NOT IN ('decommissioned')
    LOOP
        v_years_elapsed := EXTRACT(EPOCH FROM (NOW() - rec.purchase_date::timestamptz)) / (86400.0 * 365.25);
        v_annual_depreciation := (rec.purchase_cost * (1 - v_salvage_pct)) / rec.depreciation_years;
        v_residual := GREATEST(
            rec.purchase_cost - (v_annual_depreciation * v_years_elapsed),
            rec.purchase_cost * v_salvage_pct  -- не ниже ликвидационной стоимости
        );

        UPDATE inventory.equipment
        SET residual_value = ROUND(v_residual, 2)
        WHERE id = rec.id;
    END LOOP;
    RAISE NOTICE 'Амортизация пересчитана для всего активного оборудования';
END;
$$;

-- 7.2 Автоматическое создание плановых заявок на ТО
-- Создаёт задачи для оборудования со статусом requires_maintenance без открытых заявок
CREATE OR REPLACE PROCEDURE monitoring.create_scheduled_maintenance()
LANGUAGE plpgsql AS $$
DECLARE
    rec         RECORD;
    v_engineer  UUID;
BEGIN
    -- Находим любого активного инженера для назначения (можно улучшить логику)
    SELECT id INTO v_engineer
    FROM core.employees
    WHERE role = 'engineer' AND is_active = TRUE
    LIMIT 1;

    FOR rec IN
        SELECT e.id AS equipment_id, e.name, e.serial_number
        FROM inventory.equipment e
        WHERE e.status = 'requires_maintenance'
          AND NOT EXISTS (
              SELECT 1 FROM monitoring.maintenance_tasks mt
              WHERE mt.equipment_id = e.id
                AND mt.status IN ('open', 'in_progress')
                AND mt.task_type = 'preventive'
          )
    LOOP
        INSERT INTO monitoring.maintenance_tasks
            (equipment_id, assigned_to, task_type, status, description, scheduled_at)
        VALUES (
            rec.equipment_id,
            v_engineer,
            'preventive',
            'open',
            FORMAT('Плановое ТО для %s (s/n: %s)', rec.name, rec.serial_number),
            NOW() + INTERVAL '1 day'
        );
        RAISE NOTICE 'Создана заявка на ТО для оборудования: %', rec.serial_number;
    END LOOP;
END;
$$;

-- 7.3 Присвоение инвентарного номера при добавлении оборудования (§3.2.1)
CREATE OR REPLACE FUNCTION inventory.fn_assign_inventory_number()
RETURNS TRIGGER AS $$
DECLARE
    v_year     TEXT := TO_CHAR(NOW(), 'YYYY');
    v_seq      INTEGER;
    v_inv_num  TEXT;
BEGIN
    -- Если инвентарный номер не задан — генерируем автоматически
    IF NEW.inventory_number IS NULL OR NEW.inventory_number = '' THEN
        SELECT COALESCE(
            MAX(
                NULLIF(
                    REGEXP_REPLACE(inventory_number, '^INV-[0-9]+-', ''),
                    inventory_number
                )::integer
            ), 0) + 1
        INTO v_seq
        FROM inventory.equipment
        WHERE inventory_number LIKE 'INV-' || v_year || '-%';

        v_inv_num := FORMAT('INV-%s-%05d', v_year, v_seq);
        NEW.inventory_number := v_inv_num;
        RAISE NOTICE 'Присвоен инвентарный номер: %', v_inv_num;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_assign_inventory_number
    BEFORE INSERT ON inventory.equipment
    FOR EACH ROW EXECUTE FUNCTION inventory.fn_assign_inventory_number();

-- ======================================================
-- 8. БЕЗОПАСНОСТЬ (RLS)
-- ======================================================
ALTER TABLE monitoring.maintenance_tasks ENABLE ROW LEVEL SECURITY;

-- Инженер видит только назначенные ему задачи
CREATE POLICY policy_engineer_tasks ON monitoring.maintenance_tasks
    FOR SELECT
    USING (
        assigned_to = NULLIF(current_setting('app.current_user_id', true), '')::uuid
    );

-- Администратор и аудитор видят всё
CREATE POLICY policy_admin_all_tasks ON monitoring.maintenance_tasks
    FOR ALL
    USING (current_setting('app.current_role', true) IN ('admin', 'auditor', 'dba'));

-- ======================================================
-- 9. ИНДЕКСЫ (§3.6.1)
-- ======================================================
CREATE INDEX idx_eq_serial          ON inventory.equipment(serial_number);
CREATE INDEX idx_eq_status          ON inventory.equipment(status);
CREATE INDEX idx_eq_location        ON inventory.equipment(location_id);
CREATE INDEX idx_eq_responsible     ON inventory.equipment(responsible_employee_id);
CREATE INDEX idx_eq_purchase_date   ON inventory.equipment(purchase_date);
CREATE INDEX idx_eq_inv_number      ON inventory.equipment(inventory_number) WHERE inventory_number IS NOT NULL;
CREATE INDEX idx_telemetry_lookup   ON monitoring.telemetry (equipment_id, recorded_at DESC);
CREATE INDEX idx_telemetry_metric   ON monitoring.telemetry (metric_name, recorded_at DESC);
CREATE INDEX idx_tasks_equipment    ON monitoring.maintenance_tasks(equipment_id);
CREATE INDEX idx_tasks_status       ON monitoring.maintenance_tasks(status);
CREATE INDEX idx_tasks_assigned     ON monitoring.maintenance_tasks(assigned_to);

-- ======================================================
-- 10. УПРАВЛЕНИЕ ДОСТУПОМ RBAC (§3.7.1)
-- ======================================================
-- БАГ ИСПРАВЛЕН: DROP ROLE падал если не все роли существовали.
-- Теперь каждая роль удаляется отдельно с IF EXISTS.
DO $$
BEGIN
    DROP ROLE IF EXISTS dba;
    DROP ROLE IF EXISTS admin;
    DROP ROLE IF EXISTS engineer;
    DROP ROLE IF EXISTS storekeeper;
    DROP ROLE IF EXISTS auditor;
    DROP ROLE IF EXISTS viewer;
END $$;

-- Создание ролей без возможности входа
CREATE ROLE dba;          -- Администратор БД (полный доступ)
CREATE ROLE admin;        -- Администратор системы
CREATE ROLE engineer;     -- Инженер
CREATE ROLE storekeeper;  -- Кладовщик
CREATE ROLE auditor;      -- Аудитор (только чтение)
CREATE ROLE viewer;       -- Наблюдатель (минимальное чтение)

-- DBA: полный контроль
GRANT ALL PRIVILEGES ON SCHEMA core, inventory, monitoring, archive TO dba;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA core, inventory, monitoring, archive TO dba;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA core, inventory, monitoring, archive TO dba;

-- ADMIN: управление персоналом
GRANT USAGE ON SCHEMA core, inventory, monitoring TO admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA core TO admin;
GRANT SELECT ON ALL TABLES IN SCHEMA inventory, monitoring TO admin;

-- ENGINEER: работа с оборудованием и задачами
GRANT USAGE ON SCHEMA inventory, monitoring TO engineer;
GRANT SELECT, UPDATE ON inventory.equipment TO engineer;
GRANT ALL PRIVILEGES ON monitoring.maintenance_tasks TO engineer;
GRANT INSERT ON monitoring.telemetry TO engineer;
GRANT SELECT ON inventory.locations, inventory.equipment_types TO engineer;

-- STOREKEEPER: инвентаризация
GRANT USAGE ON SCHEMA inventory TO storekeeper;
GRANT ALL PRIVILEGES ON inventory.equipment, inventory.locations TO storekeeper;
GRANT SELECT ON inventory.equipment_types TO storekeeper;
GRANT INSERT ON inventory.equipment_movements TO storekeeper;

-- AUDITOR: только чтение всего, включая архив
GRANT USAGE ON SCHEMA core, inventory, monitoring, archive TO auditor;
GRANT SELECT ON ALL TABLES IN SCHEMA core, inventory, monitoring, archive TO auditor;

-- VIEWER: минимальное чтение
GRANT USAGE ON SCHEMA inventory, monitoring TO viewer;
GRANT SELECT ON inventory.equipment, inventory.locations, inventory.equipment_types TO viewer;
GRANT SELECT ON monitoring.maintenance_tasks TO viewer;

-- Права по умолчанию для будущих таблиц
ALTER DEFAULT PRIVILEGES IN SCHEMA inventory GRANT SELECT ON TABLES TO viewer;
