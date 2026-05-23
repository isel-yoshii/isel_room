(function () {
  let _dashInterval = null;

  window.switchScreen = function switchScreen(name) {
    const screen = document.getElementById('screen-' + name);
    const btn    = document.getElementById('sw-' + name);
    if (!screen || !btn) {
      console.warn(`switchScreen: missing element for "${name}" — screen=${!!screen}, btn=${!!btn}`);
      return;
    }

    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    screen.classList.add('active');

    document.querySelectorAll('.sw-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

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
    const anyModalOpen = [
      'reg-modal', 'picker-modal', 'pin-modal', 'profile-modal',
      'points-modal', 'face-rereg-modal', 'context-modal', 'promote-modal',
    ].some(id => {
      const el = document.getElementById(id);
      return el && !el.classList.contains('hidden');
    });
    if (anyModalOpen) return;

    if (e.key === 'c' || e.key === 'C') switchScreen('check-in');
    if (e.key === 'd' || e.key === 'D') switchScreen('dashboard');
  });
})();
