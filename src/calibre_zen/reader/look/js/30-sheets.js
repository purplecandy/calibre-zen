/*
 * The menu as a header and a footer ribbon over the page, as Apple Books and
 * Readest do it.
 *
 * calibre's menu (read_book/overlay.pyj MainOverlay) is built into an overlay
 * container each time it opens: a top section holding the title and the
 * actions, and a footer. This adds two ribbons to that same container --
 *
 *   header   Contents | title and chapter | Search, Aa, Bookmarks, Highlights, More
 *   footer   << <  [ position ]  > >>
 *
 * -- and while they are there, css/22-sheets.css puts calibre's own top
 * section and footer out of sight (`:has(> .zen-sheet-top)`). calibre empties
 * the container before it shows another panel in it, which takes the ribbons
 * with it, so nothing here outlives the menu. calibre's buttons stay in the
 * page: every button here that stands for one of calibre's actions clicks
 * calibre's button, so the action, its label and its translation are
 * calibre's, and an action calibre adds (Edit book, Copy link, Auto scroll)
 * turns up under More by itself. If this script does not run there are no
 * ribbons, and calibre's menu shows as the card in 20-menu.css.
 *
 * Runs in the application world, beside calibre's viewer.js (sheets.py says
 * why), and reaches calibre through `python_comm`:
 *   _from_python('trigger_shortcut', [name])   the reader's own shortcuts
 *   _from_python('goto_frac', [0..1])          a position in the book
 *   _queue_message({... name: 'zen_message'})  ask Python for the state;
 *                                              the answer is receive() below
 *
 * Clicks inside a sheet stop at the sheet: calibre closes the menu on a click
 * that reaches the container, which is what a click on the page between the
 * sheets still does.
 */
