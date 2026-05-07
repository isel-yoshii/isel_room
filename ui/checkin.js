/*
 * checkin.js — Kiosk / check-in screen logic.
 *
 * State machine:
 *   idle  →  scanning  →  checkin | checkout | fail  →  (auto-reset to idle)
 *
 * Depends on app.js (api, captureFrame, loadMemberStrip via member-strip refresh).
 */

/* ── State definitions ───────────────────────────────── */

const CHECKIN_STATES = {
  idle: {
    tagClass: 'tag-idle',   dotClass: 'dot-gray',  tagText: 'waiting',
    name:     'Stand in front<br>of camera',
    sub:      'face recognition ready',
    faceClass: 'state-idle', scanLine: false,
    card: '', btnText: 'Scan Face', btnDisabled: false,
  },
  scanning: {
    tagClass: 'tag-scanning', dotClass: 'dot-amber', tagText: 'scanning',
    name:     'Scanning…',
    sub:      'hold still for a moment',
    faceClass: 'state-scanning', scanLine: true,
    card: '', btnText: 'Scanning…', btnDisabled: true,
  },
  fail: {
    tagClass: 'tag-fail', dotClass: 'dot-red', tagText: 'unknown face',
    name:     'Face not<br>recognised',
    sub:      'not registered in the system',
    faceClass: 'state-fail', scanLine: false,
    card: `
      <div class="checkin-card">
        <div class="checkin-avatar av-red">?</div>
        <div class="checkin-info">
          <div class="checkin-name">Unknown person</div>
          <div class="checkin-detail">ask an admin to register you</div>
        </div>
      </div>`,
    btnText: 'Try Again', btnDisabled: false,
  },
};

/* ── setState: updates every UI element for a given state ── */

function setState(key) {
  const s = CHECKIN_STATES[key];
  if (!s) return;

  const tag = document.getElementById('state-tag');
  tag.className = 'state-tag ' + s.tagClass;
  document.getElementById('state-dot').className = 'dot ' + s.dotClass;
  document.getElementById('tag-text').textContent = s.tagText;

  document.getElementById('state-name').innerHTML = s.name;
  document.getElementById('state-sub').textContent = s.sub;
  document.getElementById('result-card').innerHTML = s.card;

  document.getElementById('face-box').className = 'face-box ' + s.faceClass;
  document.getElementById('scan-line').style.display = s.scanLine ? 'block' : 'none';

  const btn = document.getElementById('btn-scan');
  btn.textContent = s.btnText;
  btn.disabled    = s.btnDisabled;
}

/* ── setStateResult: builds the success card after recognition ── */

function setStateResult(name, eventType) {
  const isIn   = eventType === 'IN';
  const initials = name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
  const time   = new Date().toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });

  const tag = document.getElementById('state-tag');
  tag.className = 'state-tag tag-success';
  document.getElementById('state-dot').className = 'dot dot-green';
  document.getElementById('tag-text').textContent = 'recognised';

  document.getElementById('state-name').innerHTML = isIn
    ? `Welcome,<br>${name}!`
    : `See you,<br>${name}!`;

  document.getElementById('state-sub').textContent = isIn
    ? `check-in recorded · ${time}`
    : `check-out recorded · ${time}`;

  document.getElementById('result-card').innerHTML = `
    <div class="checkin-card">
      <div class="checkin-avatar av-green">${initials}</div>
      <div class="checkin-info">
        <div class="checkin-name">${name}</div>
        <div class="checkin-detail">${isIn ? 'checked in' : 'checked out'}</div>
      </div>
      <div class="event-badge ${isIn ? 'badge-in' : 'badge-out'}">${isIn ? 'check-in' : 'check-out'}</div>
    </div>`;

  document.getElementById('face-box').className = 'face-box state-checkin';
  document.getElementById('scan-line').style.display = 'none';
  document.getElementById('btn-scan').textContent = 'Scan Next';
  document.getElementById('btn-scan').disabled    = false;
}

/* ── scanFace: one full scan → toggle cycle ─────────── */

async function scanFace() {
  setState('scanning');

  try {
    const image    = captureFrame('checkin-video');
    const authData = await api.post('/api/auth', { image });

    if (authData.matched) {
      const toggleData = await api.post('/api/toggle', { user_id: authData.user_id });
      setStateResult(authData.name, toggleData.event_type);
      loadMemberStrip();                    // refresh bottom strip immediately
      setTimeout(() => setState('idle'), 4000);
    } else {
      setState('fail');
      setTimeout(() => setState('idle'), 3000);
    }
  } catch {
    setState('idle');
  }
}

/* ── loadMemberStrip: populates the bottom presence bar ─ */

async function loadMemberStrip() {
  try {
    const users = await api.get('/api/present-detailed');
    const strip = document.getElementById('member-strip');

    if (!users.length) {
      strip.innerHTML = '<span class="strip-empty">nobody in the lab</span>';
      return;
    }

    strip.innerHTML = users.map(u => `
      <div class="mini-member">
        <div class="mini-dot"></div>
        <span class="mini-name">${u.name}${u.duration ? ' · ' + u.duration : ''}</span>
      </div>`).join('');
  } catch {
    /* silent — network blip */
  }
}

/* ── initCheckin: keyboard shortcuts, called once at boot ── */

function initCheckin() {
  document.addEventListener('keydown', e => {
    if (!document.getElementById('screen-kiosk').classList.contains('active')) return;

    const btn = document.getElementById('btn-scan');
    if (e.key === 'Enter' && !btn.disabled) scanFace();
    if (e.key === 'Escape')                 setState('idle');
  });
}
