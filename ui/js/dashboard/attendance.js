(function () {
  function currentAcademicYear(d = new Date()) {
    return d.getMonth() >= 3 ? d.getFullYear() : d.getFullYear() - 1;  // 0=Jan, 3=Apr
  }

  let _pointsYear   = new Date().getFullYear();
  let _pointsMonth  = new Date().getMonth() + 1;
  let _pointsAyYear = currentAcademicYear();
  let _dropdownsPopulated = false;

  const _MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];

  const _cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const RANK_COLORS = [_cssVar('--color-rank-gold'), _cssVar('--color-rank-silver'), _cssVar('--color-rank-bronze')];


  function _populateDropdownsOnce() {
    if (_dropdownsPopulated) return;
    _dropdownsPopulated = true;

    const nowYear = new Date().getFullYear();
    const ay      = currentAcademicYear();

    const yearSel = document.getElementById('points-year-select');
    if (yearSel) {
      yearSel.innerHTML = '';
      for (let y = nowYear - 3; y <= nowYear; y++) {
        const opt = document.createElement('option');
        opt.value = String(y);
        opt.textContent = String(y);
        yearSel.appendChild(opt);
      }
    }

    const monthSel = document.getElementById('points-month-select');
    if (monthSel) {
      monthSel.innerHTML = '';
      _MONTH_NAMES.forEach((name, i) => {
        const opt = document.createElement('option');
        opt.value = String(i + 1);
        opt.textContent = name;
        monthSel.appendChild(opt);
      });
    }

    const aySel = document.getElementById('points-ay-select');
    if (aySel) {
      aySel.innerHTML = '';
      for (let y = ay - 3; y <= ay; y++) {
        const opt = document.createElement('option');
        opt.value = String(y);
        opt.textContent = `${y}年度`;
        aySel.appendChild(opt);
      }
    }
  }

  function _syncMonthlyDropdowns() {
    const yearSel  = document.getElementById('points-year-select');
    const monthSel = document.getElementById('points-month-select');
    if (yearSel)  yearSel.value  = String(_pointsYear);
    if (monthSel) monthSel.value = String(_pointsMonth);
  }

  function _syncYearlyDropdown() {
    const aySel = document.getElementById('points-ay-select');
    if (aySel) aySel.value = String(_pointsAyYear);
  }


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


  async function loadMonthly() {
    updatePointsMonthLabel();
    _syncMonthlyDropdowns();
    const el = document.getElementById('points-content');
    el.classList.add('is-loading');
    try {
      const data = await api.get(`/api/stats/points?year=${_pointsYear}&month=${_pointsMonth}`);
      el.innerHTML = renderAttendanceTable(data, 'No Activity Recorded This Month');
    } catch (err) {
      console.error('loadMonthly error:', err);
    } finally {
      el.classList.remove('is-loading');
    }
  }

  async function loadYearly() {
    updatePointsYearLabel();
    _syncYearlyDropdown();
    const el = document.getElementById('points-year-content');
    el.classList.add('is-loading');
    try {
      const data = await api.get(`/api/stats/points/year?year=${_pointsAyYear}`);
      document.getElementById('ay-section-label').textContent = `${data.year}年度 Leaderboard`;
      el.innerHTML = renderAttendanceTable(data.leaderboard, `No Activity Recorded For ${data.year}年度`);
    } catch (err) {
      console.error('loadYearly error:', err);
    } finally {
      el.classList.remove('is-loading');
    }
  }


  window.changePointsMonth = function changePointsMonth(delta) {
    _pointsMonth += delta;
    if (_pointsMonth > 12) { _pointsMonth = 1;  _pointsYear++; }
    if (_pointsMonth < 1)  { _pointsMonth = 12; _pointsYear--; }
    loadMonthly();
  };

  window.changePointsYear = function changePointsYear(delta) {
    _pointsAyYear += delta;
    loadYearly();
  };

  window.onPointsYearChange = function onPointsYearChange(value) {
    _pointsYear = parseInt(value, 10);
    loadMonthly();
  };

  window.onPointsMonthChange = function onPointsMonthChange(value) {
    _pointsMonth = parseInt(value, 10);
    loadMonthly();
  };

  window.onPointsAyChange = function onPointsAyChange(value) {
    _pointsAyYear = parseInt(value, 10);
    loadYearly();
  };


  window.loadAttendance = async function loadAttendance() {
    _populateDropdownsOnce();
    if (typeof loadGrid === 'function') loadGrid();
    await Promise.all([loadMonthly(), loadYearly()]);
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
              ${avatarHtml(u.name, i, 'avatar avatar-md')}
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
})();
