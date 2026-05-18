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

let pendingCommit = null; // 保留中の処理を保持

async function scanFace() {
  // すでにスキャン中、または確定待ち(pending)の間は入力を受け付けない
  if (pendingCommit) return;

  setState('scanning');

  try {
    const image = captureFrame('checkin-video');
    const authData = await api.post('/api/auth', { image });

    if (authData.matched) {
      // 1. まず画面演出（IN/OUT）を先に出す（ここではまだDB更新しない）
      // 仮のeventTypeを判定するために、現在のUI上のステータス等を参照するか、
      // サーバーから「次どっちになるか」の予測を受け取る必要があります。
      // ここでは、仮にサーバーが authData.next_event を返してくれると想定するか、
      // 確定前でも一度 toggle API を叩かずに演出だけ行います。
      
      // 演出用のダミー表示 (例: 現在が在室なら次は退室と仮定)
      const isCurrentlyIn = checkUserIsPresent(authData.name); 
      const guestEventType = isCurrentlyIn ? 'OUT' : 'IN';
      
      setStateResult(authData.name, guestEventType);

      // 2. 確定処理を保留する（5秒待機）
      pendingCommit = {
        userId: authData.user_id,
        timer: setTimeout(() => {
          commitToggle(authData.user_id);
        }, 5000) // 5秒猶予
      };

    } else {
      setState('fail');
      setTimeout(() => setState('idle'), 3000);
    }
  } catch (e) {
    console.error(e);
    setState('idle');
  }
}

// 実際にDBを更新する関数
async function commitToggle(userId) {
  if (!pendingCommit) return;
  
  try {
    await api.post('/api/toggle', { user_id: userId });
    loadMemberStrip(); // 下のバーを更新
  } catch (e) {
    console.error("確定失敗:", e);
  } finally {
    pendingCommit = null;
    setState('idle'); // 次の認証へ
  }
}

// キャンセル処理（Escキーで呼ばれる）
function cancelToggle() {
  if (pendingCommit) {
    clearTimeout(pendingCommit.timer);
    pendingCommit = null;
    setState('idle');
    console.log("キャンセルされました。DBは更新されません。");
  }
}

// ヘルパー：現在のメンバーリストから在室中か判定
function checkUserIsPresent(name) {
  const strip = document.getElementById('member-strip');
  return strip.textContent.includes(name);
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
  /*
  document.addEventListener('keydown', e => {
    if (!document.getElementById('screen-kiosk').classList.contains('active')) return;

    const btn = document.getElementById('btn-scan');
    if (e.key === 'Enter' && !btn.disabled) scanFace();
    if (e.key === 'Escape')                 setState('idle');
  });
  */
}
