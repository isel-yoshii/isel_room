(function () {
  let pendingConfirm = null;

  window.scanFace = async function scanFace() {
    if (pendingConfirm) return;
    setState('scanning');
    try {
      const image    = captureFrame('checkin-video');
      const authData = await api.post('/api/auth', { image });

      if (authData.matched) {
        if (authData.low_confidence) {
          setState('fail');
          setTimeout(() => { if (getCheckinState() === 'fail') setState('idle'); }, 8000);
          return;
        }
        const predictedEvent = authData.status ? 'OUT' : 'IN';
        setStateConfirmation(authData.name, predictedEvent);
        pendingConfirm = { userId: authData.user_id };
      } else {
        setState('fail');
        setTimeout(() => { if (getCheckinState() === 'fail') setState('idle'); }, 8000);
      }
    } catch (e) {
      console.error(e);
      setState('idle');
    }
  };

  window.commitToggle = async function commitToggle(userId) {
    pendingConfirm = null;
    try {
      const result = await api.post('/api/toggle', { user_id: userId, check_in_method: 'face' });
      setStateResult(result.name, result.event_type);
      loadMemberStrip();
      setTimeout(() => setState('idle'), 3000);
    } catch (e) {
      console.error('commitToggle error:', e);
      setState('idle');
    }
  };

  window.cancelToggle = function cancelToggle() {
    pendingConfirm = null;
    setState('idle');
  };

  window.onScanBtnClick = function onScanBtnClick() {
    if (pendingConfirm) {
      commitToggle(pendingConfirm.userId);
    } else {
      scanFace();
    }
  };

  window.showCameraError = function showCameraError() {
    const feed = document.querySelector('.cam-feed');
    if (!feed) return;
    if (feed.querySelector('.cam-error-overlay')) return;

    const overlay = document.createElement('div');
    overlay.className = 'cam-error-overlay';
    overlay.innerHTML = `
      <div class="cam-error-icon">⚠</div>
      <div class="cam-error-msg">Camera unavailable</div>
      <div class="cam-error-hint">Press Space To Check In Manually</div>`;
    feed.appendChild(overlay);
    setState('fail');
  };

  window.initCheckin = function initCheckin() {
    window.addEventListener('keydown', (e) => {
      if (!document.getElementById('screen-kiosk').classList.contains('active')) return;

      const pickerOpen  = !document.getElementById('picker-modal').classList.contains('hidden');
      const regOpen     = !document.getElementById('reg-modal').classList.contains('hidden');
      const pinOpen     = !document.getElementById('pin-modal').classList.contains('hidden');
      const profileOpen = !document.getElementById('profile-modal').classList.contains('hidden');

      if (profileOpen) {
        if (e.key === 'Escape') closeProfileModal();
        return;
      }

      if (pickerOpen) {
        if (e.key === 'Escape') closeManualPicker();
        return;
      }

      if (regOpen || pinOpen) return;

      if (e.key === 'Enter') {
        if (e.repeat) return;
        if (pendingConfirm) {
          commitToggle(pendingConfirm.userId);
        } else {
          onScanBtnClick();
        }
      }

      if (e.key === ' ' || e.key === 'Spacebar') {
        e.preventDefault();
        if (pendingConfirm || getCheckinState() === 'fail') {
          openManualPicker();
        }
      }

      if (e.key === 'Escape') {
        cancelToggle();
      }
    });
  };
})();
