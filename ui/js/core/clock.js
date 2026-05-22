(function () {
  function tick() {
    const now  = new Date();
    const date = now.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
    const time = now.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    document.getElementById('clock').textContent = `${date} · ${time}`;
  }
  setInterval(tick, 1000);
  tick();
})();
