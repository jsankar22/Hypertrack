// Workout Log page: exercise list, add/edit modal, live stats, save.
(function () {
    'use strict';

    const stateEl = document.getElementById('log-state');
    if (!stateEl) return;
    const S = JSON.parse(stateEl.textContent);

    const $ = (id) => document.getElementById(id);
    const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, (c) => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));
    const num = (n) => String(+n);                     // 60.0 -> "60", 62.5 -> "62.5"
    const csrf = () => (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '';

    // Duration/calorie estimate: ~45 s of work per set plus rest, strength-training MET of 5.
    const WORK_SEC = 45, DEFAULT_REST = 90, MET = 5;

    let exercises = S.exercises.map((e) => Object.assign({}, e));
    let durationTouched = S.hasSession && S.duration != null;
    let manualDuration = S.duration || 0;
    let dirty = false;
    let editing = null;         // index being edited, or null when adding
    let lastFocus = null;

    const library = {};
    S.library.forEach((l) => { library[l.name.toLowerCase()] = l; });

    // ---------- stats ----------
    function estimateMinutes() {
        let sec = 0;
        exercises.forEach((e) => {
            if (!e.sets.length) return;
            const rest = e.rest != null && e.rest !== '' ? +e.rest : DEFAULT_REST;
            sec += e.sets.length * (WORK_SEC + rest);
        });
        return Math.round(sec / 60);
    }
    const currentDuration = () => (durationTouched ? manualDuration : estimateMinutes());
    const caloriesFor = (min) => Math.round(MET * S.userWeight * (min / 60));

    function renderStats() {
        const min = currentDuration();
        const input = $('stat-duration');
        if (document.activeElement !== input) input.value = min;
        $('stat-calories').textContent = caloriesFor(min);
        $('stat-count').textContent = exercises.length;
    }

    // ---------- table ----------
    const ICON_EDIT = '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487z"/></svg>';
    const ICON_DEL = '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>';

    function renderRows() {
        const body = $('ex-body');
        if (!exercises.length) {
            body.innerHTML = '<tr><td colspan="6" class="!py-10 text-center text-sm text-gray-500">No exercises yet. Use “Add Exercise” to start logging.</td></tr>';
            return;
        }
        body.innerHTML = exercises.map((e, i) => {
            const details = e.sets.length
                ? e.sets.map((s) => `<span class="wk-pill">${esc(num(s.reps))} @ ${+s.weight === 0 ? '<abbr title="Bodyweight">BW</abbr>' : esc(num(s.weight))}</span>`).join('')
                : '<span class="text-gray-300">—</span>';
            const rest = e.rest != null && e.rest !== '' ? `${esc(e.rest)}s` : '-';
            return `<tr>
                <td class="text-gray-500">${i + 1}</td>
                <td><span class="font-medium text-gray-900">${esc(e.name)}</span>${e.group ? `<span class="block text-xs text-gray-400">${esc(e.group)}</span>` : ''}</td>
                <td>${e.sets.length || '-'}</td>
                <td>${details}</td>
                <td class="hidden sm:table-cell text-gray-600">${rest}</td>
                <td class="text-right whitespace-nowrap">
                    <button type="button" class="wk-icon-btn" data-act="edit" data-i="${i}" aria-label="Edit ${esc(e.name)}">${ICON_EDIT}</button>
                    <button type="button" class="wk-icon-btn is-danger" data-act="del" data-i="${i}" aria-label="Remove ${esc(e.name)}">${ICON_DEL}</button>
                </td>
            </tr>`;
        }).join('');
    }

    function render() { renderRows(); renderStats(); }
    function markDirty() { dirty = true; }

    $('ex-body').addEventListener('click', (ev) => {
        const btn = ev.target.closest('button[data-act]');
        if (!btn) return;
        const i = +btn.dataset.i;
        if (btn.dataset.act === 'edit') {
            openModal(i, btn);
        } else {
            exercises.splice(i, 1);
            markDirty();
            render();
        }
    });

    // ---------- modal ----------
    const modal = $('ex-modal');

    function fillDatalists() {
        $('lib-list').innerHTML = S.library.map((l) => `<option value="${esc(l.name)}"></option>`).join('');
        const groups = [...new Set(S.library.map((l) => l.group).filter(Boolean))].sort();
        $('group-list').innerHTML = groups.map((g) => `<option value="${esc(g)}"></option>`).join('');
    }

    function readRows() {
        return [...document.querySelectorAll('#m-rows .set-row')].map((r) => ({
            reps: r.querySelector('.s-reps').value,
            weight: r.querySelector('.s-weight').value,
        }));
    }

    function buildRows(rows) {
        $('m-hint').hidden = rows.length > 0;
        $('m-rows').innerHTML = rows.length
            ? '<div class="grid grid-cols-[2.5rem_1fr_1fr] gap-2 text-xs font-semibold text-gray-500"><span></span><span>Reps</span><span>Weight (kg)</span></div>' +
              rows.map((r, i) => `<div class="set-row grid grid-cols-[2.5rem_1fr_1fr] gap-2 items-center">
                    <span class="wk-setbadge">S${i + 1}</span>
                    <input type="number" min="1" inputmode="numeric" class="wk-input s-reps" placeholder="e.g. 10" aria-label="Reps for set ${i + 1}" value="${esc(r.reps)}">
                    <input type="number" min="0" step="any" inputmode="decimal" class="wk-input s-weight" placeholder="e.g. 60" aria-label="Weight for set ${i + 1}" value="${esc(r.weight)}">
                </div>`).join('')
            : '';
    }

    function showModalError(msg) {
        const el = $('m-error');
        el.textContent = msg;
        el.hidden = !msg;
    }

    function openModal(index, opener) {
        editing = index == null ? null : index;
        lastFocus = opener || document.activeElement;
        const e = editing == null ? { name: '', group: '', rest: '', sets: [] } : exercises[editing];

        $('ex-modal-title').textContent = editing == null ? 'Add Exercise' : 'Edit Exercise';
        $('m-name').value = e.name;
        $('m-group').value = e.group || '';
        $('m-rest').value = e.rest == null ? '' : e.rest;

        let rows = e.sets.map((s) => ({ reps: s.reps, weight: s.weight }));
        if (!rows.length && e.target) {                       // prefill from the split's targets
            rows = Array.from({ length: e.target.sets }, () => ({ reps: e.target.reps, weight: '' }));
        }
        $('m-sets').value = rows.length || '';
        buildRows(rows);
        showModalError('');

        modal.hidden = false;
        document.body.style.overflow = 'hidden';
        (editing == null ? $('m-name') : $('m-sets')).focus();
    }

    function closeModal() {
        modal.hidden = true;
        document.body.style.overflow = '';
        if (lastFocus && lastFocus.focus) lastFocus.focus();
    }

    $('m-sets').addEventListener('input', () => {
        const raw = $('m-sets').value;
        const n = raw === '' ? 0 : Math.max(0, Math.min(20, parseInt(raw, 10) || 0));
        const rows = readRows();
        while (rows.length < n) {
            const last = rows[rows.length - 1] || { reps: '', weight: '' };   // copy previous set for speed
            rows.push({ reps: last.reps, weight: last.weight });
        }
        buildRows(rows.slice(0, n));
    });

    $('m-name').addEventListener('input', () => {
        const hit = library[$('m-name').value.trim().toLowerCase()];
        if (hit && hit.group && !$('m-group').value.trim()) $('m-group').value = hit.group;
    });

    $('m-form').addEventListener('submit', (ev) => {
        ev.preventDefault();
        let name = $('m-name').value.trim();
        if (!name) return showModalError('Enter an exercise name.');

        const rows = readRows();
        const sets = [];
        for (let i = 0; i < rows.length; i++) {
            const reps = parseInt(rows[i].reps, 10);
            if (!(reps >= 1)) return showModalError(`Enter the reps for set ${i + 1}.`);
            const weight = rows[i].weight === '' ? 0 : parseFloat(rows[i].weight);
            if (!(weight >= 0)) return showModalError(`Check the weight for set ${i + 1}.`);
            sets.push({ reps, weight });
        }

        const restRaw = $('m-rest').value;
        const rest = restRaw === '' ? null : Math.max(0, parseInt(restRaw, 10) || 0);

        const known = library[name.toLowerCase()];
        if (known) name = known.name;                                  // keep library spelling
        let group = $('m-group').value.trim();
        if (!group && known) group = known.group;

        const item = { name, group, rest, sets };
        if (editing != null && exercises[editing].target && !sets.length) item.target = exercises[editing].target;
        if (editing == null) exercises.push(item); else exercises[editing] = item;

        if (!known) library[name.toLowerCase()] = { name, group };
        markDirty();
        closeModal();
        render();
    });

    $('add-ex').addEventListener('click', (ev) => openModal(null, ev.currentTarget));
    $('m-cancel').addEventListener('click', closeModal);
    modal.addEventListener('mousedown', (ev) => { if (ev.target === modal) closeModal(); });
    document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && !modal.hidden) closeModal(); });

    // ---------- duration / notes ----------
    $('stat-duration').addEventListener('input', () => {
        const raw = $('stat-duration').value;
        if (raw === '') {
            durationTouched = false;                                   // blank = go back to the estimate
        } else {
            durationTouched = true;
            manualDuration = Math.max(0, Math.min(1440, parseInt(raw, 10) || 0));
        }
        markDirty();
        $('stat-calories').textContent = caloriesFor(currentDuration());
    });
    $('stat-duration').addEventListener('blur', renderStats);

    $('notes').value = S.notes || '';
    $('notes').addEventListener('input', markDirty);

    // ---------- navigation (date / day / days per week) ----------
    const leaveOk = () => !dirty || window.confirm('You have unsaved changes. Leave without saving?');
    const go = (params) => { dirty = false; window.location.search = params.toString(); };

    $('date-input').addEventListener('change', () => {
        const v = $('date-input').value;
        if (!v) return;
        if (!leaveOk()) { $('date-input').value = S.date; return; }
        go(new URLSearchParams({ date: v }));
    });

    $('day-select').addEventListener('change', () => {
        const v = $('day-select').value;
        if (!leaveOk()) { $('day-select').value = S.dayId == null ? 'custom' : String(S.dayId); return; }
        go(new URLSearchParams({ date: S.date, day: v }));
    });

    $('days-select').addEventListener('change', () => {
        const sel = $('days-select');
        const prev = sel.dataset.prev || '';
        if (!sel.value) return;
        const msg = S.hasSplit
            ? `Replace your current split with a suggested ${sel.value}-day split? Your customised days will be lost.`
            : null;
        if ((msg && !window.confirm(msg)) || !leaveOk()) { sel.value = prev; return; }
        dirty = false;
        $('days-form-value').value = sel.value;
        $('days-form').submit();
    });

    // ---------- save ----------
    function showSaveError(msg) {
        const el = $('save-error');
        el.textContent = msg;
        el.classList.toggle('hidden', !msg);
    }

    $('save-btn').addEventListener('click', async () => {
        showSaveError('');
        if (!exercises.some((e) => e.sets.length)) {
            return showSaveError('Add reps and weight to at least one exercise before saving. Use the pencil icon on a row.');
        }
        const btn = $('save-btn');
        const label = btn.textContent;
        btn.disabled = true;
        btn.textContent = 'Saving…';

        const minutes = currentDuration();
        const payload = {
            date: S.date,
            dayId: S.dayId,
            notes: $('notes').value,
            duration: minutes,
            calories: caloriesFor(minutes),
            exercises: exercises.map((e) => ({ name: e.name, group: e.group, rest: e.rest, sets: e.sets })),
        };

        try {
            const res = await fetch(S.saveUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
                body: JSON.stringify(payload),
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.ok) {
                dirty = false;
                window.location.href = data.redirect;
                return;
            }
            showSaveError(data.error || 'Could not save your workout. Try again.');
        } catch (err) {
            showSaveError('Network problem. Check your connection and try again.');
        }
        btn.disabled = false;
        btn.textContent = label;
    });

    window.addEventListener('beforeunload', (ev) => {
        if (dirty) { ev.preventDefault(); ev.returnValue = ''; }
    });

    fillDatalists();
    render();
})();
