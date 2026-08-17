(function () {
  // HTML-escape user-supplied strings before inserting into innerHTML templates.
  // Without this, a member named `<img src=x onerror=...>` executes on render.
  const _escMap = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  window.esc = function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, ch => _escMap[ch]);
  };

  // For values inlined as a single-quoted JS string inside an HTML attribute:
  //   <button onclick="fn('${escAttr(name)}')">
  // First JS-escape (so backslash and single-quote don't terminate the JS
  // string), then HTML-escape (so double-quote and < don't break out of the
  // attribute or HTML context).
  window.escAttr = function escAttr(s) {
    return String(s ?? '')
      .replace(/\\/g, '\\\\')
      .replace(/'/g, "\\'")
      .replace(/\r/g, '\\r')
      .replace(/\n/g, '\\n')
      .replace(/[&<>"]/g, ch => _escMap[ch]);
  };

  // Format an integer number of minutes as "Xh Ym" (or just "Ym" when < 60).
  window.fmtMins = function fmtMins(mins) {
    const m = Math.max(0, Math.round(Number(mins) || 0));
    const h = Math.floor(m / 60);
    const rem = m % 60;
    return h > 0 ? `${h}h ${rem}m` : `${rem}m`;
  };

  // Tiny JSON fetch wrapper. All four verbs are JSON in / JSON out.
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

  // Topbar clock — date + time, refreshed every second.
  function tick() {
    const now  = new Date();
    const date = now.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
    const time = now.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const el = document.getElementById('clock');
    if (el) el.textContent = `${date} · ${time}`;
  }
  setInterval(tick, 1000);
  tick();

  // ── List rendering helper ──
  // Renders `items` into `el` via `template(item, i)`, joining with no separator.
  // Empty list → `empty` HTML (default: clear the element). `el` may be a DOM
  // node or an id string. Collapses the
  //   if (!arr.length) { el.innerHTML = empty; return; }
  //   el.innerHTML = arr.map(...).join('');
  // pattern that was repeated 8x across the dashboard and check-in screens.
  window.renderList = (el, items, template, empty = '') => {
    const node = typeof el === 'string' ? document.getElementById(el) : el;
    if (!node) return;
    node.innerHTML = items.length ? items.map(template).join('') : empty;
  };

  // ── Modal helpers ──
  // Open / close = add/remove the `hidden` class. Stream cleanup stays at the
  // call site because each modal owns its own camera stream variable.
  window.openModal  = id => document.getElementById(id)?.classList.remove('hidden');
  window.closeModal = id => document.getElementById(id)?.classList.add('hidden');

  // Centralised list of modal ids so the "any modal open?" guard used by global
  // keyboard handlers can't fall out of sync between files.
  const _MODAL_IDS = [
    'reg-modal', 'picker-modal', 'pin-modal', 'profile-modal',
    'face-rereg-modal', 'context-modal', 'promote-modal',
  ];
  window.anyModalOpen = () => _MODAL_IDS.some(id => {
    const el = document.getElementById(id);
    return el && !el.classList.contains('hidden');
  });

  // ── Shared member-display helpers ──
  // Lived in dashboard/overview.js historically, but every dashboard tab
  // (members, activity, attendance, attendance-grid) needs them. Moving
  // here removes a fragile load-order dependency.
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

  // One avatar circle. `cls` carries the base class plus any size modifier
  // (see .avatar-sm/-md/-lg in dashboard.css) so sizing lives in CSS rather
  // than as an inline style repeated at every call site. Always escapes —
  // two of the five call sites this replaces did not.
  window.avatarHtml = (name, i, cls = 'avatar') =>
    `<div class="${cls} ${avColor(i)}">${esc(initials(name))}</div>`;

  // ── Date helpers ──
  // Both were duplicated in dashboard/attendance-grid.js and dashboard/activity.js,
  // the latter under the name isoDay.
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

  // Present members first, then alphabetical. Used by both check-in screens.
  window.byPresenceThenName = (a, b) =>
    (b.status ? 1 : 0) - (a.status ? 1 : 0) || a.name.localeCompare(b.name);
})();
