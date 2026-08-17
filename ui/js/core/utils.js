(function () {
  // Every member name reaches innerHTML. Without this, a member named
  // `<img src=x onerror=...>` executes on render.
  const _escMap = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  window.esc = function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, ch => _escMap[ch]);
  };

  // For `<button onclick="fn('${escAttr(name)}')">`: JS-escape first (backslash,
  // quote) then HTML-escape, because both contexts nest here. Order matters.
  window.escAttr = function escAttr(s) {
    return String(s ?? '')
      .replace(/\\/g, '\\\\')
      .replace(/'/g, "\\'")
      .replace(/\r/g, '\\r')
      .replace(/\n/g, '\\n')
      .replace(/[&<>"]/g, ch => _escMap[ch]);
  };

  window.fmtMins = function fmtMins(mins) {
    const m = Math.max(0, Math.round(Number(mins) || 0));
    const h = Math.floor(m / 60);
    const rem = m % 60;
    return h > 0 ? `${h}h ${rem}m` : `${rem}m`;
  };

  const _jsonReq = (method, body) => ({
    method,
    headers: { 'Content-Type': 'application/json' },
    body:    body === undefined ? undefined : JSON.stringify(body),
  });
  window.api = {
    get:    url         => fetch(url).then(r => r.json()),
    post:   (url, body) => fetch(url, _jsonReq('POST',   body)).then(r => r.json()),
    put:    (url, body) => fetch(url, _jsonReq('PUT',    body)).then(r => r.json()),
    delete: url         => fetch(url, _jsonReq('DELETE')).then(r => r.json()),
  };

  function tick() {
    const now  = new Date();
    const date = now.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
    const time = now.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const el = document.getElementById('clock');
    if (el) el.textContent = `${date} · ${time}`;
  }
  setInterval(tick, 1000);
  tick();

  // `el` may be a DOM node or an id string; empty list renders `empty`.
  window.renderList = (el, items, template, empty = '') => {
    const node = typeof el === 'string' ? document.getElementById(el) : el;
    if (!node) return;
    node.innerHTML = items.length ? items.map(template).join('') : empty;
  };

  window.openModal  = id => document.getElementById(id)?.classList.remove('hidden');
  window.closeModal = id => document.getElementById(id)?.classList.add('hidden');

  // Backdrop click closes; a click bubbling up from the content does not.
  window.closeModalOnBg = (event, close) => {
    if (event.target === event.currentTarget) close();
  };

  // Add new modals here or the global keyboard handlers will fire behind them.
  const _MODAL_IDS = [
    'reg-modal', 'picker-modal', 'pin-modal', 'profile-modal',
    'face-rereg-modal', 'context-modal', 'promote-modal',
  ];
  window.anyModalOpen = () => _MODAL_IDS.some(id => {
    const el = document.getElementById(id);
    return el && !el.classList.contains('hidden');
  });

  const AV_COLORS = ['av-teal', 'av-blue', 'av-amber', 'av-pink', 'av-purple'];

  const isTeacher = t => t === '先生';
  window.isGraduated = t => t === '卒業';

  window.roleBadgeClass = function roleBadgeClass(type) {
    if (isTeacher(type))   return 'badge-admin';
    if (isGraduated(type)) return 'badge-grad';
    return 'badge-student';
  };

  window.formatLastSeen = function formatLastSeen(iso) {
    if (!iso) return '';
    const diff  = Date.now() - new Date(iso).getTime();
    const mins  = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days  = Math.floor(diff / 86400000);
    if (mins  < 60)  return `${mins}m ago`;
    if (hours < 24)  return `${hours}h ago`;
    if (days  === 1) return 'yesterday';
    return `${days} days ago`;
  };

  window.avColor  = i => AV_COLORS[i % AV_COLORS.length];
  window.initials = name => name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);

  // `cls` carries the base class plus any size modifier (.avatar-sm/-md/-lg).
  window.avatarHtml = (name, i, cls = 'avatar') =>
    `<div class="${cls} ${avColor(i)}">${esc(initials(name))}</div>`;

  window.mondayOf = function mondayOf(d) {
    const x = new Date(d);
    x.setHours(0, 0, 0, 0);              // zero first, then step back — the
    const dow = (x.getDay() + 6) % 7;    // reverse order shifts by an hour
    x.setDate(x.getDate() - dow);        // across a DST boundary
    return x;
  };

  // Local-time YYYY-MM-DD. Deliberately not toISOString(), which converts to
  // UTC and returns the previous day for any JST time before 09:00.
  window.isoDate = function isoDate(d) {
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  };

  window.byPresenceThenName = (a, b) =>
    (b.status ? 1 : 0) - (a.status ? 1 : 0) || a.name.localeCompare(b.name);
})();
