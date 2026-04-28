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
  await Promise.all([loadOverview(), loadAdmin()]);
}

/* ── Overview tab ────────────────────────────────────── */

async function loadOverview() {
  try {
    const [present, log, users] = await Promise.all([
      api.get('/api/present-detailed'),
      api.get('/api/log/today'),
      api.get('/api/users'),
    ]);

    /* Stats */
    document.getElementById('stat-in').textContent    = present.length;
    document.getElementById('stat-today').textContent = log.filter(l => l.event_type === 'IN').length;
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

    /* Activity log */
    const today = new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric' });
    document.getElementById('log-header').textContent = `Activity — ${today}`;

    const logBody = document.getElementById('log-body');
    if (!log.length) {
      logBody.innerHTML = '<div class="log-empty">no activity recorded today</div>';
    } else {
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

  } catch (err) {
    console.error('loadOverview error:', err);
  }
}

/* ── Admin tab ───────────────────────────────────────── */

async function loadAdmin() {
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
        </div>`;
    }).join('');

  } catch (err) {
    console.error('loadAdmin error:', err);
  }
}

/* ── Sub-tab switching (Dashboard | Admin) ───────────── */

function switchDashTab(name, btn) {
  document.querySelectorAll('.db-page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.getElementById('db-' + name).classList.add('active');
  btn.classList.add('active');
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
