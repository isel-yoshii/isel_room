/*
 * dashboard.js — Dashboard screen logic.
 *
 * Covers:
 *   - loadDashboard / loadOverview : fetch + render presence stats, member grid, activity log
 *   - loadAdmin                    : fetch + render full member list
 *   - switchDashTab                : toggle between Dashboard | Admin sub-pages
 *   - openRegModal / closeRegModal : registration modal camera lifecycle
 *   - captureAndRegister           : POST to /api/register
 *
 * Depends on app.js (api, captureFrame).
 */

/* ── Role helpers ────────────────────────────────────── */

const STUDENT_TYPES  = new Set(['B4', 'M1', 'M2', 'Intern']);
const isTeacher   = t => t === '先生';
const isStudent   = t => STUDENT_TYPES.has(t);
const isGraduated = t => t === '卒業';

function roleBadgeClass(type) {
  if (isTeacher(type))   return 'badge-admin';
  if (isGraduated(type)) return 'badge-grad';
  return 'badge-student';
}

/* ── Last-seen formatter ─────────────────────────────── */

function formatLastSeen(iso) {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const mins  = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days  = Math.floor(diff / 86400000);
  if (mins  < 60)  return `${mins}m ago`;
  if (hours < 24)  return `${hours}h ago`;
  if (days  === 1) return 'yesterday';
  return `${days} days ago`;
}

/* ── Avatar colour palette (cycles by index) ─────────── */

const AV_COLORS = ['av-teal', 'av-blue', 'av-amber', 'av-pink', 'av-purple'];
const avColor   = i => AV_COLORS[i % AV_COLORS.length];

