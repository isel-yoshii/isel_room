(function () {
  const PAGE_META = {
    overview:   { title: 'Overview',    subtitle: "Today's Lab Activity" },
    attendance: { title: 'Attendance',  subtitle: 'Days Present Ranking' },
    admin:      { title: 'Admin',       subtitle: 'Manage Members And Access' },
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
    if (name === 'admin') {
      checkAdminAndProceed(() => activateDashTab('admin', btn));
      return;
    }
    activateDashTab(name, btn);
    if (name === 'attendance') loadAttendance();
  };

  window.loadDashboard = async function loadDashboard() {
    await Promise.all([loadOverview(), loadLogSection(), loadAdmin()]);
  };

  document.addEventListener('keydown', (e) => {
    if (!document.getElementById('screen-dashboard').classList.contains('active')) return;
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return;
    const anyModalOpen = ['reg-modal', 'pin-modal', 'profile-modal']
      .some(id => !document.getElementById(id)?.classList.contains('hidden'));
    if (anyModalOpen) return;

    const tabMap = {
      '1': { name: 'overview',    btnId: 'sbt-overview'    },
      '2': { name: 'attendance',  btnId: 'sbt-attendance'  },
      '3': { name: 'admin',       btnId: 'sbt-admin'       },
    };
    const target = tabMap[e.key];
    if (!target) return;
    const btn = document.getElementById(target.btnId);
    if (btn) switchDashTab(target.name, btn);
  });
})();
