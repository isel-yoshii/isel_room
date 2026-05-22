(function () {
  const STUDENT_TYPES  = new Set(['B4', 'M1', 'M2', 'Intern']);
  const AV_COLORS      = ['av-teal', 'av-blue', 'av-amber', 'av-pink', 'av-purple'];

  window.isTeacher   = t => t === '先生';
  window.isStudent   = t => STUDENT_TYPES.has(t);
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

  let _lineChart = null;
  let _barChart  = null;

  window.loadCharts = async function loadCharts() {
    if (typeof Chart === 'undefined') return;
    try {
      const [weekly, monthly] = await Promise.all([
        api.get('/api/stats/weekly'),
        api.get(`/api/stats/monthly?year=${new Date().getFullYear()}&month=${new Date().getMonth() + 1}`),
      ]);
      renderLineChart(weekly);
      renderBarChart(monthly.slice(0, 8));
    } catch (err) {
      console.error('loadCharts error:', err);
    }
  };

  function renderLineChart(data) {
    const canvas = document.getElementById('chart-line');
    if (!canvas) return;
    if (_lineChart) { _lineChart.destroy(); _lineChart = null; }
    _lineChart = new Chart(canvas, {
      type: 'line',
      data: {
        labels: data.map(d => d.date),
        datasets: [{
          data: data.map(d => d.count),
          borderColor: '#C83B3B',
          backgroundColor: 'rgba(200, 59, 59, 0.07)',
          fill: true, tension: 0.4,
          pointBackgroundColor: '#C83B3B',
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
          x: { grid: { display: false }, ticks: { font: { size: 10, family: 'DM Mono' }, color: '#A09090' } },
          y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.04)' }, ticks: { stepSize: 1, font: { size: 10, family: 'DM Mono' }, color: '#A09090' } }
        }
      }
    });
  }

  function renderBarChart(data) {
    const canvas = document.getElementById('chart-bar');
    if (!canvas) return;
    if (_barChart) { _barChart.destroy(); _barChart = null; }
    if (!data.length) return;

    const maxMinutes = Math.max(...data.map(d => d.total_minutes));
    _barChart = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: data.map(d => d.name.split(' ')[0]),
        datasets: [{
          data: data.map(d => +(d.total_minutes / 60).toFixed(1)),
          backgroundColor: data.map(d =>
            d.total_minutes === maxMinutes ? '#C83B3B' : '#FDECEA'
          ),
          borderRadius: 6, borderSkipped: false,
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#fff', titleColor: '#1A1A1A', bodyColor: '#A09090',
            borderColor: '#F2E5E4', borderWidth: 1,
            callbacks: { label: ctx => `${ctx.raw}h This Month` }
          }
        },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 10, family: 'DM Mono' }, color: '#A09090' } },
          y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.04)' }, ticks: { font: { size: 10, family: 'DM Mono' }, color: '#A09090' } }
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

      document.getElementById('stat-in').textContent    = present.length;
      document.getElementById('stat-today').textContent = todayStats.unique_checkins;
      document.getElementById('stat-total').textContent = users.length;

      const presentNames = new Set(present.map(u => u.name));
      const durationMap  = Object.fromEntries(present.map(u => [u.name, u.duration]));

      const grid = document.getElementById('member-grid');
      if (!users.length) {
        grid.innerHTML = '<div class="grid-empty">No Members Registered Yet</div>';
      } else {
        const sorted = [...users].sort((a, b) =>
          (presentNames.has(b.name) ? 1 : 0) - (presentNames.has(a.name) ? 1 : 0)
        );
        grid.innerHTML = sorted.map((u, i) => {
          const here      = presentNames.has(u.name);
          const dur       = durationMap[u.name] ?? '–';
          const timeLabel = here ? dur : (formatLastSeen(u.last_seen) || '–');
          return `
            <div class="member-card ${here ? 'present' : 'absent'}" onclick="openProfileModal(${u.id})" style="cursor:pointer">
              <div class="avatar ${avColor(i)}">${initials(u.name)}</div>
              <div class="member-name">${u.name}</div>
              <div class="member-time">${timeLabel}</div>
              <div class="status-pill ${here ? 'pill-in' : 'pill-out'}">${here ? 'In Lab' : 'Out'}</div>
            </div>`;
        }).join('');
      }

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
    const logBody = document.getElementById('log-body');
    if (!log.length) {
      logBody.innerHTML = '<div class="log-empty">No Activity Recorded</div>';
      return;
    }
    logBody.innerHTML = log.map(l => `
      <div class="log-row">
        <div class="log-icon ${l.event_type === 'IN' ? 'log-in' : 'log-out'}">
          ${l.event_type === 'IN' ? '↑' : '↓'}
        </div>
        <div class="log-name">${l.name}</div>
        <div class="log-ts">${l.timestamp}</div>
        <div class="status-pill ${l.event_type === 'IN' ? 'pill-in' : 'pill-out'}">
          ${l.event_type === 'IN' ? 'Check-In' : 'Check-Out'}
        </div>
      </div>`).join('');
  }

  window.Dashboard = window.Dashboard || {};
  window.Dashboard.Overview = {
    init:    () => loadOverview(),
    destroy: () => {},
  };
})();
