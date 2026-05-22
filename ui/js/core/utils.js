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
})();
