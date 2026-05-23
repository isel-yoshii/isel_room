(function () {
  function currentAcademicYear(d = new Date()) {
    return d.getMonth() >= 3 ? d.getFullYear() : d.getFullYear() - 1;  // 0=Jan, 3=Apr
  }

  let _pointsYear   = new Date().getFullYear();
  let _pointsMonth  = new Date().getMonth() + 1;
  let _pointsAyYear = currentAcademicYear();

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

  function updatePointsYearLabel() {
    document.getElementById('points-year-label').textContent = `${_pointsAyYear}年度`;
    const nextBtn = document.getElementById('points-year-next');
    if (nextBtn) nextBtn.disabled = _pointsAyYear >= currentAcademicYear();
  }

  window.changePointsMonth = function changePointsMonth(delta) {
    _pointsMonth += delta;
    if (_pointsMonth > 12) { _pointsMonth = 1;  _pointsYear++; }
    if (_pointsMonth < 1)  { _pointsMonth = 12; _pointsYear--; }
    loadAttendance();
  };

  window.changePointsYear = function changePointsYear(delta) {
    _pointsAyYear += delta;
    loadAttendance();
  };

  window.loadAttendance = async function loadAttendance() {
    if (typeof loadGrid === 'function') loadGrid();
    updatePointsMonthLabel();
    updatePointsYearLabel();

    const monthEl = document.getElementById('points-content');
    const yearEl  = document.getElementById('points-year-content');
    monthEl.innerHTML = '<div class="log-empty">Loading…</div>';
    yearEl.innerHTML  = '<div class="log-empty">Loading…</div>';

    try {
      const [monthly, yearly] = await Promise.all([
        api.get(`/api/stats/points?year=${_pointsYear}&month=${_pointsMonth}`),
        api.get(`/api/stats/points/year?year=${_pointsAyYear}`),
      ]);
      renderMonthly(monthly);
      renderYearly(yearly);
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

  function renderMonthly(monthly) {
    document.getElementById('points-content').innerHTML =
      renderAttendanceTable(monthly, 'No Activity Recorded This Month');
  }

  function renderYearly(yearly) {
    document.getElementById('ay-section-label').textContent = `${yearly.year}年度 Leaderboard`;
    document.getElementById('points-year-content').innerHTML =
      renderAttendanceTable(yearly.leaderboard, `No Activity Recorded For ${yearly.year}年度`);
  }

  window.Dashboard = window.Dashboard || {};
  window.Dashboard.Attendance = {
    init:    () => loadAttendance(),
    destroy: () => {},
  };
})();
