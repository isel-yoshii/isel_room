(function () {
  let _lineChart = null;

  window.loadCharts = async function loadCharts() {
    if (typeof Chart === 'undefined') return;
    try {
      const weekly = await api.get('/api/stats/weekly');
      renderLineChart(weekly);
    } catch (err) {
      console.error('loadCharts error:', err);
    }
  };

  function renderLineChart(data) {
    const canvas = document.getElementById('chart-line');
    if (!canvas) return;
    if (_lineChart) { _lineChart.destroy(); _lineChart = null; }
    const lineColor = getComputedStyle(document.documentElement).getPropertyValue('--color-chart-line').trim() || '#2E8B70';
    _lineChart = new Chart(canvas, {
      type: 'line',
      data: {
        labels: data.map(d => d.date),
        datasets: [{
          data: data.map(d => d.count),
          borderColor: lineColor,
          backgroundColor: lineColor + '12',
          fill: true, tension: 0.4,
          pointBackgroundColor: lineColor,
          pointBorderColor: '#fff',
          pointBorderWidth: 2, pointRadius: 4, pointHoverRadius: 6,
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#fff', titleColor: '#1A1A1A', bodyColor: '#A09090',
            borderColor: '#F2E5E4', borderWidth: 1,
            callbacks: { label: ctx => `${ctx.raw} Check-Ins` }
          }
        },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 10, family: 'IBM Plex Mono' }, color: '#A09090' } },
          y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.04)' }, ticks: { stepSize: 1, font: { size: 10, family: 'IBM Plex Mono' }, color: '#A09090' } }
        }
      }
    });
  }

window.loadOverview = async function loadOverview() {
    try {
      const [present, log, users, todayStats] = await Promise.all([
        api.get('/api/present-detailed'),
        api.get('/api/log/today'),
        api.get('/api/users'),
        api.get('/api/stats/today'),
      ]);

      document.getElementById('stat-in').textContent          = present.length;
      document.getElementById('stat-today').textContent        = todayStats.unique_checkins;
      document.getElementById('stat-active-days').textContent  = todayStats.active_days_month;
      document.getElementById('stat-total').textContent        = users.length;

      const presentNames = new Set(present.map(u => u.name));
      const durationMap  = Object.fromEntries(present.map(u => [u.name, u.duration]));

      const sorted = [...users].sort((a, b) =>
        (presentNames.has(b.name) ? 1 : 0) - (presentNames.has(a.name) ? 1 : 0)
      );
      renderList('member-grid', sorted, (u, i) => {
        const here      = presentNames.has(u.name);
        const dur       = durationMap[u.name] ?? '–';
        const timeLabel = here ? dur : (formatLastSeen(u.last_seen) || '–');
        return `
          <div class="member-card ${here ? 'present' : 'absent'}" onclick="openProfileModal(${u.id})" style="cursor:pointer">
            ${avatarHtml(u.name, i)}
            <div class="member-name">${u.name}</div>
            <div class="member-time">${timeLabel}</div>
            <div class="status-pill ${here ? 'pill-in' : 'pill-out'}">${here ? 'In Lab' : 'Out'}</div>
          </div>`;
      }, '<div class="grid-empty">No Members Registered Yet</div>');

      loadCharts();
    } catch (err) {
      console.error('loadOverview error:', err);
    }
  };

  let _logDateOffset = 0;

  window.changeLogDate = function changeLogDate(delta) {
    _logDateOffset += delta;
    loadLogSection();
  };

  window.loadLogSection = async function loadLogSection() {
    const nextBtn = document.getElementById('log-nav-next');
    const labelEl = document.getElementById('log-date-label');
    if (nextBtn) nextBtn.disabled = _logDateOffset >= 0;

    let url;
    if (_logDateOffset === 0) {
      url = '/api/log/today';
      if (labelEl) labelEl.textContent = 'Today';
    } else {
      const d = new Date();
      d.setDate(d.getDate() + _logDateOffset);
      const dateStr = d.toISOString().split('T')[0];
      url = `/api/log?date=${dateStr}`;
      if (labelEl) {
        labelEl.textContent = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      }
    }

    try {
      const log = await api.get(url);
      renderLogRows(log);
    } catch (err) {
      console.error('loadLogSection error:', err);
    }
  };

  function renderLogRows(log) {
    renderList('log-body', log, l => `
      <div class="log-row">
        <div class="log-icon ${l.event_type === 'IN' ? 'log-in' : 'log-out'}">
          ${l.event_type === 'IN' ? '↑' : '↓'}
        </div>
        <div class="log-name">${l.name}</div>
        <div class="log-ts">${l.timestamp}</div>
        <div class="status-pill ${l.event_type === 'IN' ? 'pill-in' : 'pill-out'}">
          ${l.event_type === 'IN' ? 'Check-In' : 'Check-Out'}
        </div>
      </div>`,
      '<div class="log-empty">No Activity Recorded</div>');
  }
})();
