(function () {
  window.loadAdmin = async function loadAdmin() {
    await Promise.all([loadAdminUsers(), loadAuditLog()]);
  };

  window.loadAdminUsers = async function loadAdminUsers() {
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
            <div class="status-dot ${u.status ? 'in' : 'out'}" title="${u.status ? 'In Lab' : 'Out'}"></div>
            ${u.status ? `<button class="force-btn" onclick="forceCheckout(${u.id}, '${argName}')">Force Out</button>` : ''}
            <button class="icon-btn" onclick="openEditUserForm(${u.id}, '${argName}', '${argType}')" title="Edit Name / Role">✎</button>
            <button class="icon-btn" onclick="openFaceReregModal(${u.id}, '${argName}')" title="Re-Register Face">⊙</button>
            <button class="del-btn" onclick="deleteUser(${u.id}, '${argName}')">Delete</button>
          </div>`;
      }).join('');
    } catch (err) {
      console.error('loadAdminUsers error:', err);
    }
  };

  window.loadAuditLog = async function loadAuditLog() {
    try {
      const rows = await api.get('/api/audit/log');
      const body = document.getElementById('audit-body');

      if (!rows.length) {
        body.innerHTML = '<div class="log-empty">No Admin Actions Recorded Yet</div>';
        return;
      }

      const ACTION_LABEL = {
        REGISTER: 'Registered', DELETE: 'Deleted',
        CHECKIN: 'Check-In', CHECKOUT: 'Check-Out',
        MANUAL_CHECKIN: 'Manual In', MANUAL_CHECKOUT: 'Manual Out',
        AUTO_CHECKOUT: 'Auto-Out', FORCE_CHECKOUT: 'Force-Out',
        PROMOTE: 'Promoted',
      };
      const IN_ACTIONS = new Set(['REGISTER', 'CHECKIN', 'MANUAL_CHECKIN']);

      body.innerHTML = rows.map(r => {
        const isIn  = IN_ACTIONS.has(r.action);
        const label = ACTION_LABEL[r.action] ?? r.action;
        return `
          <div class="log-row">
            <div class="log-icon ${isIn ? 'log-in' : 'log-out'}">${isIn ? '+' : '×'}</div>
            <div class="log-name">${esc(r.name)}</div>
            <div class="log-ts">${esc(r.timestamp)}</div>
            <div class="status-pill ${isIn ? 'pill-in' : 'pill-out'}">${esc(label)}</div>
          </div>`;
      }).join('');
    } catch (err) {
      console.error('loadAuditLog error:', err);
    }
  };

  window.openEditUserForm = function openEditUserForm(userId, currentName, currentType) {
    const row = document.getElementById(`user-row-${userId}`);
    if (!row) return;

    const ROLE_OPTIONS = ['先生', 'B4', 'M1', 'M2', 'Intern', '卒業']
      .map(t => `<option value="${t}" ${t === currentType ? 'selected' : ''}>${t}</option>`)
      .join('');

    row.innerHTML = `
      <div class="edit-user-form" style="grid-column:1/-1;display:flex;gap:8px;align-items:center;padding:4px 0;">
        <input class="edit-input" id="edit-name-${userId}" value="${esc(currentName)}" style="flex:1" />
        <select class="edit-input" id="edit-type-${userId}">${ROLE_OPTIONS}</select>
        <button class="icon-btn ok-btn" onclick="saveEditUser(${userId})">✓</button>
        <button class="icon-btn" onclick="loadAdminUsers()">✗</button>
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
      if (r.success) { loadAdminUsers(); loadOverview(); }
      else alert(`Failed: ${r.message}`);
    } catch (e) { console.error(e); }
  };

  window.forceCheckout = async function forceCheckout(userId, userName) {
    if (!confirm(`Force "${userName}" out of the lab?`)) return;
    try {
      const res = await api.post(`/api/admin/force-checkout/${userId}`, {});
      if (res.success) { loadAdmin(); loadOverview(); }
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
      if (res.success) { loadAdmin(); loadOverview(); }
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
        loadAdminUsers();
      } else {
        alert(`Failed: ${r.message}`);
      }
    } catch { alert('Network Error Occurred.'); }
  };

  window.Dashboard = window.Dashboard || {};
  window.Dashboard.Admin = {
    init:    () => loadAdmin(),
    destroy: () => {},
  };
})();
