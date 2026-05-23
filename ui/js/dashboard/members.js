(function () {
  window.loadMembers = async function loadMembers() {
    try {
      const users = await api.get('/api/users');
      const grid  = document.getElementById('admin-grid');

      if (!users.length) {
        grid.innerHTML = '<div class="log-empty">No Members Registered Yet</div>';
        return;
      }

      grid.innerHTML = users.map((u, i) => {
        const grad = isGraduated(u.type);
        const safeName = esc(u.name);
        const argName  = escAttr(u.name);
        const safeType = esc(u.type);
        const argType  = escAttr(u.type);
        return `
          <div class="user-row ${grad ? 'user-row-grad' : ''}" id="user-row-${u.id}">
            <div class="avatar ${avColor(i)}" style="width:36px;height:36px;font-size:12px;${grad ? 'opacity:0.45' : ''}">
              ${esc(initials(u.name))}
            </div>
            <div class="user-info">
              <div class="user-name">${safeName}</div>
              <div class="user-role">
                <span class="role-badge ${roleBadgeClass(u.type)}">${safeType}</span>
                <span class="face-badge ${u.has_face ? 'badge-face-ok' : 'badge-face-none'}">
                  ${u.face_variants && u.face_variants.length ? u.face_variants.join(' · ') : 'No Face'}
                </span>
              </div>
            </div>
            <button class="icon-btn" onclick="openEditUserForm(${u.id}, '${argName}', '${argType}')" title="Edit Name / Role">✎</button>
            <button class="icon-btn" onclick="openFaceReregModal(${u.id}, '${argName}')" title="Add Face Variant">⊙</button>
            <button class="del-btn" onclick="deleteUser(${u.id}, '${argName}')">Delete</button>
          </div>`;
      }).join('');
    } catch (err) {
      console.error('loadMembers error:', err);
    }
  };

  window.openEditUserForm = function openEditUserForm(userId, currentName, currentType) {
    const row = document.getElementById(`user-row-${userId}`);
    if (!row) return;

    const ROLE_OPTIONS = ['先生', 'B4', 'M1', 'M2', 'PhD', 'Intern', '卒業']
      .map(t => `<option value="${t}" ${t === currentType ? 'selected' : ''}>${t}</option>`)
      .join('');

    row.innerHTML = `
      <div class="edit-user-form" style="grid-column:1/-1;display:flex;gap:8px;align-items:center;padding:4px 0;">
        <input class="edit-input" id="edit-name-${userId}" value="${esc(currentName)}" style="flex:1" />
        <select class="edit-input" id="edit-type-${userId}">${ROLE_OPTIONS}</select>
        <button class="icon-btn ok-btn" onclick="saveEditUser(${userId})">✓</button>
        <button class="icon-btn" onclick="loadMembers()">✗</button>
      </div>`;
  };

  window.saveEditUser = async function saveEditUser(userId) {
    const name     = document.getElementById(`edit-name-${userId}`)?.value.trim();
    const userType = document.getElementById(`edit-type-${userId}`)?.value;
    if (!name || !userType) return;
    try {
      const r = await fetch(`/api/user/${userId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, user_type: userType }),
      }).then(r => r.json());
      if (r.success) { loadMembers(); loadOverview(); }
      else alert(`Failed: ${r.message}`);
    } catch (e) { console.error(e); }
  };

  window.deleteUser = async function deleteUser(userId, userName) {
    if (!confirm(`Are you sure you want to delete "${userName}"?\nThis action cannot be undone.`)) return;
    try {
      const res = await fetch(`/api/user/${userId}`, { method: 'DELETE' }).then(r => r.json());
      if (res.success) { loadMembers(); loadOverview(); }
      else alert(`Failed to delete: ${res.message}`);
    } catch (e) {
      console.error('Delete error:', e);
      alert('Network error occurred.');
    }
  };

  const PROMOTE_OPTIONS = {
    B4:  { default: 'M1',   choices: ['M1', '卒業', '__skip__'] },
    M1:  { default: 'M2',   choices: ['M2', '__skip__'] },
    M2:  { default: '卒業', choices: ['卒業', 'PhD', '__skip__'] },
    PhD: { default: '卒業', choices: ['卒業', '__skip__'] },
  };

  window.runPromotion = async function runPromotion() {
    document.getElementById('promote-modal').classList.remove('hidden');
    document.getElementById('promote-msg').textContent = '';
    const body = document.getElementById('promote-body');
    body.innerHTML = '<div class="log-empty">Loading…</div>';
    try {
      const users = await api.get('/api/users');
      const promotable = users.filter(u => PROMOTE_OPTIONS[u.type]);
      if (!promotable.length) {
        body.innerHTML = '<div class="log-empty">No promotable students right now.</div>';
        return;
      }
      body.innerHTML = `
        <table class="promote-table">
          <thead><tr><th>Name</th><th>Current</th><th></th><th>New role</th></tr></thead>
          <tbody>
            ${promotable.map(u => {
              const opts = PROMOTE_OPTIONS[u.type].choices;
              const def  = PROMOTE_OPTIONS[u.type].default;
              return `
                <tr data-user-id="${u.id}">
                  <td>${esc(u.name)}</td>
                  <td><span class="role-badge ${roleBadgeClass(u.type)}">${esc(u.type)}</span></td>
                  <td class="promote-arrow">→</td>
                  <td>
                    <select class="promote-select">
                      ${opts.map(o => {
                        const label = o === '__skip__' ? 'No change' : o;
                        return `<option value="${o}" ${o === def ? 'selected' : ''}>${label}</option>`;
                      }).join('')}
                    </select>
                  </td>
                </tr>`;
            }).join('')}
          </tbody>
        </table>`;
    } catch (err) {
      console.error('runPromotion error:', err);
      body.innerHTML = '<div class="log-empty">Failed to load members.</div>';
    }
  };

  window.closePromoteModal = function closePromoteModal() {
    document.getElementById('promote-modal').classList.add('hidden');
  };

  window.closePromoteModalOnBg = function closePromoteModalOnBg(event) {
    if (event.target === document.getElementById('promote-modal')) closePromoteModal();
  };

  window.applyPromotions = async function applyPromotions() {
    const rows = document.querySelectorAll('#promote-body tr[data-user-id]');
    const promotions = [];
    rows.forEach(r => {
      const newType = r.querySelector('.promote-select').value;
      if (newType === '__skip__') return;
      promotions.push({ user_id: parseInt(r.dataset.userId, 10), new_type: newType });
    });
    const msg = document.getElementById('promote-msg');
    if (!promotions.length) {
      msg.textContent = 'No changes selected.';
      return;
    }
    if (!confirm(`Apply ${promotions.length} promotion${promotions.length === 1 ? '' : 's'}?`)) return;
    try {
      const r = await api.post('/api/admin/promote-students', { promotions });
      if (r.success) {
        const summary = Object.entries(r.promoted).map(([k, v]) => `${v}× ${k}`).join(' · ');
        alert(`Promotion complete: ${summary || 'no changes'}`);
        closePromoteModal();
        loadMembers();
        if (typeof loadOverview === 'function') loadOverview();
      } else {
        msg.textContent = r.message || 'Failed.';
      }
    } catch (e) {
      console.error('applyPromotions error:', e);
      msg.textContent = 'Network error.';
    }
  };

window.exportSessionsCsv = function exportSessionsCsv() {
    const now = new Date();
    const year  = prompt('Year?',  now.getFullYear());
    if (!year) return;
    const month = prompt('Month? (1-12)', now.getMonth() + 1);
    if (!month) return;
    window.location = `/api/export/csv?year=${encodeURIComponent(year)}&month=${encodeURIComponent(month)}`;
  };
})();
