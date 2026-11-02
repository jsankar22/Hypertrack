// Split day editor: rename a day and manage its planned exercises.
(function () {
    'use strict';

    const stateEl = document.getElementById('split-state');
    if (!stateEl) return;
    const S = JSON.parse(stateEl.textContent);

    const $ = (id) => document.getElementById(id);
    const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, (c) => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));
    const csrf = () => (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '';

    let rows = S.exercises.map((e) => ({ exercise: e.exercise, sets: e.sets, reps: e.reps }));
    if (!rows.length) rows.push({ exercise: '', sets: 3, reps: 10 });

    $('sd-label').value = S.label;
    $('sd-focus').value = S.muscleFocus;
    $('sd-lib').innerHTML = S.library.map((l) => `<option value="${esc(l.name)}"></option>`).join('');

    const ARROW_UP = '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M5 15l7-7 7 7"/></svg>';
    const ARROW_DOWN = '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>';
    const CLOSE = '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>';

    function render(focusIndex) {
        $('sd-rows').innerHTML = rows.map((r, i) => `
            <div class="sd-row grid grid-cols-12 gap-2 items-center" data-i="${i}">
                <input class="wk-input col-span-12 sm:col-span-6 f-name" list="sd-lib" maxlength="50" placeholder="Exercise name" aria-label="Exercise ${i + 1} name" value="${esc(r.exercise)}" autocomplete="off">
                <input class="wk-input col-span-3 sm:col-span-2 f-sets" type="number" min="1" max="50" inputmode="numeric" placeholder="Sets" aria-label="Sets" value="${esc(r.sets)}">
                <input class="wk-input col-span-3 sm:col-span-2 f-reps" type="number" min="1" max="1000" inputmode="numeric" placeholder="Reps" aria-label="Reps" value="${esc(r.reps)}">
                <div class="col-span-6 sm:col-span-2 flex justify-end gap-1">
                    <button type="button" class="wk-icon-btn" data-act="up" aria-label="Move up" ${i === 0 ? 'disabled style="opacity:.4"' : ''}>${ARROW_UP}</button>
                    <button type="button" class="wk-icon-btn" data-act="down" aria-label="Move down" ${i === rows.length - 1 ? 'disabled style="opacity:.4"' : ''}>${ARROW_DOWN}</button>
                    <button type="button" class="wk-icon-btn is-danger" data-act="del" aria-label="Remove exercise">${CLOSE}</button>
                </div>
            </div>`).join('');
        if (focusIndex != null) {
            const el = document.querySelectorAll('.f-name')[focusIndex];
            if (el) el.focus();
        }
    }

    function syncFromDom() {
        document.querySelectorAll('.sd-row').forEach((row, i) => {
            rows[i] = {
                exercise: row.querySelector('.f-name').value,
                sets: row.querySelector('.f-sets').value,
                reps: row.querySelector('.f-reps').value,
            };
        });
    }

    $('sd-rows').addEventListener('click', (ev) => {
        const btn = ev.target.closest('button[data-act]');
        if (!btn) return;
        syncFromDom();
        const i = +btn.closest('.sd-row').dataset.i;
        if (btn.dataset.act === 'del') rows.splice(i, 1);
        if (btn.dataset.act === 'up' && i > 0) [rows[i - 1], rows[i]] = [rows[i], rows[i - 1]];
        if (btn.dataset.act === 'down' && i < rows.length - 1) [rows[i + 1], rows[i]] = [rows[i], rows[i + 1]];
        render();
    });

    $('sd-add').addEventListener('click', () => {
        syncFromDom();
        const last = rows[rows.length - 1];
        rows.push({ exercise: '', sets: last ? last.sets : 3, reps: last ? last.reps : 10 });
        render(rows.length - 1);
    });

    function showError(msg) {
        const el = $('sd-error');
        el.textContent = msg;
        el.classList.toggle('hidden', !msg);
    }

    $('split-form').addEventListener('submit', async (ev) => {
        ev.preventDefault();
        showError('');
        syncFromDom();
        const label = $('sd-label').value.trim();
        if (!label) { $('sd-label').focus(); return showError('Give this day a name.'); }

        const exercises = rows
            .filter((r) => r.exercise.trim())
            .map((r) => ({ exercise: r.exercise.trim(), sets: parseInt(r.sets, 10), reps: parseInt(r.reps, 10) }));
        const bad = exercises.find((r) => !(r.sets >= 1) || !(r.reps >= 1));
        if (bad) return showError(`Enter sets and reps for ${bad.exercise}.`);

        const btn = $('sd-save');
        btn.disabled = true;
        try {
            const res = await fetch(S.saveUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
                body: JSON.stringify({ id: S.id, label, muscleFocus: $('sd-focus').value.trim(), exercises }),
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.ok) { window.location.href = data.redirect; return; }
            showError(data.error || 'Could not save this day. Try again.');
        } catch (err) {
            showError('Network problem. Check your connection and try again.');
        }
        btn.disabled = false;
    });

    render();
})();
