(function () {
  let _dashInterval = null;

  window.switchScreen = function switchScreen(name) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById('screen-' + name).classList.add('active');

    document.querySelectorAll('.sw-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('sw-' + name).classList.add('active');

    if (name === 'check-in') {
      clearInterval(_dashInterval);
      startCamera('checkin-video');
      loadMemberStrip();
    } else {
      stopCamera();
      loadDashboard();
      _dashInterval = setInterval(loadDashboard, 30_000);
    }
  };

  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return;
    const anyModalOpen = ['reg-modal', 'picker-modal', 'pin-modal', 'profile-modal']
      .some(id => !document.getElementById(id)?.classList.contains('hidden'));
    if (anyModalOpen) return;

    if (e.key === 'c' || e.key === 'C') switchScreen('check-in');
    if (e.key === 'd' || e.key === 'D') switchScreen('dashboard');
  });
})();
