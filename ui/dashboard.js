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
      grid.innerHTML = '<div class="grid-empty">no members registered yet</div>';
    } else {
      /* Sort: present first */
      const sorted = [...users].sort((a, b) =>
        (presentNames.has(b.name) ? 1 : 0) - (presentNames.has(a.name) ? 1 : 0)
      );
      grid.innerHTML = sorted.map((u, i) => {
        const here = presentNames.has(u.name);
        const dur  = durationMap[u.name] ?? '–';
        return `
          <div class="member-card ${here ? 'present' : 'absent'}">
            <div class="avatar ${avColor(i)}">${initials(u.name)}</div>
            <div class="member-name">${u.name}</div>
            <div class="member-time">${here ? dur : '–'}</div>
            <div class="status-pill ${here ? 'pill-in' : 'pill-out'}">${here ? 'in lab' : 'out'}</div>
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
      grid.innerHTML = '<div class="log-empty">no members registered yet</div>';
      return;
    }

    grid.innerHTML = users.map((u, i) => {
      const isAdmin = u.type === '管理者';
      return `
        <div class="user-row">
          <div class="avatar ${avColor(i)}" style="width:36px;height:36px;font-size:12px;">
            ${initials(u.name)}
          </div>
          <div class="user-info">
            <div class="user-name">${u.name}</div>
            <div class="user-role">
              ${u.type}
              <span class="role-badge ${isAdmin ? 'badge-admin' : 'badge-student'}">
                ${isAdmin ? 'admin' : 'student'}
              </span>
            </div>
          </div>
          <div class="status-dot ${u.status ? 'in' : 'out'}" title="${u.status ? 'in lab' : 'out'}"></div>
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
      body.innerHTML = '<div class="log-empty">no admin actions recorded yet</div>';
      return;
    }

    body.innerHTML = rows.map(r => {
      const isReg = r.action === 'REGISTER';
      return `
        <div class="log-row">
          <div class="log-icon ${isReg ? 'log-in' : 'log-out'}">${isReg ? '+' : '×'}</div>
          <div class="log-name">${r.name}</div>
          <div class="log-ts">${r.timestamp}</div>
          <div class="status-pill ${isReg ? 'pill-in' : 'pill-out'}">
            ${isReg ? 'registered' : 'deleted'}
          </div>
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
    logBody.innerHTML = '<div class="log-empty">no activity recorded</div>';
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
        ${l.event_type === 'IN' ? 'check-in' : 'check-out'}
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
  content.innerHTML = '<div class="log-empty">loading…</div>';
  try {
    const data = await api.get(`/api/stats/monthly?year=${_statsYear}&month=${_statsMonth}`);
    renderStats(data);
  } catch (err) {
    console.error('loadStats error:', err);
  }
}

function renderStats(data) {
  const content = document.getElementById('stats-content');
  if (!data.length) {
    content.innerHTML = '<div class="log-empty">no activity recorded this month</div>';
    return;
  }

  const fmt = mins => {
    const h = Math.floor(mins / 60), m = mins % 60;
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
  };

  content.innerHTML = `
    <div class="stats-table">
      <div class="stats-header">
        <div>Member</div>
        <div>Sessions</div>
        <div>Total time</div>
        <div>Avg / session</div>
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

/* ── Sub-tab switching (Overview | Admin | Stats) ───── */

const PAGE_META = {
  overview: { title: 'Overview',    subtitle: "Today's lab activity" },
  stats:    { title: 'Statistics',  subtitle: 'Monthly attendance data' },
  admin:    { title: 'Admin',       subtitle: 'Manage members and access' },
};

function switchDashTab(name, btn) {
  if (name === 'admin') {
    checkAdminAndProceed(() => activateDashTab('admin', btn));
    return;
  }
  activateDashTab(name, btn);
  if (name === 'stats') loadStats();
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
    msg.textContent = 'Enter a PIN';
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
    msg.textContent = 'Server error';
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
      msg.textContent = 'Camera access denied';
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
    msg.textContent = 'Please enter a name';
    msg.className   = 'modal-msg err';
    return;
  }

  if (!_regStream) {
    msg.textContent = 'Camera not available';
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
      msg.textContent = data.message || 'Registration failed';
      msg.className   = 'modal-msg err';
    }
  } catch {
    msg.textContent = 'Server error — please try again';
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
          callbacks: { label: ctx => `${ctx.raw} check-ins` }
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
          callbacks: { label: ctx => `${ctx.raw}h this month` }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10, family: 'DM Mono' }, color: '#A09090' } },
        y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.04)' }, ticks: { font: { size: 10, family: 'DM Mono' }, color: '#A09090' } }
      }
    }
  });
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
