(function () {
  const PAGE_META = {
    overview:   { title: 'Overview',     subtitle: "Today's Lab Activity" },
    attendance: { title: 'Attendance',   subtitle: 'Weekly Grid And Points' },
    members:    { title: 'Members',      subtitle: 'Manage Lab Members And Access' },
    activity:   { title: 'Activity Log', subtitle: 'Inspect All Admin And Attendance Events' },
  };

  window.activateDashTab = function activateDashTab(name, btn) {
    document.querySelectorAll('.db-page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.sidebar-tab').forEach(t => t.classList.remove('active'));
    document.getElementById('db-' + name).classList.add('active');
    btn.classList.add('active');

    const meta = PAGE_META[name];
    if (meta) {
      const titleEl    = document.getElementById('page-title');
      const subtitleEl = document.getElementById('page-subtitle');
      if (titleEl)    titleEl.textContent    = meta.title;
      if (subtitleEl) subtitleEl.textContent = meta.subtitle;
    }
  };

  window.checkAdminAndProceed = async function checkAdminAndProceed(callback) {
    try {
      const status = await api.get('/api/admin/status');
      if (status.authenticated) {
        callback();
      } else {
        openPinModal(callback);
      }
    } catch {
      openPinModal(callback);
    }
  };

  window.switchDashTab = function switchDashTab(name, btn) {
    if (name === 'members' || name === 'activity') {
      checkAdminAndProceed(() => {
        activateDashTab(name, btn);
        if (name === 'activity' && typeof loadActivity === 'function') loadActivity();
      });
      return;
    }
    activateDashTab(name, btn);
    if (name === 'attendance') loadAttendance();
  };

  // Scanning stops silently — nobody gets checked in, nothing errors — so the
  // header says when it last worked. Stale counts as failing: a scheduler that
  // died reports no error at all.
  window.scanStatusView = function scanStatusView(st, nowMs = Date.now()) {
    if (!st || !st.enabled) return { text: '', cls: '', title: '' };
    const last  = st.last_success ? formatLastSeen(st.last_success) : 'Never';
    const stale = !st.last_success
      || nowMs - new Date(st.last_success).getTime() > 3 * st.interval * 1000;
    if (st.error || (stale && st.last_attempt)) {
      return {
        text: `Wi-Fi Scan Failing · Last OK ${last}`,
        cls: 'scan-bad',
        title: st.error || 'No successful scan recently',
      };
    }
    if (stale) return { text: 'Wi-Fi Scan Starting…', cls: '', title: '' };
    return { text: `Wi-Fi Scan OK · ${last}`, cls: 'scan-ok', title: `${st.devices} device(s) on the network` };
  };

  window.loadScanStatus = async function loadScanStatus() {
    const el = document.getElementById('scan-status');
    if (!el) return;
    try {
      const view = scanStatusView(await api.get('/api/presence/status'));
      el.textContent = view.text;
      el.className   = 'scan-status ' + view.cls;
      el.title       = view.title;
    } catch {
      /* silent — network blip */
    }
  };

  window.loadDashboard = async function loadDashboard() {
    await Promise.all([loadOverview(), loadLogSection(), loadMembers(), loadScanStatus()]);
  };

  document.addEventListener('keydown', (e) => {
    if (!document.getElementById('screen-dashboard').classList.contains('active')) return;
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return;
    const anyModalOpen = ['reg-modal', 'pin-modal', 'profile-modal', 'face-rereg-modal', 'context-modal', 'promote-modal']
      .some(id => !document.getElementById(id)?.classList.contains('hidden'));
    if (anyModalOpen) return;

    const tabMap = {
      '1': { name: 'overview',   btnId: 'sbt-overview'   },
      '2': { name: 'attendance', btnId: 'sbt-attendance' },
      '3': { name: 'members',    btnId: 'sbt-members'    },
      '4': { name: 'activity',   btnId: 'sbt-activity'   },
    };
    const target = tabMap[e.key];
    if (!target) return;
    const btn = document.getElementById(target.btnId);
    if (btn) switchDashTab(target.name, btn);
  });
})();