function initials(name) {
  return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

/* ── Top-level load (called by switchScreen in app.js) ── */

async function loadDashboard() {
  await Promise.all([loadOverview(), loadLogSection(), loadAdmin()]);
}

/* ── Overview tab ────────────────────────────────────── */

async function loadOverview() {
  try {
    const [present, log, users, todayStats] = await Promise.all([
      api.get('/api/present-detailed'),
      api.get('/api/log/today'),
      api.get('/api/users'),
      api.get('/api/stats/today'),
    ]);

    /* Stats */
    document.getElementById('stat-in').textContent    = present.length;
    document.getElementById('stat-today').textContent = todayStats.unique_checkins;
    document.getElementById('stat-total').textContent = users.length;

    /* Member grid — all members, present ones highlighted */
    const presentNames = new Set(present.map(u => u.name));
    const durationMap  = Object.fromEntries(present.map(u => [u.name, u.duration]));

    const grid = document.getElementById('member-grid');
    if (!users.length) {
      grid.innerHTML = '<div class="grid-empty">No Members Registered Yet</div>';
    } else {
      /* Sort: present first */
      const sorted = [...users].sort((a, b) =>
        (presentNames.has(b.name) ? 1 : 0) - (presentNames.has(a.name) ? 1 : 0)
      );
      grid.innerHTML = sorted.map((u, i) => {
        const here = presentNames.has(u.name);
        const dur  = durationMap[u.name] ?? '–';
        const timeLabel = here ? dur : (formatLastSeen(u.last_seen) || '–');
        return `
          <div class="member-card ${here ? 'present' : 'absent'}" onclick="openProfileModal(${u.id})" style="cursor:pointer">
            <div class="avatar ${avColor(i)}">${initials(u.name)}</div>
            <div class="member-name">${u.name}</div>
            <div class="member-time">${timeLabel}</div>
            <div class="status-pill ${here ? 'pill-in' : 'pill-out'}">${here ? 'In Lab' : 'Out'}</div>
          </div>`;
      }).join('');
    }

    loadCharts();

  } catch (err) {
    console.error('loadOverview error:', err);
  }
}

/* ── Admin tab ───────────────────────────────────────── */

async function loadAdmin() {
  await Promise.all([loadAdminUsers(), loadAuditLog()]);
}

async function loadAdminUsers() {
  try {
    const users = await api.get('/api/users');
    const grid  = document.getElementById('admin-grid');

    if (!users.length) {
      grid.innerHTML = '<div class="log-empty">No Members Registered Yet</div>';
      return;
    }

    grid.innerHTML = users.map((u, i) => {
      const grad = isGraduated(u.type);
      return `
        <div class="user-row ${grad ? 'user-row-grad' : ''}" id="user-row-${u.id}">
          <div class="avatar ${avColor(i)}" style="width:36px;height:36px;font-size:12px;${grad ? 'opacity:0.45' : ''}">
            ${initials(u.name)}
          </div>
          <div class="user-info">
            <div class="user-name">${u.name}</div>
            <div class="user-role">
              <span class="role-badge ${roleBadgeClass(u.type)}">${u.type}</span>
              <span class="face-badge ${u.has_face ? 'badge-face-ok' : 'badge-face-none'}">
                ${u.has_face ? 'Enrolled' : 'No Face'}
              </span>
            </div>
          </div>
          <div class="status-dot ${u.status ? 'in' : 'out'}" title="${u.status ? 'In Lab' : 'Out'}"></div>
          ${u.status ? `<button class="force-btn" onclick="forceCheckout(${u.id}, '${u.name}')">Force Out</button>` : ''}
          <button class="icon-btn" onclick="openEditUserForm(${u.id}, '${u.name.replace(/'/g,"\\'")}', '${u.type}')" title="Edit Name / Role">✎</button>
          <button class="icon-btn" onclick="openFaceReregModal(${u.id}, '${u.name.replace(/'/g,"\\'")}')" title="Re-Register Face">⊙</button>
          <button class="del-btn" onclick="deleteUser(${u.id}, '${u.name}')">Delete</button>
        </div>`;
    }).join('');

  } catch (err) {
    console.error('loadAdminUsers error:', err);
  }
}

async function loadAuditLog() {
  try {
    const rows = await api.get('/api/audit/log');
    const body = document.getElementById('audit-body');

    if (!rows.length) {
      body.innerHTML = '<div class="log-empty">No Admin Actions Recorded Yet</div>';
      return;
    }

    const ACTION_LABEL = {
      REGISTER: 'Registered', DELETE: 'Deleted',
      CHECKIN: 'Check-In', CHECKOUT: 'Check-Out',
      MANUAL_CHECKIN: 'Manual In', MANUAL_CHECKOUT: 'Manual Out',
      AUTO_CHECKOUT: 'Auto-Out', FORCE_CHECKOUT: 'Force-Out',
      PROMOTE: 'Promoted',
    };
    const IN_ACTIONS = new Set(['REGISTER', 'CHECKIN', 'MANUAL_CHECKIN']);

    body.innerHTML = rows.map(r => {
      const isIn = IN_ACTIONS.has(r.action);
      const label = ACTION_LABEL[r.action] ?? r.action;
      return `
        <div class="log-row">
          <div class="log-icon ${isIn ? 'log-in' : 'log-out'}">${isIn ? '+' : '×'}</div>
          <div class="log-name">${r.name}</div>
          <div class="log-ts">${r.timestamp}</div>
          <div class="status-pill ${isIn ? 'pill-in' : 'pill-out'}">${label}</div>
        </div>`;
    }).join('');
  } catch (err) {
    console.error('loadAuditLog error:', err);
  }
}

/* ── Activity log with date navigation ───────────────── */

let _logDateOffset = 0;

function changeLogDate(delta) {
  _logDateOffset += delta;
  loadLogSection();
}

async function loadLogSection() {
  const nextBtn = document.getElementById('log-nav-next');
  const labelEl = document.getElementById('log-date-label');
  if (nextBtn) nextBtn.disabled = _logDateOffset >= 0;

  let url;
  if (_logDateOffset === 0) {
    url = '/api/log/today';
    if (labelEl) labelEl.textContent = 'Today';
  } else {
    const d = new Date();
    d.setDate(d.getDate() + _logDateOffset);
    const dateStr = d.toISOString().split('T')[0];
    url = `/api/log?date=${dateStr}`;
    if (labelEl) {
      labelEl.textContent = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
  }

  try {
    const log = await api.get(url);
    renderLogRows(log);
  } catch (err) {
    console.error('loadLogSection error:', err);
  }
}

function renderLogRows(log) {
  const logBody = document.getElementById('log-body');
  if (!log.length) {
    logBody.innerHTML = '<div class="log-empty">No Activity Recorded</div>';
    return;
  }
  logBody.innerHTML = log.map(l => `
    <div class="log-row">
      <div class="log-icon ${l.event_type === 'IN' ? 'log-in' : 'log-out'}">
        ${l.event_type === 'IN' ? '↑' : '↓'}
      </div>
      <div class="log-name">${l.name}</div>
      <div class="log-ts">${l.timestamp}</div>
      <div class="status-pill ${l.event_type === 'IN' ? 'pill-in' : 'pill-out'}">
        ${l.event_type === 'IN' ? 'Check-In' : 'Check-Out'}
      </div>
    </div>`).join('');
}

/* ── Monthly stats tab ───────────────────────────────── */

let _statsYear  = new Date().getFullYear();
let _statsMonth = new Date().getMonth() + 1;

function updateStatsMonthLabel() {
  const label = new Date(_statsYear, _statsMonth - 1, 1)
    .toLocaleDateString('en-US', { year: 'numeric', month: 'long' });
  document.getElementById('stats-month-label').textContent = label;

  const now = new Date();
  const nextBtn = document.getElementById('stats-nav-next');
  if (nextBtn) {
    nextBtn.disabled =
      _statsYear > now.getFullYear() ||
      (_statsYear === now.getFullYear() && _statsMonth >= now.getMonth() + 1);
  }
}

function changeStatsMonth(delta) {
  _statsMonth += delta;
  if (_statsMonth > 12) { _statsMonth = 1;  _statsYear++; }
  if (_statsMonth < 1)  { _statsMonth = 12; _statsYear--; }
  loadStats();
}

async function loadStats() {
  updateStatsMonthLabel();
  const content = document.getElementById('stats-content');
  content.innerHTML = '<div class="log-empty">Loading…</div>';
  try {
    const data = await api.get(`/api/stats/monthly?year=${_statsYear}&month=${_statsMonth}`);
    renderStats(data);
  } catch (err) {
    console.error('loadStats error:', err);
  }
}

function fmtMins(mins) {
  const h = Math.floor(mins / 60), m = mins % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function renderStats(data) {
  const content = document.getElementById('stats-content');
  if (!data.length) {
    content.innerHTML = '<div class="log-empty">No Activity Recorded This Month</div>';
    return;
  }

  const fmt = fmtMins;

  content.innerHTML = `
    <div class="stats-table">
      <div class="stats-header">
        <div>Member</div>
        <div>Sessions</div>
        <div>Total Time</div>
        <div>Avg / Session</div>
      </div>
      ${data.map((u, i) => `
        <div class="stats-row">
          <div class="stats-user">
            <div class="avatar ${avColor(i)}" style="width:30px;height:30px;font-size:10px;">${initials(u.name)}</div>
            <div>
              <div class="stats-name">${u.name}</div>
              <div class="stats-type">${u.type}</div>
            </div>
          </div>
          <div class="stats-value">${u.sessions}</div>
          <div class="stats-value highlight">${fmt(u.total_minutes)}</div>
          <div class="stats-value">${u.sessions ? fmt(Math.round(u.total_minutes / u.sessions)) : '–'}</div>
        </div>`).join('')}
    </div>`;
}

/* ── Points tab ─────────────────────────────────────── */

let _pointsYear  = new Date().getFullYear();
let _pointsMonth = new Date().getMonth() + 1;

const RANK_COLORS = ['#F5A623', '#9B9B9B', '#8B6340'];

function updatePointsMonthLabel() {
  const label = new Date(_pointsYear, _pointsMonth - 1, 1)
    .toLocaleDateString('en-US', { year: 'numeric', month: 'long' });
  document.getElementById('points-month-label').textContent = label;

  const now = new Date();
  const nextBtn = document.getElementById('points-nav-next');
  if (nextBtn) {
    nextBtn.disabled =
      _pointsYear > now.getFullYear() ||
      (_pointsYear === now.getFullYear() && _pointsMonth >= now.getMonth() + 1);
  }
}

function changePointsMonth(delta) {
  _pointsMonth += delta;
  if (_pointsMonth > 12) { _pointsMonth = 1;  _pointsYear++; }
  if (_pointsMonth < 1)  { _pointsMonth = 12; _pointsYear--; }
  loadPoints();
}

async function loadPoints() {
  updatePointsMonthLabel();
  const content = document.getElementById('points-content');
  content.innerHTML = '<div class="log-empty">Loading…</div>';
  try {
    const [monthly, total] = await Promise.all([
      api.get(`/api/stats/points?year=${_pointsYear}&month=${_pointsMonth}`),
      api.get('/api/stats/points/total'),
    ]);
    renderPoints(monthly, total);
  } catch (err) {
    console.error('loadPoints error:', err);
  }
}

function renderPointsTable(data, emptyMsg) {
  if (!data.length) return `<div class="log-empty">${emptyMsg}</div>`;
  return `
    <div class="points-table">
      <div class="points-header">
        <div>Rank</div>
        <div>Member</div>
        <div>Days Present</div>
      </div>
      ${data.map((u, i) => {
        const rankColor = RANK_COLORS[i] ?? 'var(--color-text-secondary)';
        const rankLabel = i < 3 ? ['1st', '2nd', '3rd'][i] : `${i + 1}th`;
        return `
        <div class="points-row ${i < 3 ? 'points-top' : ''}">
          <div class="points-rank" style="color:${rankColor}">${rankLabel}</div>
          <div class="stats-user">
            <div class="avatar ${avColor(i)}" style="width:30px;height:30px;font-size:10px;">${initials(u.name)}</div>
            <div>
              <div class="stats-name">${u.name}</div>
              <div class="stats-type">${u.type}</div>
            </div>
          </div>
          <div class="points-value">${u.points} <span class="points-unit">day${u.points !== 1 ? 's' : ''}</span></div>
        </div>`;
      }).join('')}
    </div>`;
}

function renderPoints(monthly, total) {
  const content = document.getElementById('points-content');
  content.innerHTML = `
    <div class="section-label" style="margin-bottom:8px">This Month</div>
    ${renderPointsTable(monthly, 'No Activity Recorded This Month')}
    <div class="section-label" style="margin-top:24px;margin-bottom:8px">All-Time</div>
    ${renderPointsTable(total, 'No Activity Recorded Yet')}`;
}

/* ── Sub-tab switching (Overview | Admin | Stats | Points) ── */

const PAGE_META = {
  overview: { title: 'Overview',    subtitle: "Today's Lab Activity" },
  stats:    { title: 'Statistics',  subtitle: 'Monthly Attendance Data' },
  points:   { title: 'Points',      subtitle: 'Daily Presence Scoring' },
  admin:    { title: 'Admin',       subtitle: 'Manage Members And Access' },
};

function switchDashTab(name, btn) {
  if (name === 'admin') {
    checkAdminAndProceed(() => activateDashTab('admin', btn));
    return;
  }
  activateDashTab(name, btn);
  if (name === 'stats')   loadStats();
  if (name === 'points')  loadPoints();
}

/* ── Tab activation helper ───────────────────────────── */

function activateDashTab(name, btn) {
  document.querySelectorAll('.db-page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.sidebar-tab').forEach(t => t.classList.remove('active'));
  document.getElementById('db-' + name).classList.add('active');
  btn.classList.add('active');

  const meta = PAGE_META[name];
  if (meta) {
    const titleEl    = document.getElementById('page-title');
    const subtitleEl = document.getElementById('page-subtitle');
    if (titleEl)    titleEl.textContent    = meta.title;
    if (subtitleEl) subtitleEl.textContent = meta.subtitle;
  }
}

async function checkAdminAndProceed(callback) {
  try {
    const status = await api.get('/api/admin/status');
    if (status.authenticated) {
      callback();
    } else {
      openPinModal(callback);
    }
  } catch {
    openPinModal(callback);
  }
}

/* ── Admin PIN modal ─────────────────────────────────── */

let _pinCallback = null;

function openPinModal(callback) {
  _pinCallback = callback;
  document.getElementById('pin-input').value = '';
  const msg = document.getElementById('pin-msg');
  msg.textContent = '';
  msg.className = 'modal-msg';
  document.getElementById('pin-modal').classList.remove('hidden');
  setTimeout(() => document.getElementById('pin-input').focus(), 50);
}

function closePinModal() {
  document.getElementById('pin-modal').classList.add('hidden');
  _pinCallback = null;
}

function closePinModalOnBg(event) {
  if (event.target === document.getElementById('pin-modal')) closePinModal();
}

async function submitPin() {
  const pin   = document.getElementById('pin-input').value;
  const msg   = document.getElementById('pin-msg');
  const btn   = document.getElementById('btn-pin-submit');

  if (!pin) {
    msg.textContent = 'Enter A PIN';
    msg.className   = 'modal-msg err';
    return;
  }

  btn.disabled    = true;
  msg.textContent = '';

  try {
    const data = await api.post('/api/admin/login', { pin });
    if (data.success) {
      closePinModal();
      if (_pinCallback) _pinCallback();
    } else {
      msg.textContent = data.message || 'Wrong PIN';
      msg.className   = 'modal-msg err';
      document.getElementById('pin-input').value = '';
      document.getElementById('pin-input').focus();
    }
  } catch {
    msg.textContent = 'Server Error';
    msg.className   = 'modal-msg err';
  }

  btn.disabled = false;
}

async function adminLogout() {
  await api.post('/api/admin/logout', {});
  const overviewBtn = document.getElementById('sbt-overview');
  activateDashTab('overview', overviewBtn);
  loadOverview();
}

/* ── Registration modal ──────────────────────────────── */

let _regStream = null;

function openRegModal() {
  const modal = document.getElementById('reg-modal');
  modal.classList.remove('hidden');

  /* Reset form */
  document.getElementById('reg-name').value = '';
  const msg = document.getElementById('reg-msg');
  msg.textContent = '';
  msg.className   = 'modal-msg';

  /* Start modal camera (separate stream from kiosk) */
  navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    .then(stream => {
      _regStream = stream;
      document.getElementById('reg-video').srcObject = stream;
    })
    .catch(() => {
      msg.textContent = 'Camera Access Denied';
      msg.className   = 'modal-msg err';
    });
}

function closeRegModal() {
  document.getElementById('reg-modal').classList.add('hidden');
  if (_regStream) {
    _regStream.getTracks().forEach(t => t.stop());
    _regStream = null;
  }
}

function closeRegModalOnBg(event) {
  if (event.target === document.getElementById('reg-modal')) closeRegModal();
}

async function captureAndRegister() {
  const name     = document.getElementById('reg-name').value.trim();
  const userType = document.getElementById('reg-type').value;
  const msg      = document.getElementById('reg-msg');
  const btn      = document.getElementById('btn-register');

  if (!name) {
    msg.textContent = 'Please Enter A Name';
    msg.className   = 'modal-msg err';
    return;
  }

  if (!_regStream) {
    msg.textContent = 'Camera Not Available';
    msg.className   = 'modal-msg err';
    return;
  }

  /* Capture from the modal video (not the kiosk canvas) */
  const video  = document.getElementById('reg-video');
  const canvas = document.getElementById('capture-canvas');
  canvas.width  = video.videoWidth  || 640;
  canvas.height = video.videoHeight || 480;
  canvas.getContext('2d').drawImage(video, 0, 0);
  const image = canvas.toDataURL('image/jpeg', 0.85);

  btn.disabled    = true;
  msg.textContent = 'Processing…';
  msg.className   = 'modal-msg';

  try {
    const data = await api.post('/api/register', { name, user_type: userType, image });
    if (data.success) {
      msg.textContent = data.message || `${name} registered!`;
      msg.className   = 'modal-msg ok';
      setTimeout(() => { closeRegModal(); loadAdmin(); }, 1500);
    } else {
      msg.textContent = data.message || 'Registration Failed';
      msg.className   = 'modal-msg err';
    }
  } catch {
    msg.textContent = 'Server Error — Please Try Again';
    msg.className   = 'modal-msg err';
  }

  btn.disabled = false;
}

/* ── Charts (Chart.js) ───────────────────────────────── */

let _lineChart = null;
let _barChart  = null;

async function loadCharts() {
  if (typeof Chart === 'undefined') return;
  try {
    const [weekly, monthly] = await Promise.all([
      api.get('/api/stats/weekly'),
      api.get(`/api/stats/monthly?year=${new Date().getFullYear()}&month=${new Date().getMonth() + 1}`),
    ]);
    renderLineChart(weekly);
    renderBarChart(monthly.slice(0, 8));
  } catch (err) {
    console.error('loadCharts error:', err);
  }
}

function renderLineChart(data) {
  const canvas = document.getElementById('chart-line');
  if (!canvas) return;
  if (_lineChart) { _lineChart.destroy(); _lineChart = null; }
  _lineChart = new Chart(canvas, {
    type: 'line',
    data: {
      labels: data.map(d => d.date),
      datasets: [{
        data: data.map(d => d.count),
        borderColor: '#C83B3B',
        backgroundColor: 'rgba(200, 59, 59, 0.07)',
        fill: true,
        tension: 0.4,
        pointBackgroundColor: '#C83B3B',
        pointBorderColor: '#fff',
        pointBorderWidth: 2,
        pointRadius: 4,
        pointHoverRadius: 6,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#fff',
          titleColor: '#1A1A1A',
          bodyColor: '#A09090',
          borderColor: '#F2E5E4',
          borderWidth: 1,
          callbacks: { label: ctx => `${ctx.raw} Check-Ins` }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10, family: 'DM Mono' }, color: '#A09090' } },
        y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.04)' }, ticks: { stepSize: 1, font: { size: 10, family: 'DM Mono' }, color: '#A09090' } }
      }
    }
  });
}

