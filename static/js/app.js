// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Janne Cadamuro / LabMed Alliance Inc. — see LICENSE and NOTICE
// Minimal JS — mostly handled via inline scripts in templates
// Auto-dismiss flash messages after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    const flashes = document.querySelectorAll('.flash');
    flashes.forEach(function(flash) {
        setTimeout(function() {
            flash.style.transition = 'opacity 0.3s';
            flash.style.opacity = '0';
            setTimeout(function() { flash.remove(); }, 300);
        }, 5000);
    });

    // Convert all UTC datetime elements to user's local timezone
    convertUtcElements();

    // Show user's timezone
    try {
        var tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
        var tzDisplay = tz.replace(/_/g, ' ');

        var tzEl = document.getElementById('user-timezone');
        if (tzEl) tzEl.textContent = tzDisplay;

        var voteTzLabel = document.getElementById('vote-timezone-label');
        if (voteTzLabel) {
            var now = new Date();
            var offsetMin = now.getTimezoneOffset();
            var sign = offsetMin <= 0 ? '+' : '-';
            var absH = String(Math.floor(Math.abs(offsetMin) / 60)).padStart(2, '0');
            var absM = String(Math.abs(offsetMin) % 60).padStart(2, '0');
            var utcStr = 'UTC' + sign + absH + ':' + absM;
            voteTzLabel.textContent = tzDisplay + ' (' + utcStr + ')';
        }
    } catch(e) {}
});

function convertUtcElements() {
    document.querySelectorAll('[data-utc]').forEach(function(el) {
        var utcStr = el.getAttribute('data-utc');
        var format = el.getAttribute('data-utc-format') || 'datetime';
        var addMin = parseInt(el.getAttribute('data-utc-add-minutes') || '0');

        var d = new Date(utcStr);
        if (addMin) d = new Date(d.getTime() + addMin * 60000);
        if (isNaN(d.getTime())) return;

        var dd = String(d.getDate()).padStart(2, '0');
        var mm = String(d.getMonth() + 1).padStart(2, '0');
        var yyyy = d.getFullYear();
        var hh = String(d.getHours()).padStart(2, '0');
        var min = String(d.getMinutes()).padStart(2, '0');

        switch(format) {
            case 'date': el.textContent = dd + '.' + mm + '.' + yyyy; break;
            case 'date-short': el.textContent = dd + '.' + mm; break;
            case 'time': el.textContent = hh + ':' + min; break;
            case 'datetime': el.textContent = dd + '.' + mm + '.' + yyyy + ' ' + hh + ':' + min; break;
        }
    });
}

// Helper: convert a local-time ISO string to UTC ISO string
function localToUtcSlot(localSlot) {
    var d = new Date(localSlot);
    var y = d.getUTCFullYear();
    var mo = String(d.getUTCMonth() + 1).padStart(2, '0');
    var da = String(d.getUTCDate()).padStart(2, '0');
    var h = String(d.getUTCHours()).padStart(2, '0');
    var m = String(d.getUTCMinutes()).padStart(2, '0');
    return y + '-' + mo + '-' + da + 'T' + h + ':' + m;
}

// Helper: convert a UTC ISO string (with Z) to local-time slot key
function utcToLocalSlot(utcStr) {
    var d = new Date(utcStr);
    var y = d.getFullYear();
    var mo = String(d.getMonth() + 1).padStart(2, '0');
    var da = String(d.getDate()).padStart(2, '0');
    var h = String(d.getHours()).padStart(2, '0');
    var m = String(d.getMinutes()).padStart(2, '0');
    return y + '-' + mo + '-' + da + 'T' + h + ':' + m;
}
