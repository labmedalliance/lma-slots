// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Janne Cadamuro / LabMed Alliance Inc. — see LICENSE and NOTICE
// Update icon in the header (admins only, red dot for a new release) and progress view on /admin/update.
document.addEventListener('DOMContentLoaded', function () {
    var badge = document.getElementById('update-badge');
    if (badge) {
        fetch(badge.dataset.url, { credentials: 'same-origin' })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (data && data.available) {
                    badge.title = badge.dataset.label.replace('{version}', data.version);
                    badge.setAttribute('aria-label', badge.title);
                    badge.classList.add('update-available');
                    badge.querySelector('.update-dot').hidden = false;
                }
            })
            .catch(function () { /* offline: no badge */ });
    }

    var box = document.getElementById('update-progress');
    if (!box) return;
    var steps = JSON.parse(box.dataset.steps);
    var stepEl = document.getElementById('update-step');
    var started = Date.now();

    function poll() {
        fetch(box.dataset.progressUrl, { credentials: 'same-origin', cache: 'no-store' })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (!data) return schedule();
                var s = data.status || {};
                if (s.state === 'failed' || (s.state === 'done' && s.restart_needed)) {
                    return window.location.reload();
                }
                if (s.state === 'done' && data.running_version === box.dataset.target) {
                    stepEl.textContent = box.dataset.done;
                    return setTimeout(function () { window.location.reload(); }, 1500);
                }
                stepEl.textContent = steps[s.step] || steps.start;
                schedule();
            })
            .catch(schedule);  // the app is restarting
    }

    function schedule() {
        if (Date.now() - started > 10 * 60 * 1000) {
            stepEl.textContent = box.dataset.manualRestart;
            return;
        }
        setTimeout(poll, 2000);
    }

    schedule();
});
