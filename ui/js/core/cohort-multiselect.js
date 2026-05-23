(function () {
  /**
   * mountCohortMultiselect(container, { onChange })
   * Renders a single trigger button that opens a popover with cohort presets,
   * search, and a per-member checkbox list. onChange(selectedIds[]) fires on Apply.
   * Empty list means "all members".
   */
  window.mountCohortMultiselect = function mountCohortMultiselect(container, { onChange } = {}) {
    const state = { allUsers: [], selectedIds: new Set(), filterTerm: '' };

    container.innerHTML = `
      <div class="cohort-ms">
        <button type="button" class="cohort-ms-trigger">All members <span class="cohort-ms-caret">▾</span></button>
        <div class="cohort-ms-popover hidden">
          <div class="cohort-ms-presets">
            <button type="button" data-preset="all">All</button>
            <button type="button" data-preset="B4">B4</button>
            <button type="button" data-preset="M1">M1</button>
            <button type="button" data-preset="M2">M2</button>
            <button type="button" data-preset="Intern">Intern</button>
            <button type="button" data-preset="students">Students</button>
            <button type="button" data-preset="先生">先生</button>
            <button type="button" data-preset="卒業">卒業</button>
          </div>
          <input type="search" class="cohort-ms-search" placeholder="Search members…" />
          <div class="cohort-ms-list"></div>
          <div class="cohort-ms-actions">
            <button type="button" class="btn-ghost cohort-ms-cancel">Cancel</button>
            <button type="button" class="btn-primary cohort-ms-apply">Apply</button>
          </div>
        </div>
      </div>
    `;

    const trigger   = container.querySelector('.cohort-ms-trigger');
    const popover   = container.querySelector('.cohort-ms-popover');
    const presets   = container.querySelector('.cohort-ms-presets');
    const searchEl  = container.querySelector('.cohort-ms-search');
    const listEl    = container.querySelector('.cohort-ms-list');
    const cancelBtn = container.querySelector('.cohort-ms-cancel');
    const applyBtn  = container.querySelector('.cohort-ms-apply');

    function updateTrigger() {
      const n = state.selectedIds.size;
      if (n === 0) { trigger.firstChild.nodeValue = 'All members '; return; }
      if (n === 1) {
        const u = state.allUsers.find(x => x.id === [...state.selectedIds][0]);
        trigger.firstChild.nodeValue = (u?.name || '1 selected') + ' ';
      } else {
        trigger.firstChild.nodeValue = `${n} selected `;
      }
    }

    function renderList() {
      const term = state.filterTerm.toLowerCase();
      const items = state.allUsers
        .filter(u => !term || u.name.toLowerCase().includes(term) || (u.type || '').toLowerCase().includes(term))
        .map(u => `
          <label class="cohort-ms-item">
            <input type="checkbox" data-id="${u.id}" ${state.selectedIds.has(u.id) ? 'checked' : ''} />
            <span class="cohort-ms-item-name">${escAttr(u.name)}</span>
            <span class="cohort-ms-item-type">${escAttr(u.type || '')}</span>
          </label>`).join('');
      listEl.innerHTML = items || '<div class="cohort-ms-empty">No matches</div>';
    }

    function presetIdsFor(preset) {
      if (preset === 'all') return new Set(state.allUsers.map(u => u.id));
      if (preset === 'students') return new Set(
        state.allUsers.filter(u => ['B4','M1','M2'].includes(u.type)).map(u => u.id)
      );
      return new Set(state.allUsers.filter(u => u.type === preset).map(u => u.id));
    }

    function setsEqual(a, b) {
      if (a.size !== b.size) return false;
      for (const v of a) if (!b.has(v)) return false;
      return true;
    }

    function findActivePreset() {
      const presetNames = ['all', 'B4', 'M1', 'M2', 'Intern', 'students', '先生', '卒業'];
      for (const p of presetNames) {
        if (setsEqual(state.selectedIds, presetIdsFor(p))) return p;
      }
      return null;
    }

    function updatePresetHighlight() {
      const active = findActivePreset();
      presets.querySelectorAll('button[data-preset]').forEach(btn => {
        btn.classList.toggle('cohort-ms-preset-active', btn.dataset.preset === active);
      });
    }

    function applyPreset(preset) {
      const wasActive = findActivePreset() === preset;
      state.selectedIds.clear();
      if (!wasActive || preset === 'all') {
        const ids = presetIdsFor(preset);
        ids.forEach(id => state.selectedIds.add(id));
      }
      renderList();
      updatePresetHighlight();
    }

    function openPopover() {
      popover.classList.remove('hidden');
      popover.style.left = '0';
      popover.style.right = 'auto';
      const rect = popover.getBoundingClientRect();
      if (rect.right > window.innerWidth - 8) {
        popover.style.left = 'auto';
        popover.style.right = '0';
      }
      setTimeout(() => searchEl.focus(), 0);
    }
    function closePopover() {
      popover.classList.add('hidden');
    }

    trigger.addEventListener('click', e => {
      e.stopPropagation();
      popover.classList.contains('hidden') ? openPopover() : closePopover();
    });
    document.addEventListener('click', e => {
      if (!container.contains(e.target)) closePopover();
    });
    presets.addEventListener('click', e => {
      const p = e.target.closest('button')?.dataset.preset;
      if (p) applyPreset(p);
    });
    searchEl.addEventListener('input', () => { state.filterTerm = searchEl.value; renderList(); });
    listEl.addEventListener('change', e => {
      const cb = e.target.closest('input[type="checkbox"]');
      if (!cb) return;
      const id = parseInt(cb.dataset.id, 10);
      if (cb.checked) state.selectedIds.add(id);
      else state.selectedIds.delete(id);
      updatePresetHighlight();
    });
    cancelBtn.addEventListener('click', closePopover);
    applyBtn.addEventListener('click', () => {
      updateTrigger();
      closePopover();
      if (onChange) onChange([...state.selectedIds]);
    });

    // Lazy-load member list once.
    api.get('/api/users').then(users => {
      state.allUsers = users;
      renderList();
      updatePresetHighlight();
    }).catch(err => console.error('cohort-multiselect load users error:', err));

    return {
      getSelected: () => [...state.selectedIds],
      setSelected: (ids) => { state.selectedIds = new Set(ids || []); updateTrigger(); renderList(); },
    };
  };
})();