function renderBarChart(data) {
  const canvas = document.getElementById('chart-bar');
  if (!canvas) return;
  if (_barChart) { _barChart.destroy(); _barChart = null; }
  if (!data.length) return;

  const maxMinutes = Math.max(...data.map(d => d.total_minutes));
  _barChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: data.map(d => d.name.split(' ')[0]),
      datasets: [{
        data: data.map(d => +(d.total_minutes / 60).toFixed(1)),
        backgroundColor: data.map(d =>
          d.total_minutes === maxMinutes ? '#C83B3B' : '#FDECEA'
        ),
        borderRadius: 6,
        borderSkipped: false,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#fff',
          titleColor: '#1A1A1A',
          bodyColor: '#A09090',
          borderColor: '#F2E5E4',
          borderWidth: 1,
          callbacks: { label: ctx => `${ctx.raw}h This Month` }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10, family: 'DM Mono' }, color: '#A09090' } },
        y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.04)' }, ticks: { font: { size: 10, family: 'DM Mono' }, color: '#A09090' } }
      }
    }
  });
}

async function forceCheckout(userId, userName) {
  if (!confirm(`Force "${userName}" out of the lab?`)) return;
  try {
    const res = await api.post(`/api/admin/force-checkout/${userId}`, {});
    if (res.success) {
      loadAdmin();
      loadOverview();
    } else {
      alert(`Failed: ${res.message}`);
    }
  } catch (e) {
    console.error('forceCheckout error:', e);
    alert('Network error occurred.');
  }
}

