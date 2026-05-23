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
                  ${u.has_face ? 'Enrolled' : 'No Face'}
                </span>
              </div>
            </div>
            ${u.status ? `<button class="force-btn" onclick="forceCheckout(${u.id}, '${argName}')">Force Out</button>` : ''}
            <button class="icon-btn" onclick="openEditUserForm(${u.id}, '${argName}', '${argType}')" title="Edit Name / Role">✎</button>
            <button class="icon-btn" onclick="openFaceReregModal(${u.id}, '${argName}')" title="Re-Register Face">⊙</button>
            <button class="icon-btn" onclick="openPointsModal(${u.id}, '${argName}')" title="Adjust Points">±</button>
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

  window.forceCheckout = async function forceCheckout(userId, userName) {
    if (!confirm(`Force "${userName}" out of the lab?`)) return;
    try {
      const res = await api.post(`/api/admin/force-checkout/${userId}`, {});
      if (res.success) { loadMembers(); loadOverview(); }
      else alert(`Failed: ${res.message}`);
    } catch (e) {
      console.error('forceCheckout error:', e);
      alert('Network error occurred.');
    }
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

  window.runPromotion = async function runPromotion() {
    if (!confirm('Promote all students?\nB4 → M1 · M1 → M2 · M2 → 卒業\n\nThis cannot be undone.')) return;
    try {
      const r = await fetch('/api/admin/promote-students', { method: 'POST' }).then(r => r.json());
      if (r.success) {
        const { B4, M1, M2 } = r.promoted;
        alert(`Promotion complete.\n${B4} B4 → M1 · ${M1} M1 → M2 · ${M2} M2 → 卒業`);
        loadMembers();
      } else {
        alert(`Failed: ${r.message}`);
      }
    } catch { alert('Network Error Occurred.'); }
  };

  /* ── Points adjustment modal ── */

  let _pointsUserId = null;

  window.openPointsModal = function openPointsModal(userId, name) {
    _pointsUserId = userId;
    document.getElementById('points-modal-name').textContent = name;
    document.getElementById('points-delta').value = '';
    document.getElementById('points-note').value  = '';
    document.getElementById('points-msg').textContent = '';
    document.getElementById('points-modal').classList.remove('hidden');
    document.getElementById('points-delta').focus();
  };

  window.closePointsModal = function closePointsModal() {
    document.getElementById('points-modal').classList.add('hidden');
    _pointsUserId = null;
  };

  window.closePointsModalOnBg = function closePointsModalOnBg(event) {
    if (event.target === document.getElementById('points-modal')) closePointsModal();
  };

  window.submitPointsAdjust = async function submitPointsAdjust() {
    if (_pointsUserId == null) return;
    const deltaRaw = document.getElementById('points-delta').value;
    const note     = document.getElementById('points-note').value.trim();
    const delta    = parseInt(deltaRaw, 10);
    const msg      = document.getElementById('points-msg');
    if (!Number.isInteger(delta) || delta === 0) {
      msg.textContent = 'Delta must be a non-zero integer.';
      return;
    }
    try {
      const r = await api.post('/api/admin/points/adjust', {
        user_id: _pointsUserId, delta, note,
      });
      if (r.success) { closePointsModal(); if (typeof loadActivity === 'function') loadActivity(); }
      else msg.textContent = r.message || 'Failed to adjust points.';
    } catch (e) {
      console.error('submitPointsAdjust error:', e);
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
