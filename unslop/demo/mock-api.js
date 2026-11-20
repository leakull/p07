// Демо-режим: подменяет FastAPI-бэкенд данными в памяти, чтобы SPA открывалась как обычный файл.
// Данные взяты из app/seed.py и сбрасываются при перезагрузке страницы.
(() => {
  'use strict';

  const now   = Date.now();
  const iso   = ms => new Date(ms).toISOString();
  const days  = n => n * 86400000;
  const hours = n => n * 3600000;
  let seq = 1000;
  const uid = p => `${p}-${(++seq).toString(16)}`;

  // ── Справочники ─────────────────────────────────────────────
  const DEPTS = ['IT Department', 'Production', 'Warehouse', 'Finance', 'Quality Control']
    .map((name, i) => ({ id: `d${i + 1}`, name }));

  const USERS = [
    ['u1', 'Aleksei Petrov', 'admin@company.com',     'admin123', 'admin',       'd1', true],
    ['u2', 'Maria Sokolova', 'engineer@company.com',  'eng123',   'engineer',    'd2', true],
    ['u3', 'Ivan Kozlov',    'store@company.com',     'store123', 'storekeeper', 'd3', true],
    ['u4', 'Olga Novikova',  'auditor@company.com',   'audit123', 'auditor',     'd4', true],
    ['u5', 'Dmitry Volkov',  'viewer@company.com',    'view123',  'viewer',      'd5', true],
    ['u6', 'Anna Lebedeva',  'engineer2@company.com', 'eng123',   'engineer',    'd2', false],
  ].map(([id, full_name, email, password, role, department_id, is_active]) =>
    ({ id, full_name, email, password, role, department_id, is_active, created_at: '2026-04-28T09:00:00Z' }));

  const PERMISSIONS = {
    admin:       { equipment: ['read', 'write', 'update', 'move', 'decommission'], telemetry: ['read'], maintenance: ['read', 'write'], audit: ['read'], employees: ['read', 'write'], costs: ['read'], locations: ['read'] },
    engineer:    { equipment: ['read', 'update'], telemetry: ['read', 'write'], maintenance: ['read', 'write'], audit: [], employees: [], costs: [], locations: ['read'] },
    storekeeper: { equipment: ['read', 'write', 'move'], telemetry: [], maintenance: ['read'], audit: [], employees: [], costs: [], locations: ['read', 'write'] },
    auditor:     { equipment: ['read'], telemetry: ['read'], maintenance: ['read'], audit: ['read'], employees: ['read'], costs: ['read'], locations: ['read'] },
    viewer:      { equipment: ['read'], telemetry: ['read'], maintenance: ['read'], audit: [], employees: [], costs: [], locations: ['read'] },
  };

  const TYPES = [
    ['t1', 'CNC Machine', 500, 10], ['t2', 'Industrial Generator', 1000, 15], ['t3', 'Forklift', 250, 7],
    ['t4', 'Air Compressor', 2000, 8], ['t5', 'Server', 8760, 5], ['t6', 'Conveyor Belt', 750, 12],
  ].map(([id, name, maintenance_interval_hours, depreciation_years]) => ({ id, name, maintenance_interval_hours, depreciation_years }));

  const LOCS = [
    { id: 'l1', name: 'Main Warehouse',  address: 'Industrial Zone 1, Building A', parent_location_id: null },
    { id: 'l2', name: 'Production Hall', address: 'Industrial Zone 1, Building B', parent_location_id: null },
    { id: 'l3', name: 'Server Room',     address: 'HQ, Floor 3',                   parent_location_id: null },
    { id: 'l4', name: 'Garage',          address: 'Industrial Zone 2',             parent_location_id: null },
    { id: 'l5', name: 'Storage Area B',  address: 'Industrial Zone 1, Building A', parent_location_id: 'l1' },
  ];

  const typeName = id => TYPES.find(t => t.id === id)?.name || null;
  const locName  = id => LOCS.find(l => l.id === id)?.name || null;

  // ── Оборудование ────────────────────────────────────────────
  const EQ = [
    ['CNC-A100', 'SN-CNC-001', 't1', 'l2', 'active',               150000, 3420, 1],
    ['CNC-A101', 'SN-CNC-002', 't1', 'l2', 'in_repair',            150000, 4815, 2],
    ['GEN-5000', 'SN-GEN-001', 't2', 'l1', 'active',               320000, 1288, 3],
    ['FORK-01',  'SN-FRK-001', 't3', 'l4', 'active',                85000, 2104, 4],
    ['FORK-02',  'SN-FRK-002', 't3', 'l4', 'requires_maintenance',  85000, 2650, 5],
    ['COMP-200', 'SN-CMP-001', 't4', 'l2', 'active',                64000, 1930, 6],
    ['COMP-201', 'SN-CMP-002', 't4', 'l2', 'maintenance',           64000, 2275, 7],
    ['SRV-R01',  'SN-SRV-001', 't5', 'l3', 'active',               410000, 8120, 8],
    ['SRV-R02',  'SN-SRV-002', 't5', 'l5', 'storage',              410000,    0, 9],
    ['CONV-L1',  'SN-CNV-001', 't6', 'l2', 'active',               210000, 3890, 10],
    ['CONV-L2',  'SN-CNV-002', 't6', 'l2', 'active',               210000, 3512, 11],
    ['GEN-3000', 'SN-GEN-002', 't2', 'l1', 'decommissioned',       280000, 9640, 12],
  ].map(([name, serial_number, equipment_type_id, location_id, status, cost, operation_hours, i]) => ({
    id: `e${i}`, name, serial_number, inventory_number: `INV-2024-${String(i).padStart(4, '0')}`,
    equipment_type_id, equipment_type_name: typeName(equipment_type_id),
    location_id, location_name: locName(location_id), responsible_employee_id: 'u2',
    status, purchase_cost: cost, residual_value: status === 'decommissioned' ? 0 : Math.round(cost * 0.6),
    purchase_date: '2022-01-01', operation_hours, characteristics: { demo: true },
    created_at: '2026-04-28T09:00:00Z', updated_at: iso(now - hours(i * 7)),
  }));

  // ── Задачи ТО ───────────────────────────────────────────────
  const TASKS = [
    ['e5',  'preventive', 'open',        'u2', +2,  null, 0,     'Плановое ТО: замена масла и фильтров'],
    ['e2',  'corrective', 'in_progress', 'u2', -1,  null, 0,     'Замена подшипника шпинделя'],
    ['e7',  'preventive', 'in_progress', 'u6', -2,  null, 0,     'Проверка клапанов и ресиверов'],
    ['e1',  'inspection', 'open',        null, +4,  null, 0,     'Осмотр направляющих и смазки'],
    ['e3',  'preventive', 'open',        'u2', +6,  null, 0,     'ТО генератора по моточасам'],
    ['e10', 'inspection', 'open',        null, +8,  null, 0,     'Проверка натяжения ленты'],
    ['e8',  'preventive', 'in_progress', 'u2', -3,  null, 0,     'Чистка и замена термопасты'],
    ['e4',  'corrective', 'open',        'u6', +1,  null, 0,     'Диагностика АКБ'],
    ['e11', 'preventive', 'in_progress', 'u6', -1,  null, 0,     'Замена приводного ремня'],
    ['e6',  'preventive', 'completed',   'u2', -9,  -2,  18500, 'Замена воздушного фильтра'],
    ['e1',  'corrective', 'completed',   'u2', -12, -1,  42000, 'Ремонт системы охлаждения'],
    ['e4',  'preventive', 'completed',   'u6', -8,  -1,  12400, 'Плановое ТО погрузчика'],
    ['e3',  'inspection', 'completed',   'u2', -6,  -2,  6800,  'Инспекция топливной системы'],
    ['e10', 'preventive', 'completed',   'u6', -5,  -1,  15200, 'Смазка роликов'],
    ['e8',  'inspection', 'completed',   'u2', -4,  -1,  4300,  'Проверка ИБП'],
    ['e11', 'corrective', 'completed',   'u6', -3,  -0.5, 27900, 'Замена датчика скорости'],
    ['e9',  'preventive', 'cancelled',   null, -20, null, 0,    'Отменено: оборудование на складе'],
  ].map(([equipment_id, task_type, status, assigned_to, sched, done, cost, description], i) => ({
    id: `k${i + 1}`, equipment_id, task_type, status, assigned_to, description, cost,
    scheduled_at: iso(now + days(sched)), completed_at: done == null ? null : iso(now + days(done)),
    created_at: iso(now + days(sched - 3)),
  }));

  const taskOut = t => ({
    ...t,
    equipment_name: EQ.find(e => e.id === t.equipment_id)?.name || null,
    assigned_name:  USERS.find(u => u.id === t.assigned_to)?.full_name || null,
  });

  // ── Журнал аудита ───────────────────────────────────────────
  const AUDIT = [];
  let auditSeq = 0;
  const pick = (o, keys) => Object.fromEntries(keys.map(k => [k, o[k]]));
  const AUD_KEYS = ['name', 'serial_number', 'status', 'location_id', 'operation_hours', 'purchase_cost', 'residual_value'];
  function audit(table, op, recordId, oldData, newData, userId, at = Date.now()) {
    AUDIT.unshift({
      id: ++auditSeq, schema_name: table === 'equipment' ? 'inventory' : 'monitoring', table_name: table,
      record_id: recordId, operation: op, old_data: oldData, new_data: newData, user_id: userId, performed_at: iso(at),
    });
  }
  EQ.forEach((e, i) => audit('equipment', 'I', e.id, null, pick(e, AUD_KEYS), 'u3', now - days(30) + hours(i)));
  audit('equipment', 'U', 'e2', { ...pick(EQ[1], AUD_KEYS), status: 'active' }, pick(EQ[1], AUD_KEYS), 'u2', now - days(2));
  audit('equipment', 'U', 'e5', { ...pick(EQ[4], AUD_KEYS), status: 'active' }, pick(EQ[4], AUD_KEYS), 'u2', now - days(1));
  audit('equipment', 'U', 'e12', { ...pick(EQ[11], AUD_KEYS), status: 'active', residual_value: 168000 }, pick(EQ[11], AUD_KEYS), 'u1', now - days(5));
  TASKS.slice(9, 13).forEach(t => audit('maintenance_tasks', 'U', t.id, { status: 'in_progress', cost: 0 }, { status: 'completed', cost: t.cost }, t.assigned_to, Date.parse(t.completed_at)));
  AUDIT.sort((a, b) => Date.parse(b.performed_at) - Date.parse(a.performed_at));
  AUDIT.forEach((a, i) => { a.id = AUDIT.length - i; });
  auditSeq = AUDIT.length;

  // ── Телеметрия: стабильный ряд для пары оборудование + метрика ──
  function rng(seed) {
    let s = 0;
    for (const c of seed) s = (s * 31 + c.charCodeAt(0)) >>> 0;
    return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
  }
  function metricRange(eq, name) {
    const cfg = typeof window.getMetricsForEquipment === 'function'
      ? window.getMetricsForEquipment(eq).find(m => m.name === name) : null;
    return cfg ? { min: cfg.min, max: cfg.max } : { min: 20, max: 80 };
  }
  const METRICS = {
    t1: ['spindle_rpm', 'temperature_c', 'vibration_mm_s'], t2: ['output_kw', 'fuel_level_pct', 'coolant_temp_c'],
    t3: ['battery_pct', 'load_kg', 'speed_kmh'], t4: ['pressure_bar', 'temperature_c', 'flow_m3_min'],
    t5: ['cpu_pct', 'ram_pct', 'temperature_c'], t6: ['belt_speed_m_min', 'motor_load_pct', 'motor_temp_c'],
  };
  function series(eqId, metric, hrs) {
    const eq = EQ.find(e => e.id === eqId);
    if (!eq) return [];
    const { min, max } = metricRange(eq, metric);
    const span = max - min, center = min + span * 0.5;
    const step = hrs <= 24 ? 15 : hrs <= 72 ? 30 : 60;  // минуты между точками
    const n = Math.round(hrs * 60 / step);
    const r = rng(`${eqId}:${metric}`);
    const ph1 = r() * 6, ph2 = r() * 6;
    const out = [];
    for (let i = 0; i < n; i++) {
      const t = now - (n - i) * step * 60000;
      const k = t / 3600000;  // часы: форма ряда не зависит от выбранного периода
      let v = center + span * (0.22 * Math.sin(k / 3.8 + ph1) + 0.1 * Math.sin(k / 1.1 + ph2) + (r() - 0.5) * 0.04);
      out.push({ timestamp: iso(t), value: +Math.max(min, Math.min(max, v)).toFixed(4) });
    }
    return out;
  }

  // ── HTTP-слой ───────────────────────────────────────────────
  const json = (status, body) => new Response(status === 204 ? null : JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  });
  const fail = (status, detail) => json(status, { detail });
  const page = (list, q, per = 20) => {
    const p = Math.max(1, +(q.get('page') || 1));
    const pp = Math.max(1, +(q.get('per_page') || per));
    return { items: list.slice((p - 1) * pp, p * pp), total: list.length, page: p, per_page: pp };
  };

  function userFrom(headers) {
    const h = headers instanceof Headers ? headers.get('Authorization') : (headers?.Authorization || headers?.authorization);
    const id = (h || '').replace(/^Bearer demo\./, '');
    return USERS.find(u => u.id === id && u.is_active) || null;
  }
  const can = (user, res, act) => (PERMISSIONS[user.role]?.[res] || []).includes(act);
  const publicUser = u => ({ id: u.id, full_name: u.full_name, email: u.email, role: u.role, department_id: u.department_id, is_active: u.is_active, created_at: u.created_at });

  function handle(method, url, body, headers) {
    const p = url.pathname, q = url.searchParams;

    if (p === '/api/auth/login' && method === 'POST') {
      const u = USERS.find(x => x.email === body?.email && x.password === body?.password);
      if (!u || !u.is_active) return fail(401, 'Неверный email или пароль');
      return json(200, { access_token: `demo.${u.id}`, token_type: 'bearer', ...publicUser(u) });
    }

    const me = userFrom(headers);
    if (!me) return fail(401, 'Требуется авторизация');

    if (p === '/api/auth/me') return json(200, publicUser(me));
    if (p === '/api/auth/permissions') return json(200, PERMISSIONS);

    // Справочники
    if (p === '/api/equipment/types') return json(200, TYPES);
    if (p === '/api/equipment/locations' && method === 'GET') return json(200, LOCS);
    if (p === '/api/equipment/locations' && method === 'POST') {
      if (!can(me, 'locations', 'write') && me.role !== 'admin') return fail(403, 'Недостаточно прав');
      const loc = { id: uid('l'), name: body.name, address: body.address || null, parent_location_id: body.parent_location_id || null };
      LOCS.push(loc);
      return json(200, loc);
    }

    // Оборудование
    if (p === '/api/equipment' && method === 'GET') {
      const s = (q.get('search') || '').toLowerCase(), st = q.get('status'), tp = q.get('type_id');
      const list = EQ.filter(e =>
        (!s || [e.name, e.serial_number, e.inventory_number].some(v => (v || '').toLowerCase().includes(s))) &&
        (!st || e.status === st) && (!tp || e.equipment_type_id === tp));
      return json(200, page(list, q, 20));
    }
    if (p === '/api/equipment' && method === 'POST') {
      if (!can(me, 'equipment', 'write')) return fail(403, 'Недостаточно прав');
      if (EQ.some(e => e.serial_number === body.serial_number)) return fail(400, 'Оборудование с таким серийным номером уже есть');
      const e = {
        id: uid('e'), name: body.name, serial_number: body.serial_number, inventory_number: body.inventory_number || null,
        equipment_type_id: body.equipment_type_id, equipment_type_name: typeName(body.equipment_type_id),
        location_id: body.location_id || null, location_name: locName(body.location_id),
        responsible_employee_id: body.responsible_employee_id || null, status: body.status || 'active',
        purchase_cost: +body.purchase_cost, residual_value: body.residual_value ?? null, purchase_date: body.purchase_date,
        operation_hours: body.operation_hours || 0, characteristics: {}, created_at: iso(Date.now()), updated_at: iso(Date.now()),
      };
      EQ.unshift(e);
      audit('equipment', 'I', e.id, null, pick(e, AUD_KEYS), me.id);
      return json(201, e);
    }
    let m = p.match(/^\/api\/equipment\/([^/]+)(\/move|\/decommission)?$/);
    if (m) {
      const e = EQ.find(x => x.id === m[1]);
      if (!e) return fail(404, 'Оборудование не найдено');
      if (method === 'GET') return json(200, e);
      const before = pick(e, AUD_KEYS);
      if (m[2] === '/move') {
        if (!can(me, 'equipment', 'move')) return fail(403, 'Недостаточно прав');
        e.location_id = body.location_id; e.location_name = locName(body.location_id);
      } else if (m[2] === '/decommission') {
        if (!can(me, 'equipment', 'decommission')) return fail(403, 'Недостаточно прав');
        e.status = 'decommissioned'; e.residual_value = 0;
      } else if (method === 'PATCH') {
        if (!can(me, 'equipment', 'update') && !can(me, 'equipment', 'write')) return fail(403, 'Недостаточно прав');
        Object.assign(e, body);
        e.location_name = locName(e.location_id);
      }
      e.updated_at = iso(Date.now());
      audit('equipment', 'U', e.id, before, pick(e, AUD_KEYS), me.id);
      return json(200, e);
    }

    // Сводка
    if (p === '/api/dashboard/stats') {
      const by = (list, key) => list.reduce((a, x) => (a[x[key]] = (a[x[key]] || 0) + 1, a), {});
      const byStatus = by(EQ, 'status');
      const monthStart = new Date(); monthStart.setDate(1); monthStart.setHours(0, 0, 0, 0);
      return json(200, {
        total_equipment: EQ.length, active_equipment: byStatus.active || 0, in_repair: byStatus.in_repair || 0,
        requires_maintenance: byStatus.requires_maintenance || 0, decommissioned: byStatus.decommissioned || 0,
        open_tasks: TASKS.filter(t => t.status === 'open').length,
        in_progress_tasks: TASKS.filter(t => t.status === 'in_progress').length,
        completed_tasks_month: TASKS.filter(t => t.status === 'completed' && Date.parse(t.completed_at) >= monthStart).length,
        total_purchase_value: EQ.reduce((a, e) => a + (+e.purchase_cost || 0), 0),
        total_residual_value: EQ.reduce((a, e) => a + (+e.residual_value || 0), 0),
        equipment_by_status: byStatus,
        equipment_by_type: EQ.reduce((a, e) => (a[e.equipment_type_name] = (a[e.equipment_type_name] || 0) + 1, a), {}),
        tasks_by_type: by(TASKS, 'task_type'),
        recent_telemetry_metrics: [],
      });
    }

    // Обслуживание
    if (p === '/api/maintenance/stats') {
      const by = key => TASKS.reduce((a, t) => (a[t[key]] = (a[t[key]] || 0) + 1, a), {});
      return json(200, { by_status: by('status'), by_type: by('task_type'),
        total_completed_cost: TASKS.filter(t => t.status === 'completed').reduce((a, t) => a + t.cost, 0) });
    }
    if (p === '/api/maintenance' && method === 'GET') {
      const st = q.get('status'), tp = q.get('task_type');
      const list = TASKS.filter(t => (!st || t.status === st) && (!tp || t.task_type === tp))
        .sort((a, b) => Date.parse(b.scheduled_at) - Date.parse(a.scheduled_at)).map(taskOut);
      return json(200, page(list, q, 20));
    }
    if (p === '/api/maintenance' && method === 'POST') {
      if (!can(me, 'maintenance', 'write')) return fail(403, 'Недостаточно прав');
      const t = { id: uid('k'), equipment_id: body.equipment_id, task_type: body.task_type, status: body.status || 'open',
        assigned_to: body.assigned_to || null, description: body.description || null, cost: +body.cost || 0,
        scheduled_at: body.scheduled_at, completed_at: body.status === 'completed' ? iso(Date.now()) : null, created_at: iso(Date.now()) };
      TASKS.unshift(t);
      audit('maintenance_tasks', 'I', t.id, null, { status: t.status, task_type: t.task_type, cost: t.cost }, me.id);
      return json(201, taskOut(t));
    }
    m = p.match(/^\/api\/maintenance\/([^/]+)$/);
    if (m) {
      const t = TASKS.find(x => x.id === m[1]);
      if (!t) return fail(404, 'Задача не найдена');
      if (method === 'GET') return json(200, taskOut(t));
      if (!can(me, 'maintenance', 'write')) return fail(403, 'Недостаточно прав');
      const before = { status: t.status, cost: t.cost };
      Object.assign(t, body);
      if (t.status === 'completed' && !t.completed_at) t.completed_at = iso(Date.now());
      audit('maintenance_tasks', 'U', t.id, before, { status: t.status, cost: t.cost }, me.id);
      return json(200, taskOut(t));
    }

    // Телеметрия
    if (p === '/api/telemetry/batch') return json(201, { inserted: Array.isArray(body) ? body.length : 0 });
    if (p === '/api/telemetry/metrics') {
      const e = EQ.find(x => x.id === q.get('equipment_id'));
      return json(200, e ? METRICS[e.equipment_type_id] || [] : []);
    }
    if (p === '/api/telemetry/chart') {
      return json(200, { equipment_id: q.get('equipment_id'), metric_name: q.get('metric_name'),
        points: series(q.get('equipment_id'), q.get('metric_name'), +(q.get('hours') || 24)) });
    }
    if (p === '/api/telemetry/summary') {
      const pts = series(q.get('equipment_id'), q.get('metric_name'), +(q.get('hours') || 24)).map(x => x.value);
      if (!pts.length) return json(200, { min: null, max: null, avg: null, count: 0 });
      return json(200, { min: Math.min(...pts), max: Math.max(...pts), avg: pts.reduce((a, v) => a + v, 0) / pts.length, count: pts.length });
    }

    // Аудит, сотрудники, отделы
    if (p === '/api/audit') {
      if (!can(me, 'audit', 'read')) return fail(403, 'Недостаточно прав');
      const op = q.get('operation'), tb = q.get('table_name');
      return json(200, page(AUDIT.filter(a => (!op || a.operation === op) && (!tb || a.table_name === tb)), q, 20));
    }
    if (p === '/api/employees') {
      if (!can(me, 'employees', 'read')) return fail(403, 'Недостаточно прав');
      return json(200, USERS.map(publicUser));
    }
    if (p === '/api/departments') return json(200, DEPTS);

    return fail(404, `Нет такого метода в демо: ${method} ${p}`);
  }

  const realFetch = window.fetch.bind(window);
  window.fetch = async (input, init = {}) => {
    const url = new URL(typeof input === 'string' ? input : input.url, 'http://demo.local');
    if (!url.pathname.startsWith('/api/')) return realFetch(input, init);
    const method = (init.method || 'GET').toUpperCase();
    let body = null;
    try { body = init.body ? JSON.parse(init.body) : null; } catch {}
    await new Promise(r => setTimeout(r, 120));
    try {
      return handle(method, url, body, init.headers);
    } catch (e) {
      return fail(500, e.message);
    }
  };
})();