async function deleteUser(userId, userName) {
  if (!confirm(`Are you sure you want to delete "${userName}"?\nThis action cannot be undone.`)) {
    return;
  }

  try {
    const res = await fetch(`/api/user/${userId}`, {
      method: 'DELETE',
    }).then(r => r.json());

    if (res.success) {
      // 削除成功時は、画面のリストと統計を再読み込みして最新化
      loadAdmin();
      loadOverview();
    } else {
      alert(`Failed to delete: ${res.message}`);
    }
  } catch (e) {
    console.error("Delete error:", e);
    alert('Network error occurred.');
  }
}

/* ── Edit user name / role ───────────────────────────── */

function openEditUserForm(userId, currentName, currentType) {
  const row = document.getElementById(`user-row-${userId}`);
  if (!row) return;

  const ROLE_OPTIONS = ['先生', 'B4', 'M1', 'M2', 'Intern', '卒業']
    .map(t => `<option value="${t}" ${t === currentType ? 'selected' : ''}>${t}</option>`)
    .join('');

  row.innerHTML = `
    <div class="edit-user-form" style="grid-column:1/-1;display:flex;gap:8px;align-items:center;padding:4px 0;">
      <input class="edit-input" id="edit-name-${userId}" value="${currentName}" style="flex:1" />
      <select class="edit-input" id="edit-type-${userId}">${ROLE_OPTIONS}</select>
      <button class="icon-btn ok-btn" onclick="saveEditUser(${userId})">✓</button>
      <button class="icon-btn" onclick="loadAdminUsers()">✗</button>
    </div>`;
}

