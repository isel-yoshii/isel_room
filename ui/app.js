/*
 * app.js — Shared utilities loaded first.
 * Provides: camera helpers, fetch API wrappers, clock, screen switching.
 * checkin.js and dashboard.js depend on these globals.
 */

/* ── Camera ─────────────────────────────────────────── */

let activeStream = null;

async function startCamera(videoId) {
  stopCamera();
  try {
    activeStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    document.getElementById(videoId).srcObject = activeStream;
  } catch {
    console.warn('Camera access denied or unavailable.');
    if (typeof showCameraError === 'function') showCameraError();
  }
}

function stopCamera() {
  if (activeStream) {
    activeStream.getTracks().forEach(t => t.stop());
    activeStream = null;
  }
}

/** Grabs a JPEG frame from a <video> element as a base64 data-URL. */
function captureFrame(videoId) {
  const video  = document.getElementById(videoId);
  const canvas = document.getElementById('capture-canvas');
  canvas.width  = video.videoWidth  || 640;
  canvas.height = video.videoHeight || 480;
  canvas.getContext('2d').drawImage(video, 0, 0);
  return canvas.toDataURL('image/jpeg', 0.85);
}

/* ── API fetch helpers ───────────────────────────────── */

const api = {
  get:  url          => fetch(url).then(r => r.json()),
  post: (url, body)  => fetch(url, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(body),
  }).then(r => r.json()),
};

/* ── Clock ───────────────────────────────────────────── */

function tick() {
  document.getElementById('clock').textContent =
    new Date().toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}
setInterval(tick, 1000);
tick();

/* ── Screen switching (Kiosk ↔ Dashboard) ───────────── */

let _dashInterval = null;

function switchScreen(name) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById('screen-' + name).classList.add('active');

  document.querySelectorAll('.sw-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('sw-' + name).classList.add('active');

  if (name === 'kiosk') {
    clearInterval(_dashInterval);
    startCamera('checkin-video');
    loadMemberStrip();
  } else {
    stopCamera();
    loadDashboard();
    _dashInterval = setInterval(loadDashboard, 30_000);
  }
}

/* ── Global nav keyboard shortcuts (K / D) ───────────── */

document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return;
  const anyModalOpen = ['reg-modal', 'picker-modal', 'pin-modal', 'profile-modal']
    .some(id => !document.getElementById(id)?.classList.contains('hidden'));
  if (anyModalOpen) return;

  if (e.key === 'k' || e.key === 'K') switchScreen('kiosk');
  if (e.key === 'd' || e.key === 'D') switchScreen('dashboard');
});
