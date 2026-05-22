(function () {
  let _statsYear  = new Date().getFullYear();
  let _statsMonth = new Date().getMonth() + 1;

  window.fmtMins = function fmtMins(mins) {
    const h = Math.floor(mins / 60), m = mins % 60;
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
  };

  window.updateStatsMonthLabel = function updateStatsMonthLabel() {
    const label = new Date(_statsYear, _statsMonth - 1, 1)
      .toLocaleDateString('en-US', { year: 'numeric', month: 'long' });
    document.getElementById('stats-month-label').textContent = label;

    const now     = new Date();
    const nextBtn = document.getElementById('stats-nav-next');
    if (nextBtn) {
      nextBtn.disabled =
        _statsYear > now.getFullYear() ||
        (_statsYear === now.getFullYear() && _statsMonth >= now.getMonth() + 1);
    }
  };

  window.changeStatsMonth = function changeStatsMonth(delta) {
    _statsMonth += delta;
    if (_statsMonth > 12) { _statsMonth = 1;  _statsYear++; }
    if (_statsMonth < 1)  { _statsMonth = 12; _statsYear--; }
    loadStats();
  };

  window.loadStats = async function loadStats() {
    updateStatsMonthLabel();
    const content = document.getElementById('stats-content');
    content.innerHTML = '<div class="log-empty">Loading…</div>';
    try {
      const data = await api.get(`/api/stats/monthly?year=${_statsYear}&month=${_statsMonth}`);
      renderStats(data);
    } catch (err) {
      console.error('loadStats error:', err);
    }
  };

  function renderStats(data) {
    const content = document.getElementById('stats-content');
    if (!data.length) {
      content.innerHTML = '<div class="log-empty">No Activity Recorded This Month</div>';
      return;
    }

    content.innerHTML = `
      <div class="stats-table">
        <div class="stats-header">
          <div>Member</div>
          <div>Sessions</div>
          <div>Total Time</div>
          <div>Avg / Session</div>
        </div>
        ${data.map((u, i) => `
          <div class="stats-row">
            <div class="stats-user">
              <div class="avatar ${avColor(i)}" style="width:30px;height:30px;font-size:10px;">${initials(u.name)}</div>
              <div>
                <div class="stats-name">${u.name}</div>
                <div class="stats-type">${u.type}</div>
              </div>
            </div>
            <div class="stats-value">${u.sessions}</div>
            <div class="stats-value highlight">${fmtMins(u.total_minutes)}</div>
            <div class="stats-value">${u.sessions ? fmtMins(Math.round(u.total_minutes / u.sessions)) : '–'}</div>
          </div>`).join('')}
      </div>`;
  }

  window.Dashboard = window.Dashboard || {};
  window.Dashboard.Statistics = {
    init:    () => loadStats(),
    destroy: () => {},
  };
})();
