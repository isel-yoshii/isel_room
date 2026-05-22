(function () {
  let _pointsYear  = new Date().getFullYear();
  let _pointsMonth = new Date().getMonth() + 1;

  const _cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const RANK_COLORS = [_cssVar('--color-rank-gold'), _cssVar('--color-rank-silver'), _cssVar('--color-rank-bronze')];

  window.updatePointsMonthLabel = function updatePointsMonthLabel() {
    const label = new Date(_pointsYear, _pointsMonth - 1, 1)
      .toLocaleDateString('en-US', { year: 'numeric', month: 'long' });
    document.getElementById('points-month-label').textContent = label;

    const now     = new Date();
    const nextBtn = document.getElementById('points-nav-next');
    if (nextBtn) {
      nextBtn.disabled =
        _pointsYear > now.getFullYear() ||
        (_pointsYear === now.getFullYear() && _pointsMonth >= now.getMonth() + 1);
    }
  };

  window.changePointsMonth = function changePointsMonth(delta) {
    _pointsMonth += delta;
    if (_pointsMonth > 12) { _pointsMonth = 1;  _pointsYear++; }
    if (_pointsMonth < 1)  { _pointsMonth = 12; _pointsYear--; }
    loadAttendance();
  };

  window.loadAttendance = async function loadAttendance() {
    updatePointsMonthLabel();
    const content = document.getElementById('points-content');
    content.innerHTML = '<div class="log-empty">Loading…</div>';
    try {
      const [monthly, total] = await Promise.all([
        api.get(`/api/stats/points?year=${_pointsYear}&month=${_pointsMonth}`),
        api.get('/api/stats/points/total'),
      ]);
      renderAttendance(monthly, total);
    } catch (err) {
      console.error('loadAttendance error:', err);
    }
  };

  function renderAttendanceTable(data, emptyMsg) {
    if (!data.length) return `<div class="log-empty">${emptyMsg}</div>`;
    return `
      <div class="points-table">
        <div class="points-header">
          <div>Rank</div>
          <div>Member</div>
          <div>Days Present</div>
        </div>
        ${data.map((u, i) => {
          const rankColor = RANK_COLORS[i] ?? 'var(--color-text-secondary)';
          const rankLabel = i < 3 ? ['1st', '2nd', '3rd'][i] : `${i + 1}th`;
          return `
          <div class="points-row ${i < 3 ? 'points-top' : ''}">
            <div class="points-rank" style="color:${rankColor}">${rankLabel}</div>
            <div class="stats-user">
              <div class="avatar ${avColor(i)}" style="width:30px;height:30px;font-size:10px;">${initials(u.name)}</div>
              <div>
                <div class="stats-name">${u.name}</div>
                <div class="stats-type">${u.type}</div>
              </div>
            </div>
            <div class="points-value">${u.points} <span class="points-unit">day${u.points !== 1 ? 's' : ''}</span></div>
          </div>`;
        }).join('')}
      </div>`;
  }

  function renderAttendance(monthly, total) {
    const content = document.getElementById('points-content');
    content.innerHTML = `
      <div class="section-label" style="margin-bottom:8px">This Month</div>
      ${renderAttendanceTable(monthly, 'No Activity Recorded This Month')}
      <div class="section-label" style="margin-top:24px;margin-bottom:8px">All-Time</div>
      ${renderAttendanceTable(total, 'No Activity Recorded Yet')}`;
  }

  window.Dashboard = window.Dashboard || {};
  window.Dashboard.Attendance = {
    init:    () => loadAttendance(),
    destroy: () => {},
  };
})();
