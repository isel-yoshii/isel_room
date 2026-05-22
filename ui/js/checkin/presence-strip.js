(function () {
  window.loadMemberStrip = async function loadMemberStrip() {
    try {
      const users = await api.get('/api/users');
      const strip = document.getElementById('member-strip');

      if (!users.length) {
        strip.innerHTML = '<span class="strip-empty">No Members Registered</span>';
        return;
      }

      const sorted = [...users].sort((a, b) =>
        (b.status ? 1 : 0) - (a.status ? 1 : 0) || a.name.localeCompare(b.name)
      );

      strip.innerHTML = sorted.map(u => `
        <div class="mini-member ${u.status ? '' : 'mini-out'}">
          <div class="mini-dot ${u.status ? '' : 'mini-dot-out'}"></div>
          <span class="mini-name">${u.name}</span>
        </div>`).join('');
    } catch {
      /* silent — network blip */
    }
  };
})();
