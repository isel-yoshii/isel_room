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
  const _selectedActions = new Set();
  let _filterDebounce = null;
  let _filtersInitialized = false;

  window.loadActivity = async function loadActivity() {
    await Promise.all([initAuditFilters(), loadAuditLog()]);
  };

  window.buildAuditFilterParams = function buildAuditFilterParams() {
    const params = new URLSearchParams();
    const uid = document.getElementById('filter-user')?.value;
    if (uid) params.set('user_id', uid);
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
    document.getElementById('filter-user').value  = '';
    document.getElementById('filter-start').value = '';
    document.getElementById('filter-end').value   = '';
    document.getElementById('filter-q').value     = '';
    _selectedActions.clear();
    document.querySelectorAll('#filter-actions .chip').forEach(c => c.classList.remove('chip-active'));
    loadAuditLog();
  };

  async function initAuditFilters() {
    if (_filtersInitialized) return;
    _filtersInitialized = true;
    try {
      const users = await api.get('/api/users');
      const sel = document.getElementById('filter-user');
      users.forEach(u => {
        const opt = document.createElement('option');
        opt.value = u.id;
        opt.textContent = u.name;
        sel.appendChild(opt);
      });
    } catch (err) {
      console.error('initAuditFilters users error:', err);
    }
    const chipBar = document.getElementById('filter-actions');
    chipBar.innerHTML = ACTION_TYPES.map(a =>
      `<span class="chip" data-action="${a}" onclick="toggleActionChip('${a}')">${ACTION_LABEL[a] ?? a}</span>`
    ).join('');
  }

  window.loadAuditLog = async function loadAuditLog() {
    try {
      const params = buildAuditFilterParams();
      const qs = params.toString();
      const rows = await api.get('/api/audit/log' + (qs ? '?' + qs : ''));
      const body = document.getElementById('audit-body');

      if (!rows.length) {
        const hasFilters = params.toString().length > 0;
        body.innerHTML = `<div class="log-empty">${hasFilters ? 'No entries match the current filters' : 'No Admin Actions Recorded Yet'}</div>`;
        return;
      }

      body.innerHTML = rows.map(r => {
        const isIn  = IN_ACTIONS.has(r.action);
        const label = ACTION_LABEL[r.action] ?? r.action;
        const clickable = r.user_id != null;
        return `
          <div class="log-row${clickable ? ' log-row-clickable' : ''}"
               ${clickable ? `onclick="openProfileModal(${r.user_id})"` : ''}
               title="${clickable ? 'Open user profile' : 'User no longer exists'}">
            <div class="log-icon ${isIn ? 'log-in' : 'log-out'}">${isIn ? '+' : '×'}</div>
            <div class="log-name">${esc(r.name)}</div>
            <div class="log-ts">${esc(r.timestamp)}</div>
            <div class="status-pill ${isIn ? 'pill-in' : 'pill-out'}">${esc(label)}</div>
          </div>`;
      }).join('');
    } catch (err) {
      console.error('loadAuditLog error:', err);
    }
  };

  window.exportAuditCsv = function exportAuditCsv() {
    const qs = buildAuditFilterParams().toString();
    window.location = '/api/audit/export.csv' + (qs ? '?' + qs : '');
  };
})();
