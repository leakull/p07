#!/usr/bin/env bash
# =============================================================================
# §3.7.3 — Ежедневный регламент администратора БД
# Запускается cron: 0 8 * * * /scripts/admin_daily_checklist.sh
# =============================================================================
set -euo pipefail

PGHOST="${PGHOST:-db}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-admin}"
PGDATABASE="${PGDATABASE:-vekas_inventory}"
STANZA="vekas"
LOG="/var/log/pgbackrest/admin_daily_$(date +%Y%m%d).log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG}"; }
psql_cmd() { PGPASSWORD="${PGPASSWORD:-}" psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -tAc "$1"; }

log "========== ЕЖЕДНЕВНЫЙ РЕГЛАМЕНТ =========="

# 1. Проверка бэкапов
log "[1] Последний успешный бэкап:"
pgbackrest --stanza="${STANZA}" info --output=text 2>>"${LOG}" | grep "full backup" | tail -1 || true

# 2. Место под бэкапы
log "[2] Использование диска под бэкапы:"
df -h /backups | tee -a "${LOG}"

# 3. Состояние репликации WAL-архива
log "[3] Проверка pgbackrest stanza:"
pgbackrest --stanza="${STANZA}" check 2>>"${LOG}" && log "OK" || log "ОШИБКА!"

# 4. Статистика оборудования
log "[4] Статистика оборудования:"
psql_cmd "SELECT status, COUNT(*) FROM inventory.equipment GROUP BY status ORDER BY status;" | tee -a "${LOG}"

# 5. Незакрытые задачи ТО
log "[5] Открытые заявки на ТО:"
psql_cmd "SELECT COUNT(*) FROM monitoring.maintenance_tasks WHERE status IN ('open','in_progress');" | tee -a "${LOG}"

# 6. Оборудование, требующее ТО
log "[6] Оборудование для ТО:"
psql_cmd "SELECT serial_number, operation_hours FROM inventory.equipment WHERE status='requires_maintenance' LIMIT 10;" | tee -a "${LOG}"

# 7. Пересчёт амортизации (процедура §3.2.1)
log "[7] Пересчёт амортизации:"
PGPASSWORD="${PGPASSWORD:-}" psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" \
    -c "CALL inventory.recalculate_depreciation();" 2>>"${LOG}" && log "OK" || log "ПРОПУЩЕНО"

# 8. Авто-создание заявок ТО (процедура §3.2.1)
log "[8] Создание плановых заявок ТО:"
PGPASSWORD="${PGPASSWORD:-}" psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" \
    -c "CALL monitoring.create_scheduled_maintenance();" 2>>"${LOG}" && log "OK" || log "ПРОПУЩЕНО"

# 9. Размер БД
log "[9] Размер базы данных:"
psql_cmd "SELECT pg_size_pretty(pg_database_size(current_database()));" | tee -a "${LOG}"

log "========== РЕГЛАМЕНТ ЗАВЕРШЁН =========="