async function saveEditUser(userId) {
  const name     = document.getElementById(`edit-name-${userId}`)?.value.trim();
  const userType = document.getElementById(`edit-type-${userId}`)?.value;
  if (!name || !userType) return;
  try {
    const r = await fetch(`/api/user/${userId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, user_type: userType }),
    }).then(r => r.json());
    if (r.success) { loadAdminUsers(); loadOverview(); }
    else alert(`Failed: ${r.message}`);
  } catch (e) { console.error(e); }
}

/* ── Face re-registration ────────────────────────────── */

let _faceReregStream = null;
let _faceReregUserId = null;

function openFaceReregModal(userId, userName) {
  _faceReregUserId = userId;
  document.getElementById('face-rereg-title').textContent = `Re-Register Face — ${userName}`;
  const msg = document.getElementById('face-rereg-msg');
  msg.textContent = '';
  msg.className   = 'modal-msg';

  navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    .then(stream => {
      _faceReregStream = stream;
      document.getElementById('face-rereg-video').srcObject = stream;
    })
    .catch(() => {
      msg.textContent = 'Camera Access Denied';
      msg.className   = 'modal-msg err';
    });

  document.getElementById('face-rereg-modal').classList.remove('hidden');
}

function closeFaceReregModal() {
  document.getElementById('face-rereg-modal').classList.add('hidden');
  if (_faceReregStream) {
    _faceReregStream.getTracks().forEach(t => t.stop());
    _faceReregStream = null;
  }
  _faceReregUserId = null;
}

function closeFaceReregModalOnBg(event) {
  if (event.target === document.getElementById('face-rereg-modal')) closeFaceReregModal();
}

async function captureAndReregFace() {
  if (!_faceReregUserId || !_faceReregStream) return;
  const video  = document.getElementById('face-rereg-video');
  const canvas = document.getElementById('capture-canvas');
  canvas.width  = video.videoWidth  || 640;
  canvas.height = video.videoHeight || 480;
  canvas.getContext('2d').drawImage(video, 0, 0);
  const image = canvas.toDataURL('image/jpeg', 0.85);

  const msg = document.getElementById('face-rereg-msg');
  const btn = document.getElementById('btn-face-rereg');
  btn.disabled    = true;
  msg.textContent = 'Processing…';
  msg.className   = 'modal-msg';

  try {
    const r = await fetch(`/api/user/${_faceReregUserId}/face`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image }),
    }).then(r => r.json());

    if (r.success) {
      msg.textContent = 'Face Updated';
      msg.className   = 'modal-msg ok';
      setTimeout(() => { closeFaceReregModal(); loadAdminUsers(); }, 1200);
    } else {
      msg.textContent = r.message || 'Failed';
      msg.className   = 'modal-msg err';
    }
  } catch {
    msg.textContent = 'Server Error — Please Try Again';
    msg.className   = 'modal-msg err';
  }
  btn.disabled = false;
}

/* ── Manual student promotion ────────────────────────── */

async function runPromotion() {
  if (!confirm('Promote all students?\nB4 → M1 · M1 → M2 · M2 → 卒業\n\nThis cannot be undone.')) return;
  try {
    const r = await fetch('/api/admin/promote-students', { method: 'POST' }).then(r => r.json());
    if (r.success) {
      const { B4, M1, M2 } = r.promoted;
      alert(`Promotion complete.\n${B4} B4 → M1 · ${M1} M1 → M2 · ${M2} M2 → 卒業`);
      loadAdminUsers();
    } else {
      alert(`Failed: ${r.message}`);
    }
  } catch (e) { alert('Network Error Occurred.'); }
}

/* ── Member profile modal ────────────────────────────── */

async function openProfileModal(userId) {
  _currentProfileUserId = userId;
  try {
    const data = await api.get(`/api/user/${userId}/profile`);

    document.getElementById('profile-name').textContent = data.name;

    document.getElementById('profile-badges').innerHTML = `
      <span class="role-badge ${roleBadgeClass(data.type)}" style="margin-right:4px">
        ${data.type}
      </span>
      <span class="face-badge ${data.has_face ? 'badge-face-ok' : 'badge-face-none'}">
        ${data.has_face ? 'Enrolled' : 'No Face'}
      </span>`;

    const ms = data.monthly_stats;
    document.getElementById('profile-monthly').innerHTML = `
      <div class="profile-stats-row">
        <div class="profile-stat">
          <div class="profile-stat-val">${ms.sessions}</div>
          <div class="profile-stat-lbl">Sessions This Month</div>
        </div>
        <div class="profile-stat">
          <div class="profile-stat-val">${fmtMins(ms.total_minutes)}</div>
          <div class="profile-stat-lbl">Total Time This Month</div>
        </div>
        ${ms.sessions > 0 ? `<div class="profile-stat">
          <div class="profile-stat-val">${fmtMins(Math.round(ms.total_minutes / ms.sessions))}</div>
          <div class="profile-stat-lbl">Avg Per Session</div>
        </div>` : ''}
      </div>`;

    if (!data.recent_sessions.length) {
      document.getElementById('profile-sessions').innerHTML = '<div class="log-empty">No Sessions Recorded Yet</div>';
    } else {
      document.getElementById('profile-sessions').innerHTML = `
        <div class="profile-sess-table">
          <div class="profile-sess-header">
            <div>Date</div><div>In</div><div>Out</div><div>Duration</div><div>Method</div><div></div>
          </div>
          ${data.recent_sessions.map(s => `
            <div class="profile-sess-row" id="sess-row-${s.id}">
              <div>${s.date}</div>
              <div>${s.checked_in_at}</div>
              <div>${s.checked_out_at ?? '–'}</div>
              <div>${fmtMins(s.duration_minutes)}</div>
              <div>${s.check_in_method}</div>
              <div><button class="icon-btn" onclick="openEditSessionForm(${s.id}, '${s.checked_in_at_iso}', '${s.checked_out_at_iso ?? ''}')">✎</button></div>
            </div>`).join('')}
        </div>`;
    }

    document.getElementById('profile-modal').classList.remove('hidden');
  } catch (err) {
    console.error('openProfileModal error:', err);
  }
}

function closeProfileModal() {
  document.getElementById('profile-modal').classList.add('hidden');
}

function closeProfileModalOnBg(event) {
  if (event.target === document.getElementById('profile-modal')) closeProfileModal();
}

/* ── Session time editing ────────────────────────────── */

function openEditSessionForm(sessionId, inIso, outIso) {
  const row = document.getElementById(`sess-row-${sessionId}`);
  if (!row) return;
  row.innerHTML = `
    <div style="grid-column:1/-1;display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
      <label style="font-size:11px;color:var(--color-text-secondary)">In</label>
      <input type="datetime-local" class="edit-input" id="sess-in-${sessionId}"
             value="${inIso ? inIso.slice(0,16) : ''}" />
      <label style="font-size:11px;color:var(--color-text-secondary)">Out</label>
      <input type="datetime-local" class="edit-input" id="sess-out-${sessionId}"
             value="${outIso ? outIso.slice(0,16) : ''}" />
      <button class="icon-btn ok-btn" onclick="saveEditSession(${sessionId})">✓</button>
      <button class="icon-btn" onclick="openProfileModal(_currentProfileUserId)">✗</button>
    </div>`;
}

let _currentProfileUserId = null;

async function saveEditSession(sessionId) {
  const inVal  = document.getElementById(`sess-in-${sessionId}`)?.value;
  const outVal = document.getElementById(`sess-out-${sessionId}`)?.value;
  if (!inVal) return;
  try {
    const r = await fetch(`/api/session/${sessionId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        checked_in_at:  inVal  ? inVal  + ':00' : null,
        checked_out_at: outVal ? outVal + ':00' : null,
      }),
    }).then(r => r.json());
    if (r.success && _currentProfileUserId) openProfileModal(_currentProfileUserId);
    else alert(`Failed: ${r.message}`);
  } catch (e) { console.error(e); }
}

/* ── Dashboard sidebar keyboard shortcuts (1 / 2 / 3 / 4) ── */

document.addEventListener('keydown', (e) => {
  if (!document.getElementById('screen-dashboard').classList.contains('active')) return;
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return;
  const anyModalOpen = ['reg-modal', 'pin-modal', 'profile-modal']
    .some(id => !document.getElementById(id)?.classList.contains('hidden'));
  if (anyModalOpen) return;

  const tabMap = {
    '1': { name: 'overview', btnId: 'sbt-overview' },
    '2': { name: 'stats',    btnId: 'sbt-stats'    },
    '3': { name: 'points',   btnId: 'sbt-points'   },
    '4': { name: 'admin',    btnId: 'sbt-admin'    },
  };
  const target = tabMap[e.key];
  if (!target) return;
  const btn = document.getElementById(target.btnId);
  if (btn) switchDashTab(target.name, btn);
});
