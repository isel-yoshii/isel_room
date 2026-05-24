(function () {
  /* ── Helpers ── */

  async function captureBurst(videoId, count = 3, gapMs = 350) {
    const video  = document.getElementById(videoId);
    const canvas = document.getElementById('capture-canvas');
    canvas.width  = video.videoWidth  || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    const frames = [];
    for (let i = 0; i < count; i++) {
      ctx.drawImage(video, 0, 0);
      frames.push(canvas.toDataURL('image/jpeg', 0.85));
      if (i < count - 1) await new Promise(r => setTimeout(r, gapMs));
    }
    return frames;
  }

  /* ── Admin PIN modal ── */

  let _pinCallback = null;

  window.openPinModal = function openPinModal(callback) {
    _pinCallback = callback;
    document.getElementById('pin-input').value = '';
    const msg = document.getElementById('pin-msg');
    msg.textContent = '';
    msg.className   = 'modal-msg';
    document.getElementById('pin-modal').classList.remove('hidden');
    setTimeout(() => document.getElementById('pin-input').focus(), 50);
  };

  window.closePinModal = function closePinModal() {
    document.getElementById('pin-modal').classList.add('hidden');
    _pinCallback = null;
  };

  window.closePinModalOnBg = function closePinModalOnBg(event) {
    if (event.target === document.getElementById('pin-modal')) closePinModal();
  };

  window.submitPin = async function submitPin() {
    const pin = document.getElementById('pin-input').value;
    const msg = document.getElementById('pin-msg');
    const btn = document.getElementById('btn-pin-submit');

    if (!pin) {
      msg.textContent = 'Enter A PIN';
      msg.className   = 'modal-msg err';
      return;
    }

    btn.disabled    = true;
    msg.textContent = '';

    try {
      const data = await api.post('/api/admin/login', { pin });
      if (data.success) {
        closePinModal();
        if (_pinCallback) _pinCallback();
      } else {
        msg.textContent = data.message || 'Wrong PIN';
        msg.className   = 'modal-msg err';
        document.getElementById('pin-input').value = '';
        document.getElementById('pin-input').focus();
      }
    } catch {
      msg.textContent = 'Server Error';
      msg.className   = 'modal-msg err';
    }

    btn.disabled = false;
  };

  window.adminLogout = async function adminLogout() {
    await api.post('/api/admin/logout', {});
    const overviewBtn = document.getElementById('sbt-overview');
    activateDashTab('overview', overviewBtn);
    loadOverview();
  };

  /* ── Registration modal ── */

  let _regStream = null;

  /* ── Registration 3-step wizard (normal → glasses → mask) ── */

  const REG_STEPS = [
    { key: 'normal',  label: 'Normal',  hint: 'no glasses, no mask', skippable: false },
    { key: 'glasses', label: 'Glasses', hint: 'put glasses on now',  skippable: true  },
    { key: 'mask',    label: 'Mask',    hint: 'put a mask on now',   skippable: true  },
  ];
  let _regStep = 0;
  let _regVariants = {};

  function _renderRegStep() {
    document.querySelectorAll('#reg-modal .reg-dot').forEach((el, i) => {
      el.classList.toggle('reg-dot-on',   i === _regStep);
      el.classList.toggle('reg-dot-done', i <  _regStep);
    });
    const s = REG_STEPS[_regStep];
    document.getElementById('reg-step-label').innerHTML =
      `Step ${_regStep + 1} of 3 — <strong>${s.label}</strong> (${s.hint})`;
    document.getElementById('btn-register').textContent =
      _regStep < REG_STEPS.length - 1 ? 'Capture' : 'Capture & Register';
    document.getElementById('btn-register-skip').hidden = !s.skippable;
  }

  window.openRegModal = function openRegModal() {
    const modal = document.getElementById('reg-modal');
    modal.classList.remove('hidden');

    document.getElementById('reg-name').value = '';
    const msg = document.getElementById('reg-msg');
    msg.textContent = '';
    msg.className   = 'modal-msg';
    document.getElementById('btn-register').disabled = false;
    _regStep = 0;
    _regVariants = {};
    _renderRegStep();

    navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      .then(stream => {
        _regStream = stream;
        document.getElementById('reg-video').srcObject = stream;
      })
      .catch(() => {
        msg.textContent = 'Camera Access Denied';
        msg.className   = 'modal-msg err';
      });
  };

  window.closeRegModal = function closeRegModal() {
    document.getElementById('reg-modal').classList.add('hidden');
    if (_regStream) {
      _regStream.getTracks().forEach(t => t.stop());
      _regStream = null;
    }
  };

  window.closeRegModalOnBg = function closeRegModalOnBg(event) {
    if (event.target === document.getElementById('reg-modal')) closeRegModal();
  };

  window.onRegStepCapture = async function onRegStepCapture() {
    const name = document.getElementById('reg-name').value.trim();
    const msg  = document.getElementById('reg-msg');
    const btn  = document.getElementById('btn-register');

    if (!name) {
      msg.textContent = 'Please Enter A Name';
      msg.className   = 'modal-msg err';
      return;
    }
    if (!_regStream) {
      msg.textContent = 'Camera Not Available';
      msg.className   = 'modal-msg err';
      return;
    }

    btn.disabled    = true;
    msg.textContent = `Capturing ${REG_STEPS[_regStep].label}…`;
    msg.className   = 'modal-msg';
    const frames = await captureBurst('reg-video');
    _regVariants[REG_STEPS[_regStep].key] = frames;
    _regStep++;
    if (_regStep < REG_STEPS.length) {
      btn.disabled = false;
      msg.textContent = '';
      _renderRegStep();
    } else {
      await _submitRegistration();
    }
  };

  window.onRegStepSkip = function onRegStepSkip() {
    _regStep++;
    if (_regStep < REG_STEPS.length) {
      _renderRegStep();
    } else {
      _submitRegistration();
    }
  };

  async function _submitRegistration() {
    const name     = document.getElementById('reg-name').value.trim();
    const userType = document.getElementById('reg-type').value;
    const msg      = document.getElementById('reg-msg');
    const btn      = document.getElementById('btn-register');
    msg.textContent = 'Processing…';
    msg.className   = 'modal-msg';
    try {
      const data = await api.post('/api/register', {
        name, user_type: userType, variants: _regVariants,
      });
      if (data.success) {
        msg.textContent = data.message || `${name} registered!`;
        msg.className   = 'modal-msg ok';
        setTimeout(() => { closeRegModal(); loadMembers(); }, 1500);
      } else {
        msg.textContent = data.message || 'Registration Failed';
        msg.className   = 'modal-msg err';
        _regStep = 0;
        _regVariants = {};
        _renderRegStep();
        btn.disabled = false;
      }
    } catch {
      msg.textContent = 'Server Error — Please Try Again';
      msg.className   = 'modal-msg err';
      btn.disabled = false;
    }
  }

  /* ── Face re-registration modal ── */

  let _faceReregStream = null;
  let _faceReregUserId = null;

  window.openFaceReregModal = function openFaceReregModal(userId, userName) {
    _faceReregUserId = userId;
    document.getElementById('face-rereg-title').textContent = `Add Face Variant — ${userName}`;
    const normalRadio = document.querySelector('input[name="rereg-variant"][value="normal"]');
    if (normalRadio) normalRadio.checked = true;
    const msg = document.getElementById('face-rereg-msg');
    msg.textContent = '';
    msg.className   = 'modal-msg';

    navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      .then(stream => {
        _faceReregStream = stream;
        document.getElementById('face-rereg-video').srcObject = stream;
      })
      .catch(() => {
        msg.textContent = 'Camera Access Denied';
        msg.className   = 'modal-msg err';
      });

    document.getElementById('face-rereg-modal').classList.remove('hidden');
  };

  window.closeFaceReregModal = function closeFaceReregModal() {
    document.getElementById('face-rereg-modal').classList.add('hidden');
    if (_faceReregStream) {
      _faceReregStream.getTracks().forEach(t => t.stop());
      _faceReregStream = null;
    }
    _faceReregUserId = null;
  };

  window.closeFaceReregModalOnBg = function closeFaceReregModalOnBg(event) {
    if (event.target === document.getElementById('face-rereg-modal')) closeFaceReregModal();
  };

  window.captureAndReregFace = async function captureAndReregFace() {
    if (!_faceReregUserId || !_faceReregStream) return;
    const variant = document.querySelector('input[name="rereg-variant"]:checked')?.value || 'normal';
    const msg = document.getElementById('face-rereg-msg');
    const btn = document.getElementById('btn-face-rereg');
    btn.disabled    = true;
    msg.textContent = `Capturing ${variant}…`;
    msg.className   = 'modal-msg';
    const images = await captureBurst('face-rereg-video');
    msg.textContent = 'Processing…';

    try {
      const r = await api.post(`/api/user/${_faceReregUserId}/face`, { variant, images });

      if (r.success) {
        msg.textContent = r.variants
          ? `Updated ${variant} (now: ${r.variants.join(' · ')})`
          : 'Face Updated';
        msg.className   = 'modal-msg ok';
        setTimeout(() => { closeFaceReregModal(); loadMembers(); }, 1400);
      } else {
        msg.textContent = r.message || 'Failed';
        msg.className   = 'modal-msg err';
      }
    } catch {
      msg.textContent = 'Server Error — Please Try Again';
      msg.className   = 'modal-msg err';
    }
    btn.disabled = false;
  };

  /* ── Member profile modal ── */

  let _currentProfileUserId = null;

  window.openProfileModal = async function openProfileModal(userId) {
    if (userId == null) return;
    _currentProfileUserId = userId;
    window._currentProfileUserId = userId;
    try {
      const data = await api.get(`/api/user/${userId}/profile`);

      document.getElementById('profile-name').textContent = data.name;

      document.getElementById('profile-badges').innerHTML = `
        <span class="role-badge ${roleBadgeClass(data.type)}" style="margin-right:4px">
          ${data.type}
        </span>
        <span class="face-badge ${data.has_face ? 'badge-face-ok' : 'badge-face-none'}">
          ${data.has_face ? 'Enrolled' : 'No Face'}
        </span>`;

      const ms = data.monthly_stats;
      document.getElementById('profile-monthly').innerHTML = `
        <div class="profile-stats-row">
          <div class="profile-stat">
            <div class="profile-stat-val">${ms.sessions}</div>
            <div class="profile-stat-lbl">Sessions This Month</div>
          </div>
          <div class="profile-stat">
            <div class="profile-stat-val">${fmtMins(ms.total_minutes)}</div>
            <div class="profile-stat-lbl">Total Time This Month</div>
          </div>
          ${ms.sessions > 0 ? `<div class="profile-stat">
            <div class="profile-stat-val">${fmtMins(Math.round(ms.total_minutes / ms.sessions))}</div>
            <div class="profile-stat-lbl">Avg Per Session</div>
          </div>` : ''}
        </div>`;

      if (!data.recent_sessions.length) {
        document.getElementById('profile-sessions').innerHTML = '<div class="log-empty">No Sessions Recorded Yet</div>';
      } else {
        document.getElementById('profile-sessions').innerHTML = `
          <div class="profile-sess-table">
            <div class="profile-sess-header">
              <div>Date</div><div>In</div><div>Out</div><div>Duration</div><div>Method</div><div></div>
            </div>
            ${data.recent_sessions.map(s => `
              <div class="profile-sess-row" id="sess-row-${s.id}">
                <div>${s.date}</div>
                <div>${s.checked_in_at}</div>
                <div>${s.checked_out_at ?? '–'}</div>
                <div>${fmtMins(s.duration_minutes)}</div>
                <div>${s.check_in_method}</div>
                <div><button class="icon-btn" onclick="openEditSessionForm(${s.id}, '${s.checked_in_at_iso}', '${s.checked_out_at_iso ?? ''}')">✎</button></div>
              </div>`).join('')}
          </div>`;
      }

      document.getElementById('profile-modal').classList.remove('hidden');
    } catch (err) {
      console.error('openProfileModal error:', err);
    }
  };

  window.closeProfileModal = function closeProfileModal() {
    document.getElementById('profile-modal').classList.add('hidden');
  };

  window.closeProfileModalOnBg = function closeProfileModalOnBg(event) {
    if (event.target === document.getElementById('profile-modal')) closeProfileModal();
  };

  /* ── Session time editing ── */

  window.openEditSessionForm = function openEditSessionForm(sessionId, inIso, outIso) {
    const row = document.getElementById(`sess-row-${sessionId}`);
    if (!row) return;
    row.innerHTML = `
      <div style="grid-column:1/-1;display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
        <label style="font-size:11px;color:var(--color-text-secondary)">In</label>
        <input type="datetime-local" class="edit-input" id="sess-in-${sessionId}"
               value="${inIso ? inIso.slice(0,16) : ''}" />
        <label style="font-size:11px;color:var(--color-text-secondary)">Out</label>
        <input type="datetime-local" class="edit-input" id="sess-out-${sessionId}"
               value="${outIso ? outIso.slice(0,16) : ''}" />
        <button class="icon-btn ok-btn" onclick="saveEditSession(${sessionId})">✓</button>
        <button class="icon-btn" onclick="openProfileModal(_currentProfileUserId)">✗</button>
      </div>`;
  };

  window.saveEditSession = async function saveEditSession(sessionId) {
    const inVal  = document.getElementById(`sess-in-${sessionId}`)?.value;
    const outVal = document.getElementById(`sess-out-${sessionId}`)?.value;
    if (!inVal) return;
    try {
      const r = await api.put(`/api/session/${sessionId}`, {
        checked_in_at:  inVal  ? inVal  + ':00' : null,
        checked_out_at: outVal ? outVal + ':00' : null,
      });
      if (r.success && _currentProfileUserId) openProfileModal(_currentProfileUserId);
      else alert(`Failed: ${r.message}`);
    } catch (e) { console.error(e); }
  };
})();