(function () {
    'use strict';
    if (window.zenReader) return;

    var SVGNS = 'http://www.w3.org/2000/svg';
    var XLINK = 'http://www.w3.org/1999/xlink';
    var TOP_SECTION = '.read-book-main-overlay-top-section';
    var ACTION = '.read-book-main-overlay-action-control';
    var FOOTER = '.read-book-main-overlay-footer';
    var RIGHT_SLOT = '.read-book-main-overlay-footer-right-slot';

    // The header's own buttons, by the sprite icon calibre gives the action.
    // Matching the icon, not the label, keeps this right in every language.
    var HEADER = ['search', null, 'bookmark', 'image'];
    var IN_HEADER = {toc: true, search: true, bookmark: true, image: true};

    var state = {labels: {}, schemes: [], current_scheme: '', pos_frac: null, chapter: ''};
    var dragging = false;

    function L(key, fallback) {
        return (state.labels && state.labels[key]) || fallback;
    }

    function calibre(slot, args) {
        if (window.python_comm) window.python_comm._from_python(slot, args || []);
    }

    function shortcut(name) {
        calibre('trigger_shortcut', [name]);
    }

    function tell(want) {
        if (window.python_comm) {
            window.python_comm._queue_message({type: 'signal', name: 'zen_message', args: [{want: want}]});
        }
    }

    function ask() {
        tell('state');
    }

    // calibre does not record the position while its menu is open, and the
    // footer moves the reader with it open: once the page has settled, Python
    // asks where it is and records that (sheets.py sync).
    var syncTimer = 0;
    function moved() {
        clearTimeout(syncTimer);
        syncTimer = setTimeout(function () { tell('sync'); }, 350);
    }

    function navigate(name) {
        shortcut(name);
        moved();
    }

    function el(tag, cls, text) {
        var e = document.createElement(tag);
        if (cls) e.className = cls;
        if (text) e.textContent = text;
        return e;
    }

    function icon(name) {
        var svg = document.createElementNS(SVGNS, 'svg');
        svg.setAttribute('class', 'zen-icon');
        svg.setAttribute('aria-hidden', 'true');
        var use = document.createElementNS(SVGNS, 'use');
        use.setAttributeNS(XLINK, 'xlink:href', '#icon-' + name);
        svg.appendChild(use);
        return svg;
    }

    function stop(ev) {
        ev.stopPropagation();
    }

    function button(cls, iconName, label, onclick) {
        var b = el('button', 'zen-sheet-button ' + (cls || ''));
        b.type = 'button';
        if (iconName) b.appendChild(typeof iconName === 'string' ? icon(iconName) : iconName);
        if (label) {
            b.title = label;
            b.setAttribute('aria-label', label);
        }
        b.addEventListener('click', function (ev) {
            ev.stopPropagation();
            onclick(ev, b);
        });
        return b;
    }

    // calibre's actions {{{

    function iconOf(btn) {
        var use = btn.querySelector('use');
        if (!use) return btn.querySelector('.read-book-main-overlay-text-icon') ? ':text' : '';
        var ref = use.getAttribute('href') || use.getAttributeNS(XLINK, 'href') || use.getAttribute('xlink:href') || '';
        return ref.replace(/^#icon-/, '');
    }

    function labelOf(btn) {
        var parts = [];
        for (var i = 0; i < btn.childNodes.length; i++) {
            if (btn.childNodes[i].nodeType === 3) parts.push(btn.childNodes[i].textContent);
        }
        return parts.join('').trim() || btn.title || '';
    }

    function actions(container) {
        var groups = [];
        var lists = container.querySelectorAll(TOP_SECTION + ' ul');
        for (var i = 0; i < lists.length; i++) {
            var items = [];
            var buttons = lists[i].querySelectorAll(ACTION);
            for (var j = 0; j < buttons.length; j++) {
                items.push({button: buttons[j], icon: iconOf(buttons[j]), label: labelOf(buttons[j])});
            }
            if (items.length) groups.push(items);
        }
        return groups;
    }

    function find(groups, name) {
        // Highlights shares calibre's `image` icon with View image; it is the
        // one that sits beside Bookmarks.
        for (var i = 0; i < groups.length; i++) {
            var hasBookmark = groups[i].some(function (a) { return a.icon === 'bookmark'; });
            for (var j = 0; j < groups[i].length; j++) {
                var a = groups[i][j];
                if (a.icon !== name) continue;
                if (name === 'image' && !hasBookmark) continue;
                return a;
            }
        }
        return null;
    }

    function proxy(action, cls) {
        if (!action) return null;
        var b = button(cls, action.icon && action.icon.charAt(0) !== ':' ? action.icon : null, action.label, function () {
            closePopover();
            action.button.click();
        });
        return b;
    }

    // }}}

    // Popovers {{{

    var openPopover = null;

    function closePopover() {
        if (!openPopover) return;
        openPopover.anchor.classList.remove('zen-open');
        openPopover.node.remove();
        openPopover = null;
    }

    function popover(container, anchor, build, cls, ev) {
        var wasOpen = openPopover && openPopover.anchor === anchor;
        closePopover();
        if (wasOpen) return;
        var node = el('div', 'zen-popover ' + (cls || ''));
        node.setAttribute('role', 'dialog');
        node.addEventListener('click', stop);
        build(node);
        container.appendChild(node);
        var a = anchor.getBoundingClientRect();
        var width = node.offsetWidth;
        var margin = 8;
        var left = Math.min(Math.max(margin, a.left + a.width / 2 - width / 2), window.innerWidth - width - margin);
        node.style.left = left + 'px';
        node.style.top = (a.bottom + 10) + 'px';
        node.style.setProperty('--zen-arrow-x', (a.left + a.width / 2 - left) + 'px');
        anchor.classList.add('zen-open');
        openPopover = {node: node, anchor: anchor};
        // Into the popover only when it was opened from the keyboard (a
        // click made by Enter or Space has no click count); a mouse user's
        // first item is not where they are about to look.
        if (ev && ev.detail === 0) {
            var first = node.querySelector('button');
            if (first) first.focus({preventScroll: true});
        }
    }

    function buildMore(groups, footerHelp) {
        return function (node) {
            var shown = 0;
            groups.forEach(function (group) {
                var rows = group.filter(function (a) {
                    return !(IN_HEADER[a.icon] && find(groups, a.icon) === a) && a.icon !== ':text';
                });
                if (!rows.length) return;
                if (shown) node.appendChild(el('div', 'zen-popover-separator'));
                rows.forEach(function (a) {
                    var row = button('zen-menu-row', a.icon && a.icon.charAt(0) !== ':' ? a.icon : null, null, function () {
                        closePopover();
                        a.button.click();
                    });
                    row.appendChild(el('span', 'zen-menu-label', a.label));
                    node.appendChild(row);
                    shown++;
                });
            });
            if (footerHelp) {
                node.appendChild(el('div', 'zen-popover-separator'));
                var help = button('zen-menu-row', 'help', null, function () {
                    closePopover();
                    footerHelp.click();
                });
                help.appendChild(el('span', 'zen-menu-label', labelOf(footerHelp)));
                node.appendChild(help);
            }
        };
    }

    function buildAppearance(groups) {
        return function (node) {
            node.appendChild(el('div', 'zen-popover-title', L('appearance', 'Themes & Settings')));

            var sizes = el('div', 'zen-segmented');
            var smaller = button('zen-segment zen-size-smaller', null, L('smaller', 'Smaller text'), function () { shortcut('decrease_font_size'); });
            smaller.appendChild(el('span', '', 'A'));
            var larger = button('zen-segment zen-size-larger', null, L('larger', 'Larger text'), function () { shortcut('increase_font_size'); });
            larger.appendChild(el('span', '', 'A'));
            sizes.appendChild(smaller);
            sizes.appendChild(el('span', 'zen-segment-divider'));
            sizes.appendChild(larger);
            node.appendChild(sizes);

            var grid = el('div', 'zen-themes');
            (state.schemes || []).forEach(function (s) {
                var tile = button('zen-theme' + (s.key === state.current_scheme ? ' zen-current' : ''), null, s.name, function () {
                    state.current_scheme = s.key;
                    var tiles = grid.querySelectorAll('.zen-theme');
                    for (var i = 0; i < tiles.length; i++) tiles[i].classList.toggle('zen-current', tiles[i] === tile);
                    shortcut('switch_color_scheme:' + s.key);
                });
                tile.style.setProperty('--zen-theme-bg', s.bg);
                tile.style.setProperty('--zen-theme-fg', s.fg);
                tile.setAttribute('aria-pressed', s.key === state.current_scheme ? 'true' : 'false');
                tile.appendChild(el('span', 'zen-theme-sample', 'Aa'));
                tile.appendChild(el('span', 'zen-theme-name', s.name));
                grid.appendChild(tile);
            });
            node.appendChild(grid);

            var prefs = find(groups, 'cogs');
            if (prefs) {
                var more = button('zen-wide-button', 'cogs', null, function () {
                    closePopover();
                    prefs.button.click();
                });
                more.appendChild(el('span', '', L('customize', 'More settings')));
                node.appendChild(more);
            }
        };
    }

    // }}}

    // The footer's position {{{

    function fracFromSlot(container) {
        var slot = container.querySelector(RIGHT_SLOT);
        var m = slot && /(\d{1,3})\s*%/.exec(slot.textContent);
        return m ? Math.min(100, parseInt(m[1], 10)) / 100 : null;
    }

    function showPosition(sheet, frac) {
        if (!sheet || frac === null || frac === undefined || isNaN(frac)) return;
        frac = Math.max(0, Math.min(1, frac));
        sheet.style.setProperty('--zen-position', (frac * 100).toFixed(2) + '%');
        var label = sheet.querySelector('.zen-position-label');
        if (label) label.textContent = Math.round(frac * 100) + '%';
        var track = sheet.querySelector('.zen-track');
        if (track) track.setAttribute('aria-valuenow', String(Math.round(frac * 100)));
    }

    function buildTrack(sheet) {
        var track = el('div', 'zen-track');
        track.setAttribute('role', 'slider');
        track.setAttribute('aria-valuemin', '0');
        track.setAttribute('aria-valuemax', '100');
        track.setAttribute('aria-label', L('position', 'Position in the book'));
        track.tabIndex = 0;
        track.appendChild(el('div', 'zen-track-fill'));
        track.appendChild(el('div', 'zen-track-thumb'));

        function fracAt(ev) {
            var r = track.getBoundingClientRect();
            return Math.max(0, Math.min(1, (ev.clientX - r.left) / Math.max(1, r.width)));
        }
        track.addEventListener('click', stop);
        track.addEventListener('pointerdown', function (ev) {
            ev.stopPropagation();
            dragging = true;
            track.setPointerCapture(ev.pointerId);
            sheet.classList.add('zen-dragging');
            showPosition(sheet, fracAt(ev));
        });
        track.addEventListener('pointermove', function (ev) {
            if (dragging) showPosition(sheet, fracAt(ev));
        });
        track.addEventListener('pointerup', function (ev) {
            if (!dragging) return;
            dragging = false;
            sheet.classList.remove('zen-dragging');
            var f = fracAt(ev);
            showPosition(sheet, f);
            calibre('goto_frac', [f]);
            moved();
        });
        track.addEventListener('pointercancel', function () {
            dragging = false;
            sheet.classList.remove('zen-dragging');
        });
        track.addEventListener('keydown', function (ev) {
            var step = {ArrowLeft: -0.01, ArrowRight: 0.01, PageDown: 0.1, PageUp: -0.1}[ev.key];
            if (step === undefined) return;
            ev.preventDefault();
            ev.stopPropagation();
            var f = Math.max(0, Math.min(1, (state.pos_frac || 0) + step));
            state.pos_frac = f;
            showPosition(sheet, f);
            calibre('goto_frac', [f]);
            moved();
        });
        return track;
    }

    // }}}

    function hasRibbons(container) {
        return !!container.querySelector(':scope > .zen-sheet-top');
    }

    function build(container) {
        if (hasRibbons(container)) return;
        var groups = actions(container);
        if (!groups.length) return;

        var titleEl = container.querySelector('.read-book-main-overlay-title');
        var footerButtons = container.querySelectorAll(FOOTER + ' .read-book-main-overlay-footer-action');
        var footerHelp = footerButtons.length > 1 ? footerButtons[1] : null;

        // Header {{{
        var top = el('div', 'zen-sheet zen-sheet-top');
        top.setAttribute('role', 'toolbar');
        top.addEventListener('click', stop);

        var left = el('div', 'zen-sheet-cluster zen-sheet-left');
        var toc = proxy(find(groups, 'toc'));
        if (toc) left.appendChild(toc);

        var middle = el('div', 'zen-sheet-title');
        middle.appendChild(el('div', 'zen-sheet-book', titleEl ? titleEl.textContent : document.title));
        middle.appendChild(el('div', 'zen-sheet-chapter', state.chapter || ''));

        var right = el('div', 'zen-sheet-cluster zen-sheet-right');
        HEADER.forEach(function (name) {
            if (name === null) {
                right.appendChild(button('zen-appearance', 'zen-letter-case', L('appearance', 'Themes & Settings'), function (ev, b) {
                    popover(container, b, buildAppearance(groups), 'zen-popover-appearance', ev);
                }));
                return;
            }
            var b = proxy(find(groups, name));
            if (b) right.appendChild(b);
        });
        right.appendChild(button('zen-more', 'zen-dots', L('more', 'More'), function (ev, b) {
            popover(container, b, buildMore(groups, footerHelp), 'zen-popover-menu', ev);
        }));

        top.appendChild(left);
        top.appendChild(middle);
        top.appendChild(right);
        // }}}

        // Footer {{{
        var bottom = el('div', 'zen-sheet zen-sheet-bottom');
        bottom.addEventListener('click', stop);
        bottom.appendChild(button('zen-nav', 'zen-chevrons-left', L('previous_chapter', 'Previous chapter'), function () { navigate('previous_section'); }));
        bottom.appendChild(button('zen-nav', 'zen-chevron-left', L('previous_page', 'Previous page'), function () { navigate('pageup'); }));
        var position = el('div', 'zen-position');
        position.appendChild(buildTrack(bottom));
        position.appendChild(el('span', 'zen-position-label', ''));
        bottom.appendChild(position);
        bottom.appendChild(button('zen-nav', 'zen-chevron-right', L('next_page', 'Next page'), function () { navigate('pagedown'); }));
        bottom.appendChild(button('zen-nav', 'zen-chevrons-right', L('next_chapter', 'Next chapter'), function () { navigate('next_section'); }));
        // }}}

        container.appendChild(top);
        container.appendChild(bottom);
        showPosition(bottom, state.pos_frac !== null ? state.pos_frac : fracFromSlot(container));
        ask();
    }

    function refresh() {
        var chapters = document.querySelectorAll('.zen-sheet-chapter');
        for (var i = 0; i < chapters.length; i++) chapters[i].textContent = state.chapter || '';
        if (dragging) return;
        var bottoms = document.querySelectorAll('.zen-sheet-bottom');
        for (var j = 0; j < bottoms.length; j++) showPosition(bottoms[j], state.pos_frac);
    }

    function scan() {
        var sections = document.querySelectorAll(TOP_SECTION);
        for (var i = 0; i < sections.length; i++) {
            var c = sections[i].parentElement;
            if (c && !hasRibbons(c)) {
                try {
                    build(c);
                } catch (e) {
                    // calibre's own menu stays, unhidden, as it was drawn.
                    var partial = c.querySelectorAll(':scope > .zen-sheet, :scope > .zen-popover');
                    for (var k = 0; k < partial.length; k++) partial[k].remove();
                    console.error('zen sheets:', e);
                }
            }
        }
        if (openPopover && !document.body.contains(openPopover.anchor)) closePopover();
    }

    var pending = false;
    new MutationObserver(function () {
        if (pending) return;
        pending = true;
        requestAnimationFrame(function () {
            pending = false;
            scan();
        });
    }).observe(document.documentElement, {childList: true, subtree: true});

    document.addEventListener('keydown', function (ev) {
        if (ev.key === 'Escape' && openPopover) {
            ev.stopPropagation();
            ev.preventDefault();
            closePopover();
        }
    }, true);

    window.zenReader = {
        receive: function (data) {
            if (!data) return;
            for (var k in data) {
                if (Object.prototype.hasOwnProperty.call(data, k)) state[k] = data[k];
            }
            refresh();
        },
        state: function () { return state; }
    };
    scan();
})();
