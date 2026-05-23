(function () {
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
  };

  let _currentState = 'idle';

  window.getCheckinState = () => _currentState;

  window.setHints = function setHints(pairs) {
    const el = document.getElementById('check-in-hints');
    if (!el) return;
    el.innerHTML = pairs.map(([key, label]) =>
      `<div class="hint-group"><kbd class="hint-key">${key}</kbd><span class="hint-label">${label}</span></div>`
    ).join('');
  };

  window.setState = function setState(key) {
    const s = CHECKIN_STATES[key];
    if (!s) return;
    _currentState = key;

    const tag = document.getElementById('state-tag');
    tag.className = 'state-tag ' + s.tagClass;
    document.getElementById('tag-text').textContent = s.tagText;

    document.getElementById('state-name').innerHTML = s.name;
    document.getElementById('state-sub').textContent = s.sub;
    document.getElementById('result-card').innerHTML = s.card;

    document.getElementById('face-box').className = 'face-box ' + s.faceClass;
    document.getElementById('scan-line').style.display = s.scanLine ? 'block' : 'none';

    const btn = document.getElementById('btn-scan');
    btn.textContent = s.btnText;
    btn.disabled    = s.btnDisabled;

    setHints(s.hints ?? []);
  };

  window.setStateConfirmation = function setStateConfirmation(name, predictedEvent) {
    _currentState = 'confirmation';
    const isIn = predictedEvent === 'IN';

    const tag = document.getElementById('state-tag');
    tag.className = 'state-tag tag-scanning';
    document.getElementById('tag-text').textContent = 'Confirm?';

    document.getElementById('state-name').innerHTML = `Is This<br>${name}?`;
    document.getElementById('state-sub').textContent = `Will ${isIn ? 'Check In' : 'Check Out'}`;

    document.getElementById('result-card').innerHTML = '';

    document.getElementById('face-box').className = 'face-box state-scanning';
    document.getElementById('scan-line').style.display = 'none';

    const btn = document.getElementById('btn-scan');
    btn.textContent = 'Confirm';
    btn.disabled    = false;

    setHints([['↵', 'Confirm'], ['Space', 'Manual'], ['Esc', 'Back']]);
  };

  window.setStateResult = function setStateResult(name, eventType) {
    _currentState = 'success';
    const isIn  = eventType === 'IN';
    const inits = name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
    const time  = new Date().toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });

    const tag = document.getElementById('state-tag');
    tag.className = 'state-tag tag-success';
    document.getElementById('tag-text').textContent = 'Recognised';

    document.getElementById('state-name').innerHTML = isIn
      ? `Welcome,<br>${name}!`
      : `See You,<br>${name}!`;

    document.getElementById('state-sub').textContent = isIn
      ? `Now In Lab · Since ${time}`
      : `Left Lab · At ${time}`;

    document.getElementById('result-card').innerHTML = `
      <div class="checkin-card">
        <div class="checkin-avatar ${isIn ? 'av-green' : 'av-red'}">${inits}</div>
        <div class="checkin-info">
          <div class="checkin-name">${name}</div>
          <div class="checkin-detail">${isIn ? 'Now In Lab' : 'Left Lab'}</div>
        </div>
        <div class="event-badge ${isIn ? 'badge-in' : 'badge-out'}">${isIn ? 'In Lab' : 'Out'}</div>
      </div>`;

    document.getElementById('face-box').className = 'face-box state-checkin';
    document.getElementById('scan-line').style.display = 'none';

    const btn = document.getElementById('btn-scan');
    btn.textContent = 'Scan Next';
    btn.disabled    = false;

    setHints([['↵', 'Next']]);
  };
})();
