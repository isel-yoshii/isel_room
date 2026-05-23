(function () {
  const ACTION_TYPES = [
    'REGISTER', 'DELETE',
    'CHECKIN', 'CHECKOUT',
    'MANUAL_CHECKIN', 'MANUAL_CHECKOUT',
    'AUTO_CHECKOUT', 'FORCE_CHECKOUT',
    'PROMOTE', 'POINTS_ADJUST',
  ];
  const ACTION_LABEL = {
    REGISTER: 'Registered', DELETE: 'Deleted',
    CHECKIN: 'Check-In', CHECKOUT: 'Check-Out',
    MANUAL_CHECKIN: 'Manual In', MANUAL_CHECKOUT: 'Manual Out',
    AUTO_CHECKOUT: 'Auto-Out', FORCE_CHECKOUT: 'Force-Out',
    PROMOTE: 'Promoted', POINTS_ADJUST: 'Points Adjusted',
  };
  const IN_ACTIONS = new Set(['REGISTER', 'CHECKIN', 'MANUAL_CHECKIN']);
  const PRESET_GROUPS = {
    all:         [],
    anomalies:   ['MANUAL_CHECKIN', 'MANUAL_CHECKOUT', 'AUTO_CHECKOUT', 'FORCE_CHECKOUT'],
    attendance:  ['CHECKIN', 'CHECKOUT', 'MANUAL_CHECKIN', 'MANUAL_CHECKOUT', 'AUTO_CHECKOUT', 'FORCE_CHECKOUT'],
    admin:       ['REGISTER', 'DELETE', 'PROMOTE', 'POINTS_ADJUST'],
  };

  const _selectedActions = new Set();
  let _filterDebounce = null;
  let _filtersInitialized = false;
  let _selectedUserIds = [];
  let _memberMs = null;

  function isoDay(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }
  function mondayOf(d) {
    const x = new Date(d); x.setHours(0,0,0,0);
    const dow = (x.getDay() + 6) % 7;
    x.setDate(x.getDate() - dow);
    return x;
  }

  window.loadActivity = async function loadActivity() {
    await initAuditFilters();
    applyDatePreset(document.getElementById('filter-date-preset')?.value || 'this-week');
  };

  window.applyDatePreset = function applyDatePreset(name) {
    const today = new Date(); today.setHours(0,0,0,0);
    const startEl = document.getElementById('filter-start');
    const endEl   = document.getElementById('filter-end');
    const customWrap = document.getElementById('filter-date-custom');

    let start = null, end = null;
    if (name === 'this-week')  { start = mondayOf(today); end = new Date(start); end.setDate(end.getDate() + 6); }
    else if (name === 'last-week') { end = mondayOf(today); end.setDate(end.getDate() - 1); start = new Date(end); start.setDate(start.getDate() - 6); }
    else if (name === 'this-month') { start = new Date(today.getFullYear(), today.getMonth(), 1); end = new Date(today.getFullYear(), today.getMonth() + 1, 0); }
    else if (name === 'last-month') { start = new Date(today.getFullYear(), today.getMonth() - 1, 1); end = new Date(today.getFullYear(), today.getMonth(), 0); }

    if (name === 'custom') {
      customWrap?.classList.remove('hidden');
    } else {
      customWrap?.classList.add('hidden');
      startEl.value = start ? isoDay(start) : '';
      endEl.value   = end   ? isoDay(end)   : '';
    }
    loadAuditLog();
  };

  window.applyActionPreset = function applyActionPreset(name) {
    const target = new Set(PRESET_GROUPS[name] || []);
    _selectedActions.clear();
    target.forEach(a => _selectedActions.add(a));
    document.querySelectorAll('#filter-actions .chip').forEach(c => {
      c.classList.toggle('chip-active', target.has(c.dataset.action));
    });
    loadAuditLog();
  };

  window.buildAuditFilterParams = function buildAuditFilterParams() {
    const params = new URLSearchParams();
    if (_selectedUserIds.length) params.set('user_ids', _selectedUserIds.join(','));
    if (_selectedActions.size) params.set('actions', [..._selectedActions].join(','));
    const start = document.getElementById('filter-start')?.value;
    const end   = document.getElementById('filter-end')?.value;
    if (start) params.set('start', `${start}T00:00:00`);
    if (end)   params.set('end',   `${end}T23:59:59`);
    const q = document.getElementById('filter-q')?.value.trim();
    if (q) params.set('q', q);
    return params;
  };

  window.scheduleFilterReload = function scheduleFilterReload() {
    if (_filterDebounce) clearTimeout(_filterDebounce);
    _filterDebounce = setTimeout(loadAuditLog, 250);
  };

  window.toggleActionChip = function toggleActionChip(action) {
    const el = document.querySelector(`.chip[data-action="${action}"]`);
    if (_selectedActions.has(action)) {
      _selectedActions.delete(action);
      el?.classList.remove('chip-active');
    } else {
      _selectedActions.add(action);
      el?.classList.add('chip-active');
    }
    loadAuditLog();
  };

  window.clearAuditFilters = function clearAuditFilters() {
    _selectedUserIds = [];
    if (_memberMs) _memberMs.setSelected([]);
    document.getElementById('filter-q').value = '';
    _selectedActions.clear();
    document.querySelectorAll('#filter-actions .chip').forEach(c => c.classList.remove('chip-active'));
    document.getElementById('filter-date-preset').value = 'this-week';
    applyDatePreset('this-week');
  };

  async function initAuditFilters() {
    if (_filtersInitialized) return;
    _filtersInitialized = true;
    const container = document.getElementById('audit-member-filter');
    if (container && typeof mountCohortMultiselect === 'function') {
      _memberMs = mountCohortMultiselect(container, {
        onChange: (ids) => { _selectedUserIds = ids; loadAuditLog(); },
      });
    }
    const chipBar = document.getElementById('filter-actions');
    chipBar.innerHTML = ACTION_TYPES.map(a =>
      `<span class="chip" data-action="${a}" onclick="toggleActionChip('${a}')">${ACTION_LABEL[a] ?? a}</span>`
    ).join('');
  }

  function dateLabel(yyyy_mm_dd) {
    const today = new Date(); today.setHours(0,0,0,0);
    const yest  = new Date(today); yest.setDate(yest.getDate() - 1);
    if (yyyy_mm_dd === isoDay(today)) return 'Today';
    if (yyyy_mm_dd === isoDay(yest))  return 'Yesterday';
    const d = new Date(yyyy_mm_dd + 'T00:00:00');
    return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  }

  window.loadAuditLog = async function loadAuditLog() {
    try {
      const params = buildAuditFilterParams();
      const qs = params.toString();
      const rows = await api.get('/api/audit/log' + (qs ? '?' + qs : ''));
      const body = document.getElementById('audit-body');
      const countEl = document.getElementById('audit-result-count');
      if (countEl) countEl.textContent = `${rows.length} event${rows.length === 1 ? '' : 's'}`;

      if (!rows.length) {
        body.innerHTML = '<div class="log-empty">No entries match the current filters</div>';
        return;
      }

      const html = [];
      let lastDay = null;
      for (const r of rows) {
        const day = r.timestamp.slice(0, 10);
        const time = r.timestamp.slice(11);
        if (day !== lastDay) {
          html.push(`<div class="log-date-divider">${esc(dateLabel(day))}</div>`);
          lastDay = day;
        }
        const isIn  = IN_ACTIONS.has(r.action);
        const label = ACTION_LABEL[r.action] ?? r.action;
        const clickable = r.user_id != null;
        const argName = escAttr(r.name);
        html.push(`
          <div class="log-row${clickable ? ' log-row-clickable' : ''}"
               ${clickable ? `onclick="openContextModal(${r.user_id}, '${day}T${time}:00', '${argName}')"` : ''}
               title="${clickable ? '±30 min around this event' : 'User no longer exists'}">
            <div class="log-icon ${isIn ? 'log-in' : 'log-out'}">${isIn ? '+' : '×'}</div>
            <div class="log-name">${esc(r.name)}</div>
            <div class="log-ts">${esc(time)}</div>
            <div class="status-pill ${isIn ? 'pill-in' : 'pill-out'}">${esc(label)}</div>
          </div>`);
      }
      body.innerHTML = html.join('');
    } catch (err) {
      console.error('loadAuditLog error:', err);
    }
  };

  window.exportAuditCsv = function exportAuditCsv() {
    const qs = buildAuditFilterParams().toString();
    window.location = '/api/audit/export.csv' + (qs ? '?' + qs : '');
  };

  /* ── Context modal ── */

  window.openContextModal = async function openContextModal(userId, isoTs, name) {
    document.getElementById('context-title').textContent =
      `Context — ${name} @ ${isoTs.slice(11, 16)} on ${isoTs.slice(0, 10)}`;
    const body = document.getElementById('context-body');
    body.innerHTML = '<div class="log-empty">Loading…</div>';
    document.getElementById('context-modal').classList.remove('hidden');
    const btn = document.getElementById('context-profile-btn');
    if (btn) btn.onclick = () => { closeContextModal(); openProfileModal(userId); };

    try {
      const center = new Date(isoTs);
      const start = new Date(center.getTime() - 30 * 60 * 1000);
      const end   = new Date(center.getTime() + 30 * 60 * 1000);
      const toIso = (d) => d.toISOString().slice(0, 19);
      const rows = await api.get(
        `/api/audit/log?user_id=${userId}&start=${toIso(start)}&end=${toIso(end)}&limit=200`
      );

      if (!rows.length) {
        body.innerHTML = '<div class="log-empty">No surrounding events</div>';
        return;
      }
      body.innerHTML = rows.map(r => {
        const isIn = IN_ACTIONS.has(r.action);
        const label = ACTION_LABEL[r.action] ?? r.action;
        const time = r.timestamp.slice(11);
        return `
          <div class="log-row">
            <div class="log-icon ${isIn ? 'log-in' : 'log-out'}">${isIn ? '+' : '×'}</div>
            <div class="log-name">${esc(r.name)}</div>
            <div class="log-ts">${esc(time)}</div>
            <div class="status-pill ${isIn ? 'pill-in' : 'pill-out'}">${esc(label)}</div>
          </div>`;
      }).join('');
    } catch (err) {
      console.error('openContextModal error:', err);
      body.innerHTML = '<div class="log-empty">Failed to load context</div>';
    }
  };

  window.closeContextModal = function closeContextModal() {
    document.getElementById('context-modal').classList.add('hidden');
  };

  window.closeContextModalOnBg = function closeContextModalOnBg(event) {
    if (event.target === document.getElementById('context-modal')) closeContextModal();
  };
})();
