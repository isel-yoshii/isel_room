/* ── State ── */
let stream = null;
let pendingUserId = null;

/* ── Clock ── */
function tick() {
  document.getElementById('clock').textContent =
    new Date().toLocaleTimeString('ja-JP');
}
setInterval(tick, 1000);
tick();

/* ── View switching ── */
function showView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById('view-' + name).classList.add('active');

  if (name === 'auth')     startCamera('auth-video');
  if (name === 'register') startCamera('reg-video');
}

function backToMain() {
  stopCamera();
  resetAuth();
  resetRegister();
  showView('main');
  loadPresent();
}

function resetAuth() {
  pendingUserId = null;
  setResult('auth-result', 'カメラに顔を向けて「スキャン」を押してください', '');
  document.getElementById('btn-confirm').hidden = true;
  setBtn('btn-scan', '顔をスキャン', false);
}

function resetRegister() {
  document.getElementById('reg-name').value = '';
  setResult('reg-result', '名前を入力してカメラに顔を向けてください', '');
  setBtn('btn-register', '顔を撮影して登録', false);
}

/* ── Camera ── */
async function startCamera(videoId) {
  stopCamera();
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    document.getElementById(videoId).srcObject = stream;
  } catch {
    alert('カメラへのアクセスが拒否されました。ブラウザの設定を確認してください。');
  }
}

function stopCamera() {
  if (stream) {
    stream.getTracks().forEach(t => t.stop());
    stream = null;
  }
}

function captureFrame(videoId, canvasId) {
  const video  = document.getElementById(videoId);
  const canvas = document.getElementById(canvasId);
  canvas.width  = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);
  return canvas.toDataURL('image/jpeg', 0.85);
}

/* ── UI helpers ── */
function setResult(id, text, state) {
  const el = document.getElementById(id);
  el.textContent = text;
  el.className = 'result-box' + (state ? ' ' + state : '');
}

function setBtn(id, label, disabled) {
  const btn = document.getElementById(id);
  btn.textContent = label;
  btn.disabled = disabled;
}

/* ── Present users ── */
async function loadPresent() {
  try {
    const res   = await fetch('/api/present');
    const users = await res.json();
    const list  = document.getElementById('present-list');
    list.innerHTML = users.length
      ? users.map(n => `<li>${n}</li>`).join('')
      : '<li class="empty">在室者なし</li>';
  } catch {
    /* silent — network blip */
  }
}

/* ── Auth: single scan ── */
async function scanFace() {
  const imageData = captureFrame('auth-video', 'auth-canvas');

  setBtn('btn-scan', 'スキャン中…', true);
  setResult('auth-result', '処理中…', '');
  document.getElementById('btn-confirm').hidden = true;

  try {
    const res  = await fetch('/api/auth', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: imageData }),
    });
    const data = await res.json();

    if (data.matched) {
      pendingUserId = data.user_id;
      setResult('auth-result', `${data.name} さんを認識しました`, 'info');
      document.getElementById('btn-confirm').hidden = false;
    } else {
      pendingUserId = null;
      setResult('auth-result', data.message, 'error');
    }
  } catch {
    setResult('auth-result', 'サーバーエラーが発生しました', 'error');
  }

  setBtn('btn-scan', '再スキャン', false);
}

async function confirmToggle() {
  if (!pendingUserId) return;

  setBtn('btn-confirm', '処理中…', true);

  try {
    const res  = await fetch('/api/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: pendingUserId }),
    });
    const data = await res.json();
    const label = data.event_type === 'IN' ? '入室' : '退室';

    setResult('auth-result', `${data.name} さんが${label}しました`, 'success');
    document.getElementById('btn-confirm').hidden = true;
    pendingUserId = null;
    setBtn('btn-scan', '顔をスキャン', false);
  } catch {
    setResult('auth-result', 'サーバーエラーが発生しました', 'error');
    setBtn('btn-confirm', '入退室を確定する', false);
  }
}

/* ── Register: single capture ── */
async function captureAndRegister() {
  const name     = document.getElementById('reg-name').value.trim();
  const userType = document.getElementById('reg-type').value;

  if (!name) {
    setResult('reg-result', '名前を入力してください', 'error');
    return;
  }

  const imageData = captureFrame('reg-video', 'reg-canvas');

  setBtn('btn-register', '処理中…', true);
  setResult('reg-result', '処理中…', '');

  try {
    const res  = await fetch('/api/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, user_type: userType, image: imageData }),
    });
    const data = await res.json();

    setResult('reg-result', data.message, data.success ? 'success' : 'error');
    if (data.success) document.getElementById('reg-name').value = '';
  } catch {
    setResult('reg-result', 'サーバーエラーが発生しました', 'error');
  }

  setBtn('btn-register', '顔を撮影して登録', false);
}

/* ── Init ── */
loadPresent();
setInterval(loadPresent, 30_000);
