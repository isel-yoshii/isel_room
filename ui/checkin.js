/*
 * checkin.js — Kiosk / check-in screen logic.
 *
 * State machine:
 *   idle  →  scanning  →  confirmation  →  commit → success → idle
 *                      ↘  fail          →  (Space: manual picker) → commit → success → idle
 *
 * Depends on app.js (api, captureFrame).
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
          <div class="checkin-detail">press Space to check in manually</div>
        </div>
      </div>`,
    btnText: 'Try Again', btnDisabled: false,
  },
};

/* ── setState ─────────────────────────────────────────── */

let _currentState = 'idle';

function setState(key) {
  const s = CHECKIN_STATES[key];
  if (!s) return;
  _currentState = key;

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

/* ── setStateConfirmation: shown after a match, before commit ── */

function setStateConfirmation(name, predictedEvent) {
  _currentState = 'confirmation';
  const isIn = predictedEvent === 'IN';

  const tag = document.getElementById('state-tag');
  tag.className = 'state-tag tag-scanning';
  document.getElementById('state-dot').className = 'dot dot-amber';
  document.getElementById('tag-text').textContent = 'confirm?';

  document.getElementById('state-name').innerHTML = `Is this<br>${name}?`;
  document.getElementById('state-sub').textContent = `will ${isIn ? 'check in' : 'check out'}`;

  document.getElementById('result-card').innerHTML = `
    <div class="hint-row">
      <div class="hint"><span>Enter</span> · confirm</div>
      <div class="hint"><span>Space</span> · choose manually</div>
      <div class="hint"><span>Esc</span> · cancel</div>
    </div>`;

  document.getElementById('face-box').className = 'face-box state-scanning';
  document.getElementById('scan-line').style.display = 'none';

  const btn = document.getElementById('btn-scan');
  btn.textContent = 'Confirm (Enter)';
  btn.disabled    = false;
}

/* ── setStateResult: shown briefly after a successful commit ── */

function setStateResult(name, eventType) {
  _currentState = 'success';
  const isIn     = eventType === 'IN';
  const inits    = name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
  const time     = new Date().toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });

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
      <div class="checkin-avatar av-green">${inits}</div>
      <div class="checkin-info">
        <div class="checkin-name">${name}</div>
        <div class="checkin-detail">${isIn ? 'checked in' : 'checked out'}</div>
      </div>
      <div class="event-badge ${isIn ? 'badge-in' : 'badge-out'}">${isIn ? 'check-in' : 'check-out'}</div>
    </div>`;

  document.getElementById('face-box').className = 'face-box state-checkin';
  document.getElementById('scan-line').style.display = 'none';

  const btn = document.getElementById('btn-scan');
  btn.textContent = 'Scan Next';
  btn.disabled    = false;
}

/* ── Core scan / commit / cancel ─────────────────────── */

let pendingConfirm = null;

async function scanFace() {
  if (pendingConfirm) return;

  setState('scanning');

  try {
    const image    = captureFrame('checkin-video');
    const authData = await api.post('/api/auth', { image });

    if (authData.matched) {
      // authData.status = true means currently IN → next event is OUT
      const predictedEvent = authData.status ? 'OUT' : 'IN';
      setStateConfirmation(authData.name, predictedEvent);
      pendingConfirm = { userId: authData.user_id };
    } else {
      setState('fail');
      // auto-reset after 8 s if user does nothing
      setTimeout(() => { if (_currentState === 'fail') setState('idle'); }, 8000);
    }
  } catch (e) {
    console.error(e);
    setState('idle');
  }
}

async function commitToggle(userId) {
  pendingConfirm = null;
  try {
    const result = await api.post('/api/toggle', { user_id: userId });
    setStateResult(result.name, result.event_type);
    loadMemberStrip();
    setTimeout(() => setState('idle'), 3000);
  } catch (e) {
    console.error('commitToggle error:', e);
    setState('idle');
  }
}

function cancelToggle() {
  pendingConfirm = null;
  setState('idle');
}

/* ── onScanBtnClick: routes button click based on state ── */

function onScanBtnClick() {
  if (pendingConfirm) {
    commitToggle(pendingConfirm.userId);
  } else {
    scanFace();
  }
}

/* ── Manual picker ───────────────────────────────────── */

let _pickerUsers  = [];
let _pickerFiltered = [];
let _pickerIndex  = 0;

async function openManualPicker() {
  try {
    const users = await api.get('/api/users');
    // Present (IN) members first, then alphabetical
    _pickerUsers = [...users].sort((a, b) =>
      (b.status ? 1 : 0) - (a.status ? 1 : 0) || a.name.localeCompare(b.name)
    );
    _pickerIndex  = 0;
    _pickerFiltered = _pickerUsers;

    const search = document.getElementById('picker-search');
    search.value = '';
    renderPickerList(_pickerFiltered);
    document.getElementById('picker-modal').classList.remove('hidden');
    setTimeout(() => search.focus(), 50);

    search.oninput = () => {
      const q = search.value.toLowerCase();
      _pickerFiltered = _pickerUsers.filter(u => u.name.toLowerCase().includes(q));
      _pickerIndex = 0;
      renderPickerList(_pickerFiltered);
    };

    search.onkeydown = (e) => {
      const rows = document.querySelectorAll('#picker-list .picker-row');
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        _pickerIndex = Math.min(_pickerIndex + 1, rows.length - 1);
        updatePickerHighlight(rows);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        _pickerIndex = Math.max(_pickerIndex - 1, 0);
        updatePickerHighlight(rows);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const active = document.querySelector('#picker-list .picker-row.active');
        if (active) active.click();
      }
    };
  } catch (err) {
    console.error('openManualPicker error:', err);
  }
}

function renderPickerList(users) {
  const list = document.getElementById('picker-list');
  if (!users.length) {
    list.innerHTML = '<div class="picker-empty">no members found</div>';
    return;
  }
  list.innerHTML = users.map((u, i) => {
    const inits = u.name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
    return `
      <div class="picker-row ${i === _pickerIndex ? 'active' : ''}"
           onclick="selectPickerUser(${u.id})">
        <div class="picker-av">${inits}</div>
        <div class="picker-name">${u.name}</div>
        <div class="status-pill ${u.status ? 'pill-in' : 'pill-out'}">${u.status ? 'in lab' : 'out'}</div>
      </div>`;
  }).join('');
}

function updatePickerHighlight(rows) {
  rows.forEach((r, i) => r.classList.toggle('active', i === _pickerIndex));
  rows[_pickerIndex]?.scrollIntoView({ block: 'nearest' });
}

function closeManualPicker() {
  document.getElementById('picker-modal').classList.add('hidden');
  const search = document.getElementById('picker-search');
  search.oninput   = null;
  search.onkeydown = null;
}

async function selectPickerUser(userId) {
  closeManualPicker();
  pendingConfirm = null;
  await commitToggle(userId);
}

/* ── loadMemberStrip: bottom presence bar ───────────── */

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

/* ── initCheckin: called once at boot ───────────────── */

function initCheckin() {
  // keyboard shortcuts are wired in index.html boot script
}
