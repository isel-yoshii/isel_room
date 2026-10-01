(function () {
  let pendingConfirm = null;
  let currentScanId = null;

  window.loadMemberStrip = async function loadMemberStrip() {
    try {
      const users = await api.get('/api/users');
      const sorted = [...users].sort(byPresenceThenName);
      renderList('member-strip', sorted, u => `
        <div class="mini-member ${u.status ? '' : 'mini-out'}">
          <span class="mini-name">${u.name}</span>
        </div>`,
        '<span class="strip-empty">No Members Registered</span>');
    } catch {
      /* silent — network blip */
    }
  };

  window.scanFace = async function scanFace() {
    if (pendingConfirm) return;

    const myScanId = Date.now();
    currentScanId = myScanId;

    setState('scanning');
    try {
      const images   = await captureBurst('checkin-video');
      const authData = await api.post('/api/auth', { images });

      if (currentScanId !== myScanId) {
        console.log("Old ScanID(Deleted)");
        return; 
      }

      if (authData.matched) {
        if (authData.low_confidence) {
          setState('fail');
          setTimeout(() => { if (getCheckinState() === 'fail') setState('idle'); }, 8000);
          return;
        }
        setState('confirmation', { name: authData.name, status: authData.status });
        pendingConfirm = { userId: authData.user_id };
      } else {
        setState('fail');
        setTimeout(() => { if (getCheckinState() === 'fail') setState('idle'); }, 8000);
      }
    } catch (e) {
      if (currentScanId !== myScanId) return;
      console.error(e);
      setState('idle');
    }
  };

  // action is 'in' or 'out'. Explicit rather than a toggle: Wi-Fi may already
  // have checked the person in, and a toggle would then check them out.
  window.commitEntry = async function commitEntry(action) {
    if (!pendingConfirm) return;
    const userId = pendingConfirm.userId;
    pendingConfirm = null;
    try {
      const result = await api.post('/api/toggle', { user_id: userId, check_in_method: 'face', action });
      if (!result.event_type) throw new Error(result.message);
      setState('success', { name: result.name, event: result.event_type, changed: result.changed });
      loadMemberStrip();
      setTimeout(() => setState('idle'), 3000);
    } catch (e) {
      console.error('commitEntry error:', e);
      setState('idle');
    }
  };

  window.cancelToggle = function cancelToggle() {
    pendingConfirm = null;
    currentScanId = null;
    setState('idle');
  };

  window.onScanBtnClick = function onScanBtnClick() {
    if (!pendingConfirm) scanFace();
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
      if (!document.getElementById('screen-check-in').classList.contains('active')) return;

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
        onScanBtnClick();
      }

      if (pendingConfirm && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) {
        e.preventDefault();
        if (e.repeat) return;
        commitEntry(e.key === 'ArrowLeft' ? 'in' : 'out');
      }

      if (e.key === ' ' || e.key === 'Spacebar') {
        e.preventDefault();
        const st = getCheckinState();
        if (pendingConfirm || st === 'fail' || st === 'idle') {
          // Drop the face match first, or it outlives the picker and blocks the next scan.
          if (pendingConfirm) cancelToggle();
          openManualPicker();
        }
      }

      if (e.key === 'Escape') {
        cancelToggle();
      }
    });
  };
})();
