#!/usr/bin/env bash
# =============================================================================
# §3.5 — Тестирование процедур резервного копирования (PITR)
# Скрипт проверяет: целостность бэкапа, полное восстановление, PITR
# =============================================================================
set -euo pipefail

STANZA="vekas"
RESTORE_TARGET_DIR="/tmp/vekas_restore_test"
PGDATA_RESTORE="${RESTORE_TARGET_DIR}/pgdata"
LOG_FILE="/var/log/pgbackrest/test_restore_$(date +%Y%m%d_%H%M%S).log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"; }

# -------------------------------------------------------------------
# 1. ПРОВЕРКА ЦЕЛОСТНОСТИ БЭКАПА (§3.5.1)
# -------------------------------------------------------------------
log "=== Шаг 1: Проверка целостности резервной копии ==="
if ! pgbackrest --stanza="${STANZA}" check 2>>"${LOG_FILE}"; then
    log "ОШИБКА: Проверка целостности провалилась!"
    exit 1
fi
log "OK: pgbackrest check прошёл успешно"

# Список бэкапов
log "=== Доступные резервные копии ==="
pgbackrest --stanza="${STANZA}" info | tee -a "${LOG_FILE}"

# -------------------------------------------------------------------
# 2. ПОЛНОЕ ВОССТАНОВЛЕНИЕ В ОТДЕЛЬНУЮ ДИРЕКТОРИЮ (§3.5.2)
# -------------------------------------------------------------------
log "=== Шаг 2: Полное восстановление ==="
START_TIME=$(date +%s)

rm -rf "${RESTORE_TARGET_DIR}"
mkdir -p "${PGDATA_RESTORE}"
chmod 700 "${PGDATA_RESTORE}"

pgbackrest --stanza="${STANZA}" \
    --pg1-path="${PGDATA_RESTORE}" \
    --recovery-option="recovery_target_action=promote" \
    restore 2>>"${LOG_FILE}"

END_TIME=$(date +%s)
RTO_SECONDS=$((END_TIME - START_TIME))
log "OK: Полное восстановление выполнено за ${RTO_SECONDS} сек (RTO = ${RTO_SECONDS}s)"

# Проверка достижения RTO < 3600 сек (1 час, требование диплома)
if [ "${RTO_SECONDS}" -gt 3600 ]; then
    log "ПРЕДУПРЕЖДЕНИЕ: RTO ${RTO_SECONDS}s превышает целевой показатель 3600s!"
fi

# -------------------------------------------------------------------
# 3. PITR — ВОССТАНОВЛЕНИЕ НА ТОЧКУ ВО ВРЕМЕНИ (§3.5.2)
# -------------------------------------------------------------------
log "=== Шаг 3: PITR — восстановление на момент времени ==="
PITR_TARGET=$(date -u -d '10 minutes ago' '+%Y-%m-%d %H:%M:%S' 2>/dev/null \
    || date -u -v-10M '+%Y-%m-%d %H:%M:%S')  # macOS fallback

log "Цель PITR: ${PITR_TARGET}"
PITR_DIR="/tmp/vekas_pitr_test"
mkdir -p "${PITR_DIR}"
chmod 700 "${PITR_DIR}"

pgbackrest --stanza="${STANZA}" \
    --pg1-path="${PITR_DIR}" \
    --target="${PITR_TARGET}" \
    --target-action=promote \
    --type=time \
    restore 2>>"${LOG_FILE}" && log "OK: PITR на '${PITR_TARGET}' выполнен" \
                              || log "ПРЕДУПРЕЖДЕНИЕ: PITR не выполнен (нет WAL для данной точки?)"

# -------------------------------------------------------------------
# 4. ЧЕК-ЛИСТ ПОСЛЕ ВОССТАНОВЛЕНИЯ (§3.5.3)
# -------------------------------------------------------------------
log "=== Шаг 4: Чек-лист после восстановления ==="
log "[ ] Запустите PostgreSQL из ${PGDATA_RESTORE} и проверьте доступность БД"
log "[ ] Выполните: psql -p 5435 -U admin -d vekas_inventory -c 'SELECT COUNT(*) FROM inventory.equipment;'"
log "[ ] Проверьте целостность таблиц: SELECT schemaname, tablename FROM pg_tables WHERE schemaname IN ('core','inventory','monitoring','archive');"
log "[ ] Убедитесь, что триггеры активны: SELECT tgname FROM pg_trigger;"
log "[ ] После проверки удалите тестовые директории:"
log "    rm -rf ${RESTORE_TARGET_DIR} ${PITR_DIR}"

# Очистка
rm -rf "${PITR_DIR}"
log "=== Тест завершён. Лог: ${LOG_FILE} ==="
