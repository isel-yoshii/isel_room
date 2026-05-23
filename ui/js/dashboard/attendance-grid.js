(function () {
  const WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  let _gridWeekStart = mondayOf(new Date());
  let _selectedUserIds = null;
  let _memberMs = null;
  let _gridFilterInitialized = false;

  function initGridFilter() {
    if (_gridFilterInitialized) return;
    _gridFilterInitialized = true;
    const container = document.getElementById('grid-member-filter');
    if (container && typeof mountCohortMultiselect === 'function') {
      _memberMs = mountCohortMultiselect(container, {
        onChange: (ids) => { _selectedUserIds = ids.length ? ids : null; loadGrid(); },
      });
    }
  }

  function mondayOf(d) {
    const x = new Date(d);
    x.setHours(0, 0, 0, 0);
    const dow = (x.getDay() + 6) % 7;  // Mon=0..Sun=6
    x.setDate(x.getDate() - dow);
    return x;
  }

  function isoDate(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }

  function isToday(isoDateStr) {
    return isoDate(new Date()) === isoDateStr;
  }

  function formatWeekLabel(start) {
    const end = new Date(start);
    end.setDate(end.getDate() + 6);
    const fmt = { month: 'short', day: 'numeric' };
    const startStr = start.toLocaleDateString('en-US', fmt);
    const endStr   = end.toLocaleDateString('en-US', fmt);
    return `${startStr} – ${endStr}, ${start.getFullYear()}`;
  }

  window.changeGridWeek = function changeGridWeek(delta) {
    _gridWeekStart.setDate(_gridWeekStart.getDate() + delta * 7);
    loadGrid();
  };

  window.goCurrentWeek = function goCurrentWeek() {
    _gridWeekStart = mondayOf(new Date());
    loadGrid();
  };

  window.setGridMemberFilter = function setGridMemberFilter(ids) {
    _selectedUserIds = (ids && ids.length) ? ids : null;
    loadGrid();
  };

  window.loadGrid = async function loadGrid() {
    initGridFilter();
    document.getElementById('grid-week-label').textContent = formatWeekLabel(_gridWeekStart);
    const nextBtn = document.getElementById('grid-nav-next');
    const today = mondayOf(new Date());
    if (nextBtn) nextBtn.disabled = _gridWeekStart >= today;

    const content = document.getElementById('grid-content');
    content.innerHTML = '<div class="log-empty">Loading…</div>';
    try {
      const params = new URLSearchParams({ start: isoDate(_gridWeekStart) });
      if (_selectedUserIds) params.set('user_ids', _selectedUserIds.join(','));
      const data = await api.get('/api/stats/weekly-grid?' + params.toString());
      renderGrid(data);
    } catch (err) {
      console.error('loadGrid error:', err);
      content.innerHTML = '<div class="log-empty">Failed to load grid</div>';
    }
  };

  function renderGrid(rows) {
    const content = document.getElementById('grid-content');
    if (!rows.length) {
      content.innerHTML = '<div class="log-empty">No members match the current filter</div>';
      return;
    }

    const headerCells = [`<div class="grid-corner"></div>`];
    for (let i = 0; i < 7; i++) {
      const d = new Date(_gridWeekStart);
      d.setDate(d.getDate() + i);
      const iso = isoDate(d);
      const todayCls = isToday(iso) ? ' grid-header-today' : '';
      headerCells.push(`
        <div class="grid-header-cell${todayCls}">
          <div class="grid-header-day">${WEEKDAY_LABELS[i]}</div>
          <div class="grid-header-date">${d.getDate()}</div>
        </div>`);
    }

    const bodyCells = rows.map((u, i) => {
      const grad = isGraduated(u.type);
      const nameCell = `
        <div class="grid-name-cell ${grad ? 'grid-name-grad' : ''}" id="grid-row-${u.id}">
          <div class="avatar ${avColor(i)}" style="width:28px;height:28px;font-size:10px;">${esc(initials(u.name))}</div>
          <div class="grid-name-info">
            <div class="grid-name">${esc(u.name)}</div>
          </div>
        </div>`;
      const dayCells = u.days.map(d => {
        const todayCls   = isToday(d.date) ? ' grid-cell-today' : '';
        const presentCls = d.total_minutes > 0 ? ' grid-cell-present' : '';
        const tip = d.total_minutes > 0
          ? `${d.date}: ${d.sessions} session${d.sessions === 1 ? '' : 's'}`
          : `${d.date}: no sessions`;
        return `<div class="grid-cell${todayCls}${presentCls}" title="${tip}"></div>`;
      }).join('');
      return nameCell + dayCells;
    }).join('');

    content.innerHTML = `<div class="grid-table">${headerCells.join('')}${bodyCells}</div>`;
  }
})();
