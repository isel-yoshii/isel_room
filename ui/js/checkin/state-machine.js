(function () {
  // Every kiosk state is a row in this table, and setState() is the only thing
  // that writes the screen. Fields may be plain values or functions of the data
  // passed to setState — that is how confirmation and success get the member's
  // name in without needing their own hand-written render functions.
  const CHECKIN_STATES = {
    idle: {
      tagClass: 'tag-idle',     tagText: 'Waiting',
      name:     'Stand In Front<br>Of Camera',
      sub:      'Face Recognition Ready',
      faceClass: 'state-idle', scanLine: false,
      card: '', btnText: 'Scan Face', btnDisabled: false,
      hints: [['↵', 'Scan'], ['Space', 'Manual']],
    },
    scanning: {
      tagClass: 'tag-scanning', tagText: 'Scanning',
      name:     'Scanning…',
      sub:      'Hold Still For A Moment',
      faceClass: 'state-scanning', scanLine: true,
      card: '', btnText: 'Scanning…', btnDisabled: true,
      hints: [],
    },
    fail: {
      tagClass: 'tag-fail',     tagText: 'Unknown Face',
      name:     'Face Not<br>Recognised',
      sub:      'Not Registered In The System',
      faceClass: 'state-fail', scanLine: false,
      card: `
        <div class="checkin-card">
          <div class="checkin-avatar av-red">?</div>
          <div class="checkin-info">
            <div class="checkin-name">Unknown Person</div>
            <div class="checkin-detail">Press Space To Check In Manually</div>
          </div>
        </div>`,
      btnText: 'Try Again', btnDisabled: false,
      hints: [['↵', 'Try Again'], ['Space', 'Manual'], ['Esc', 'Back']],
    },
    confirmation: {
      tagClass: 'tag-scanning', tagText: 'Confirm?',
      name:     d => `Is This<br>${esc(d.name)}?`,
      sub:      d => `Will ${d.event === 'IN' ? 'Check In' : 'Check Out'}`,
      faceClass: 'state-scanning', scanLine: false,
      card: '', btnText: 'Confirm', btnDisabled: false,
      hints: [['↵', 'Confirm'], ['Space', 'Manual'], ['Esc', 'Back']],
    },
    success: {
      tagClass: 'tag-success', tagText: 'Recognised',
      name: d => d.event === 'IN'
        ? `Welcome,<br>${esc(d.name)}!`
        : `See You,<br>${esc(d.name)}!`,
      sub: d => {
        const time = new Date().toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });
        return d.event === 'IN' ? `Now In Lab · Since ${time}` : `Left Lab · At ${time}`;
      },
      faceClass: 'state-checkin', scanLine: false,
      card: d => {
        const isIn = d.event === 'IN';
        return `
      <div class="checkin-card">
        <div class="checkin-avatar ${isIn ? 'av-green' : 'av-red'}">${esc(initials(d.name))}</div>
        <div class="checkin-info">
          <div class="checkin-name">${esc(d.name)}</div>
          <div class="checkin-detail">${isIn ? 'Now In Lab' : 'Left Lab'}</div>
        </div>
        <div class="event-badge ${isIn ? 'badge-in' : 'badge-out'}">${isIn ? 'In Lab' : 'Out'}</div>
      </div>`;
      },
      btnText: 'Scan Next', btnDisabled: false,
      hints: [['↵', 'Next']],
    },
  };

  let _currentState = 'idle';
  let _scanningCyclerId = null;

  window.getCheckinState = () => _currentState;

  // Progressive sub-text during the ~2 s scanning window so the user has
  // something changing to track instead of one frozen "Hold Still" string.
  // The interval is purely visual; the actual response arrives whenever the
  // server is done and the next setState() call clears the cycler.
  const _SCAN_PHASES = [
    'Capturing frame 1 of 3…',
    'Capturing frame 2 of 3…',
    'Capturing frame 3 of 3…',
    'Detecting your face…',
    'Matching against lab members…',
    'Almost done…',
  ];

  function _stopScanningCycler() {
    if (_scanningCyclerId) {
      clearInterval(_scanningCyclerId);
      _scanningCyclerId = null;
    }
  }

  function _startScanningCycler() {
    _stopScanningCycler();
    const sub = document.getElementById('state-sub');
    let i = 0;
    sub.textContent = _SCAN_PHASES[i];
    _scanningCyclerId = setInterval(() => {
      i = Math.min(i + 1, _SCAN_PHASES.length - 1);
      sub.textContent = _SCAN_PHASES[i];
    }, 400);
  }

  window.setHints = function setHints(pairs) {
    renderList('check-in-hints', pairs, ([key, label]) =>
      `<div class="hint-group"><kbd class="hint-key">${key}</kbd><span class="hint-label">${label}</span></div>`
    );
  };

  const _value = (field, data) => (typeof field === 'function' ? field(data) : field);

  // setState('confirmation' | 'success', { name, event }) — the data argument is
  // ignored by the states that don't take one.
  window.setState = function setState(key, data = {}) {
    const s = CHECKIN_STATES[key];
    if (!s) return;
    _currentState = key;
    _stopScanningCycler();

    const tag = document.getElementById('state-tag');
    tag.className = 'state-tag ' + s.tagClass;
    document.getElementById('tag-text').textContent = s.tagText;

    document.getElementById('state-name').innerHTML = _value(s.name, data);
    document.getElementById('state-sub').textContent = _value(s.sub, data);
    document.getElementById('result-card').innerHTML = _value(s.card, data);

    document.getElementById('face-box').className = 'face-box ' + s.faceClass;
    document.getElementById('scan-line').style.display = s.scanLine ? 'block' : 'none';

    const btn = document.getElementById('btn-scan');
    btn.textContent = s.btnText;
    btn.disabled    = s.btnDisabled;

    setHints(s.hints ?? []);

    if (key === 'scanning') _startScanningCycler();
  };
})();
