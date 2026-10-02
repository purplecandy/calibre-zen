/*
 * The menu's progress bar (css/20-menu.css) is drawn from --zen-progress, a
 * length. calibre writes the reading position into the footer's right slot as
 * text ("26%"), which CSS cannot read as a number, so this copies it across
 * whenever the slot changes. Nothing else is touched: without this script the
 * slot is just the percentage, as calibre draws it.
 */
(function () {
    'use strict';
    var SLOT = '.read-book-main-overlay-footer-right-slot';
    var PERCENT = /^(\d{1,3})\s*%$/;
    function sync() {
        var slots = document.querySelectorAll(SLOT);
        for (var i = 0; i < slots.length; i++) {
            var m = PERCENT.exec(slots[i].textContent.trim());
            if (m) slots[i].style.setProperty('--zen-progress', Math.min(100, parseInt(m[1], 10)) + '%');
            else slots[i].style.removeProperty('--zen-progress');
        }
    }
    var pending = false;
    new MutationObserver(function () {
        if (pending) return;
        pending = true;
        requestAnimationFrame(function () { pending = false; sync(); });
    }).observe(document.documentElement, {childList: true, subtree: true, characterData: true});
})();
