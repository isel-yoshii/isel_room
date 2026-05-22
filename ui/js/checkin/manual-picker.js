(function () {
  let _pickerUsers    = [];
  let _pickerFiltered = [];
  let _pickerIndex    = 0;

  function renderPickerList(users) {
    const list = document.getElementById('picker-list');
    if (!users.length) {
      list.innerHTML = '<div class="picker-empty">No Members Found</div>';
      return;
    }
    list.innerHTML = users.map((u, i) => {
      return `
        <div class="picker-row ${i === _pickerIndex ? 'active' : ''}"
             onclick="selectPickerUser(${u.id})">
          <div class="picker-av ${avColor(i)}">${esc(initials(u.name))}</div>
          <div class="picker-name">${esc(u.name)}</div>
          <div class="status-pill ${u.status ? 'pill-in' : 'pill-out'}">${u.status ? 'In Lab' : 'Out'}</div>
        </div>`;
    }).join('');
  }

  function updatePickerHighlight(rows) {
    rows.forEach((r, i) => r.classList.toggle('active', i === _pickerIndex));
    rows[_pickerIndex]?.scrollIntoView({ block: 'nearest' });
  }

  window.openManualPicker = async function openManualPicker() {
    try {
      const users = await api.get('/api/users');
      _pickerUsers = [...users].sort((a, b) =>
        (b.status ? 1 : 0) - (a.status ? 1 : 0) || a.name.localeCompare(b.name)
      );
      _pickerIndex    = 0;
      _pickerFiltered = _pickerUsers;

      const search = document.getElementById('picker-search');
      search.value = '';
      renderPickerList(_pickerFiltered);
      document.getElementById('picker-modal').classList.remove('hidden');
      setTimeout(() => search.focus(), 50);

      search.oninput = () => {
        const q = search.value.toLowerCase();
        _pickerFiltered = _pickerUsers.filter(u => u.name.toLowerCase().includes(q));
        _pickerIndex = 0;
        renderPickerList(_pickerFiltered);
      };

      search.onkeydown = (e) => {
        const rows = document.querySelectorAll('#picker-list .picker-row');
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          _pickerIndex = Math.min(_pickerIndex + 1, rows.length - 1);
          updatePickerHighlight(rows);
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          _pickerIndex = Math.max(_pickerIndex - 1, 0);
          updatePickerHighlight(rows);
        } else if (e.key === 'Enter') {
          e.preventDefault();
          const active = document.querySelector('#picker-list .picker-row.active');
          if (active) active.click();
        }
      };
    } catch (err) {
      console.error('openManualPicker error:', err);
    }
  };

  window.closeManualPicker = function closeManualPicker() {
    document.getElementById('picker-modal').classList.add('hidden');
    const search = document.getElementById('picker-search');
    search.oninput   = null;
    search.onkeydown = null;
  };

  window.selectPickerUser = async function selectPickerUser(userId) {
    closeManualPicker();
    const result = await api.post('/api/toggle', { user_id: userId, check_in_method: 'manual' });
    setStateResult(result.name, result.event_type);
    loadMemberStrip();
    setTimeout(() => setState('idle'), 3000);
  };
})();
