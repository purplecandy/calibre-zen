#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The zen look: a flat, low-contrast restyling of calibre's Qt Widgets chrome.

calibre draws its UI with Qt Widgets through the CalibreStyle proxy over
Fusion. That gives correct, dense, thoroughly dated chrome: boxed tabs, 1px
sunken frames everywhere, chunky scrollbars, hard-edged menus. None of that is
Qt's fault -- Fusion is simply styleable and nobody has restyled it here.

This module is that restyling. It is only colors, radii and spacing: one global
stylesheet plus a pair of palettes, applied from PaletteManager. No widget is
subclassed and no layout is touched, so nothing here can change behaviour --
the worst a mistake can do is look wrong.

Set CALIBRE_ZEN_STYLE=0 to get stock calibre back, for comparing the two.
"""

import hashlib
import os

from qt.core import QColor, QPalette

# Palette {{{

# One accent for every selection, focus ring and active state, in both themes.
# calibre's stock palettes use a blue highlight and an unrelated green "accent";
# the green appears in exactly one place (fts/cards.py), so folding the two
# together costs nothing and stops the UI reading as two-toned. Links are the
# one thing that does not use it: on a dark ground this blue is too dark to
# read as text, so the dark palette sets a lighter Link color.
ACCENT = QColor(0x35, 0x74, 0xF0)


def mix(a: QColor, b: QColor, f: float) -> QColor:
    "Blend f of b into a, in sRGB. Good enough for chrome, not for images."
    g = 1.0 - f
    return QColor(
        round(a.red() * g + b.red() * f),
        round(a.green() * g + b.green() * f),
        round(a.blue() * g + b.blue() * f),
    )


def zen_dark_palette() -> QPalette:
    p = QPalette()
    window = QColor(0x24, 0x26, 0x2A)
    base = QColor(0x1A, 0x1C, 0x1F)
    text = QColor(0xDF, 0xE1, 0xE5)
    disabled = QColor(0x78, 0x7C, 0x84)

    p.setColor(QPalette.ColorRole.Window, window)
    p.setColor(QPalette.ColorRole.WindowText, text)
    p.setColor(QPalette.ColorRole.Base, base)
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(0x1F, 0x21, 0x24))
    p.setColor(QPalette.ColorRole.Text, text)
    p.setColor(QPalette.ColorRole.Button, QColor(0x2C, 0x2F, 0x34))
    p.setColor(QPalette.ColorRole.ButtonText, text)
    p.setColor(QPalette.ColorRole.PlaceholderText, disabled)
    p.setColor(QPalette.ColorRole.BrightText, QColor(0xFF, 0x6B, 0x6B))
    # A dark tooltip on a dark UI. The stock pale yellow is the single most
    # dated thing on screen and it is not even legible against dark chrome.
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(0x32, 0x35, 0x3A))
    p.setColor(QPalette.ColorRole.ToolTipText, text)
    p.setColor(QPalette.ColorRole.Link, QColor(0x6E, 0xA8, 0xFF))
    p.setColor(QPalette.ColorRole.LinkVisited, QColor(0xB9, 0x8E, 0xFF))
    p.setColor(QPalette.ColorRole.Highlight, ACCENT)
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(0xFF, 0xFF, 0xFF))
    p.setColor(QPalette.ColorRole.Accent, ACCENT)
    # Fusion derives frame and separator colors from these three; left at their
    # defaults they are far lighter than this window color and every sunken
    # frame glows.
    p.setColor(QPalette.ColorRole.Light, QColor(0x3A, 0x3E, 0x44))
    p.setColor(QPalette.ColorRole.Midlight, QColor(0x32, 0x35, 0x3A))
    p.setColor(QPalette.ColorRole.Mid, QColor(0x3A, 0x3E, 0x44))
    p.setColor(QPalette.ColorRole.Dark, QColor(0x16, 0x18, 0x1A))
    p.setColor(QPalette.ColorRole.Shadow, QColor(0x0E, 0x0F, 0x11))

    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.HighlightedText,
    ):
        p.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    return p


def zen_light_palette() -> QPalette:
    p = QPalette()
    window = QColor(0xF4, 0xF5, 0xF7)
    base = QColor(0xFF, 0xFF, 0xFF)
    text = QColor(0x1F, 0x23, 0x29)
    disabled = QColor(0x9A, 0x9F, 0xA8)

    p.setColor(QPalette.ColorRole.Window, window)
    p.setColor(QPalette.ColorRole.WindowText, text)
    p.setColor(QPalette.ColorRole.Base, base)
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(0xF8, 0xF9, 0xFB))
    p.setColor(QPalette.ColorRole.Text, text)
    p.setColor(QPalette.ColorRole.Button, base)
    p.setColor(QPalette.ColorRole.ButtonText, text)
    p.setColor(QPalette.ColorRole.PlaceholderText, disabled)
    p.setColor(QPalette.ColorRole.BrightText, QColor(0xD1, 0x24, 0x2F))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(0x2B, 0x2E, 0x33))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor(0xF2, 0xF3, 0xF5))
    p.setColor(QPalette.ColorRole.Link, ACCENT)
    p.setColor(QPalette.ColorRole.LinkVisited, QColor(0x7B, 0x4D, 0xD8))
    p.setColor(QPalette.ColorRole.Highlight, ACCENT)
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(0xFF, 0xFF, 0xFF))
    p.setColor(QPalette.ColorRole.Accent, ACCENT)
    p.setColor(QPalette.ColorRole.Light, QColor(0xFF, 0xFF, 0xFF))
    p.setColor(QPalette.ColorRole.Midlight, QColor(0xEC, 0xEE, 0xF1))
    p.setColor(QPalette.ColorRole.Mid, QColor(0xD8, 0xDB, 0xE0))
    p.setColor(QPalette.ColorRole.Dark, QColor(0xB4, 0xB9, 0xC1))
    p.setColor(QPalette.ColorRole.Shadow, QColor(0x8A, 0x90, 0x99))

    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.HighlightedText,
    ):
        p.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    return p
# }}}


def enabled() -> bool:
    return os.environ.get('CALIBRE_ZEN_STYLE', '1') not in ('0', 'false', 'no', 'off')


class Tokens:

    """
    Chrome colors derived from whatever palette is actually in use.

    Deriving rather than hard-coding is what keeps this compatible with the
    custom palettes calibre lets users define in Preferences: pick a sepia
    theme and the borders, hovers and scrollbars follow it instead of staying
    stubbornly blue-grey.
    """

    def __init__(self, pal: QPalette, is_dark: bool):
        window = pal.color(QPalette.ColorRole.Window)
        base = pal.color(QPalette.ColorRole.Base)
        text = pal.color(QPalette.ColorRole.WindowText)
        accent = pal.color(QPalette.ColorRole.Highlight)

        self.window = window.name()
        self.accent = accent.name()
        self.accent_text = pal.color(QPalette.ColorRole.HighlightedText).name()
        self.alt = pal.color(QPalette.ColorRole.AlternateBase).name()
        self.button = pal.color(QPalette.ColorRole.Button).name()

        # Borders as a blend toward the text color rather than a fixed grey, so
        # they stay a hairline against any window color instead of turning into
        # a hard line on light themes and a glow on dark ones.
        self.border = mix(window, text, 0.16 if is_dark else 0.14).name()
        self.border_weak = mix(window, text, 0.09 if is_dark else 0.07).name()
        self.border_strong = mix(window, text, 0.30 if is_dark else 0.26).name()
        self.muted = mix(window, text, 0.55).name()

        # Hover and pressed as translucent accent: one color that works over
        # the window, over base, and over alternating rows without computing a
        # variant for each.
        rgb = f'{accent.red()}, {accent.green()}, {accent.blue()}'
        self.hover = f'rgba({rgb}, {45 if is_dark else 28})'
        self.pressed = f'rgba({rgb}, {75 if is_dark else 52})'
        self.selected_soft = f'rgba({rgb}, {95 if is_dark else 62})'

        self.track = mix(window, text, 0.12).name()
        self.scroll = mix(window, text, 0.26).name()
        self.scroll_hover = mix(window, text, 0.42).name()
        self.tooltip_bg = pal.color(QPalette.ColorRole.ToolTipBase).name()
        self.tooltip_fg = pal.color(QPalette.ColorRole.ToolTipText).name()
        button = pal.color(QPalette.ColorRole.Button)
        self.button_hover = mix(button, text, 0.10).name()
        self.button_pressed = mix(button, text, 0.18).name()
        self.menu_bg = mix(window, base, 0.5 if is_dark else 1.0).name()


# Check and radio marks {{{

# Qt stops drawing a subcontrol natively the moment you style it, so a rounded
# accent-filled checkbox has to supply its own tick. QSS url() wants a real
# file, so the marks are written to the cache directory once per color and
# reused. They are a few hundred bytes each.

CHECK_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
    '<path d="M3.5 8.4 L6.4 11.3 L12.5 5" fill="none" stroke="{color}"'
    ' stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/></svg>'
)
DASH_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
    '<path d="M4.2 8 L11.8 8" fill="none" stroke="{color}"'
    ' stroke-width="2.1" stroke-linecap="round"/></svg>'
)
DOT_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
    '<circle cx="8" cy="8" r="3.1" fill="{color}"/></svg>'
)


def mark_url(name: str, template: str, color: str) -> str:
    "Path to the mark, written on demand. Falls back to no image if unwritable."
    from calibre.constants import cache_dir

    data = template.format(color=color)
    d = os.path.join(cache_dir(), 'zen-style')
    digest = hashlib.sha256(data.encode('utf-8')).hexdigest()[:12]
    path = os.path.join(d, f'{name}-{digest}.svg')
    try:
        if not os.path.exists(path):
            os.makedirs(d, exist_ok=True)
            with open(path, 'w') as f:
                f.write(data)
    except OSError:
        return 'none'
    # QSS url() takes forward slashes on every platform.
    return f'url("{path.replace(os.sep, "/")}")'

# }}}


def stylesheet(pal: QPalette, is_dark: bool) -> str:
    t = Tokens(pal, is_dark)
    check = mark_url('check', CHECK_SVG, t.accent_text)
    dash = mark_url('dash', DASH_SVG, t.accent_text)
    dot = mark_url('dot', DOT_SVG, t.accent_text)
    return f'''
/* Tooltips {{{{{{ */
QToolTip {{
    background-color: {t.tooltip_bg};
    color: {t.tooltip_fg};
    border: 1px solid {t.border_strong};
    border-radius: 6px;
    padding: 5px 8px;
}}
/* }}}}}} */

/* Buttons {{{{{{ */
QPushButton {{
    background-color: {t.button};
    color: palette(button-text);
    border: 1px solid {t.border_strong};
    border-radius: 6px;
    padding: 4px 14px;
    min-height: 20px;
}}

QPushButton:hover {{ background-color: {t.button_hover}; }}
QPushButton:pressed {{ background-color: {t.button_pressed}; }}
QPushButton:focus {{ border-color: {t.accent}; }}
QPushButton:default {{ border-color: {t.accent}; color: {t.accent}; }}
QPushButton:disabled {{ background-color: transparent; border-color: {t.border_weak}; color: {t.muted}; }}
QPushButton:flat {{ background-color: transparent; border-color: transparent; }}
QPushButton:flat:hover {{ background-color: {t.hover}; }}
QPushButton::menu-indicator {{ subcontrol-origin: padding; subcontrol-position: center right; right: 6px; }}

/* Toolbar buttons get no chrome at rest -- a row of framed boxes is most of
   what makes the stock toolbar read as a 2005 UI. */
QToolButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 3px;
}}

QToolButton:hover {{ background-color: {t.hover}; }}
QToolButton:pressed {{ background-color: {t.pressed}; }}
QToolButton:checked {{ background-color: {t.pressed}; border-color: {t.border}; }}
/* DelayedPopup is 0, MenuButtonPopup 1, InstantPopup 2. Only the last two
   draw an arrow, and only they need room reserved for it. */
QToolButton[popupMode="1"] {{ padding-right: 18px; }}
QToolButton[popupMode="2"] {{ padding-right: 16px; }}
QToolButton::menu-button {{ border: none; border-top-right-radius: 6px; border-bottom-right-radius: 6px; width: 15px; }}
QToolButton::menu-button:hover {{ background-color: {t.pressed}; }}
QToolButton::menu-arrow {{ subcontrol-origin: padding; subcontrol-position: center right; right: 3px; }}
/* }}}}}} */

/* Check marks and radios. QGroupBox and the item views share the rules so a
   checkbox looks the same in a dialog, a list and a checkable group box. */
QCheckBox::indicator, QGroupBox::indicator, QAbstractItemView::indicator, QMenu::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {t.border_strong};
    border-radius: 4px;
    background-color: palette(base);
}}

QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {t.border_strong};
    border-radius: 8px;
    background-color: palette(base);
}}

QCheckBox::indicator:hover, QRadioButton::indicator:hover,
QGroupBox::indicator:hover, QMenu::indicator:hover {{ border-color: {t.accent}; }}

QCheckBox::indicator:checked, QGroupBox::indicator:checked,
QAbstractItemView::indicator:checked, QMenu::indicator:checked {{
    background-color: {t.accent}; border-color: {t.accent}; image: {check};
}}
QCheckBox::indicator:indeterminate, QAbstractItemView::indicator:indeterminate,
QMenu::indicator:indeterminate {{
    background-color: {t.accent}; border-color: {t.accent}; image: {dash};
}}
QRadioButton::indicator:checked, QMenu::indicator:exclusive:checked {{
    background-color: {t.accent}; border-color: {t.accent}; image: {dot};
}}
QMenu::indicator:exclusive {{ border-radius: 8px; }}

QCheckBox::indicator:disabled, QRadioButton::indicator:disabled,
QGroupBox::indicator:disabled {{ border-color: {t.border_weak}; background-color: transparent; }}
QCheckBox::indicator:checked:disabled, QRadioButton::indicator:checked:disabled {{
    background-color: {t.muted}; border-color: {t.muted};
}}
QCheckBox:disabled, QRadioButton:disabled {{ color: {t.muted}; }}
/* }}}}}} */

/* Text entry {{{{{{ */
QLineEdit, QPlainTextEdit, QTextEdit, QTextBrowser, QSpinBox, QDoubleSpinBox,
QDateEdit, QDateTimeEdit, QTimeEdit, QComboBox, QKeySequenceEdit {{
    background-color: palette(base);
    border: 1px solid {t.border_strong};
    border-radius: 6px;
    padding: 3px 8px;
    min-height: 20px;
    selection-background-color: {t.accent};
    selection-color: {t.accent_text};
}}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QDateEdit:focus, QDateTimeEdit:focus, QTimeEdit:focus, QComboBox:focus, QKeySequenceEdit:focus {{
    border-color: {t.accent};
}}

QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled, QSpinBox:disabled,
QDoubleSpinBox:disabled, QComboBox:disabled {{
    background-color: transparent;
    border-color: {t.border_weak};
    color: {t.muted};
}}

QLineEdit:read-only {{ background-color: {t.alt}; }}

QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background-color: {t.menu_bg};
    border: 1px solid {t.border};
    border-radius: 6px;
    padding: 3px;
    selection-background-color: {t.accent};
    selection-color: {t.accent_text};
}}

/* The spin buttons are deliberately left to CalibreStyle. Styling the button
   subcontrol stops Qt drawing the native subcontrol *including its arrow*, and
   a spin box whose arrows are invisible is worse than one that is square. */
/* }}}}}} */

/* Scrollbars: thin, no arrows, handle only on the track it needs {{{{{{ */
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 0; border: none; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 0; border: none; }}

QScrollBar::handle:vertical {{
    background: {t.scroll}; border-radius: 3px; min-height: 32px; margin: 2px 3px;
}}
QScrollBar::handle:horizontal {{
    background: {t.scroll}; border-radius: 3px; min-width: 32px; margin: 3px 2px;
}}
QScrollBar::handle:hover {{ background: {t.scroll_hover}; }}

QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0; height: 0; border: none; background: transparent;
}}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar::up-arrow, QScrollBar::down-arrow,
QScrollBar::left-arrow, QScrollBar::right-arrow {{ background: transparent; }}
/* }}}}}} */

/* Menus {{{{{{ */
QMenu {{
    background-color: {t.menu_bg};
    border: 1px solid {t.border_strong};
    border-radius: 8px;
    padding: 5px;
}}

QMenu::item {{
    background-color: transparent;
    border-radius: 5px;
    padding: 5px 28px 5px 26px;
    margin: 1px 2px;
}}
QMenu::item:selected {{ background-color: {t.accent}; color: {t.accent_text}; }}
QMenu::item:disabled {{ color: {t.muted}; }}
QMenu::separator {{ height: 1px; background: {t.border}; margin: 4px 10px; }}
QMenu::icon {{ left: 7px; }}
QMenu::right-arrow {{ margin-right: 8px; }}

QMenuBar {{ background-color: transparent; border: none; padding: 1px 2px; }}
QMenuBar::item {{ background-color: transparent; border-radius: 5px; padding: 4px 9px; }}
QMenuBar::item:selected {{ background-color: {t.hover}; }}
QMenuBar::item:pressed {{ background-color: {t.pressed}; }}
/* }}}}}} */

/* Tabs: an underline on the active tab instead of a raised box {{{{{{ */
QTabWidget::pane {{ border: 1px solid {t.border}; border-radius: 8px; top: -1px; }}
QTabWidget::tab-bar {{ alignment: left; }}

QTabBar {{ qproperty-drawBase: 0; background: transparent; }}
QTabBar::tab {{
    background: transparent;
    border: none;
    padding: 6px 14px;
    margin: 0 1px;
    color: {t.muted};
}}
QTabBar::tab:hover {{ color: palette(window-text); background-color: {t.hover}; border-radius: 6px; }}
QTabBar::tab:selected {{ color: palette(window-text); }}
QTabBar::tab:top:selected {{ border-bottom: 2px solid {t.accent}; }}
QTabBar::tab:bottom:selected {{ border-top: 2px solid {t.accent}; }}
QTabBar::tab:left:selected {{ border-right: 2px solid {t.accent}; }}
QTabBar::tab:right:selected {{ border-left: 2px solid {t.accent}; }}
QTabBar::tab:disabled {{ color: {t.border_strong}; }}
/* }}}}}} */

/* Item views {{{{{{ */
QAbstractItemView {{
    background-color: palette(base);
    alternate-background-color: {t.alt};
    border: 1px solid {t.border};
    selection-background-color: {t.accent};
    selection-color: {t.accent_text};
    outline: none;
}}

QListView, QTreeView {{ border-radius: 8px; }}
QListView::item, QTreeView::item {{ border-radius: 5px; padding: 2px; }}
QListView::item:hover, QTreeView::item:hover {{ background-color: {t.hover}; }}
QListView::item:selected:!active, QTreeView::item:selected:!active {{
    background-color: {t.selected_soft}; color: palette(text);
}}

QHeaderView {{ background-color: transparent; border: none; }}
QHeaderView::section {{
    background-color: {t.window};
    color: {t.muted};
    border: none;
    border-bottom: 1px solid {t.border};
    border-right: 1px solid {t.border_weak};
    padding: 5px 8px;
}}
QHeaderView::section:hover {{ background-color: {t.button_hover}; color: palette(window-text); }}
QHeaderView::section:last, QHeaderView::section:only-one {{ border-right: none; }}
/* }}}}}} */

/* Containers and separators {{{{{{ */
QGroupBox {{
    border: 1px solid {t.border};
    border-radius: 8px;
    margin-top: 11px;
    padding: 10px 4px 4px 4px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 5px;
    color: {t.muted};
}}

QToolBar {{ background: transparent; border: none; padding: 2px; spacing: 2px; }}
QToolBar::separator {{ background: {t.border}; margin: 5px 6px; }}
QToolBar::separator:horizontal {{ width: 1px; }}
QToolBar::separator:vertical {{ height: 1px; }}

QStatusBar {{ background: transparent; border-top: 1px solid {t.border_weak}; }}
QStatusBar::item {{ border: none; }}

QDockWidget {{ titlebar-close-icon: none; titlebar-normal-icon: none; }}
QDockWidget::title {{ background: transparent; padding: 6px; text-align: left; }}

/* QFrame::HLine is 4, VLine is 5. Stock Fusion draws both as a two-tone
   engraved groove; a single hairline is what every current UI uses. */
QFrame[frameShape="4"] {{ border: none; border-top: 1px solid {t.border}; max-height: 1px; }}
QFrame[frameShape="5"] {{ border: none; border-left: 1px solid {t.border}; max-width: 1px; }}

QSplitter::handle {{ background: transparent; }}
QSplitter::handle:hover {{ background: {t.hover}; }}
QSplitter::handle:horizontal {{ width: 5px; }}
QSplitter::handle:vertical {{ height: 5px; }}
/* }}}}}} */

/* Indicators {{{{{{ */
QProgressBar {{
    background-color: {t.track};
    border: none;
    border-radius: 5px;
    text-align: center;
    color: palette(window-text);
}}
QProgressBar::chunk {{ background-color: {t.accent}; border-radius: 5px; }}

QSlider::groove:horizontal {{ height: 4px; background: {t.track}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {t.accent}; border-radius: 2px; }}
QSlider::groove:vertical {{ width: 4px; background: {t.track}; border-radius: 2px; }}
QSlider::add-page:vertical {{ background: {t.accent}; border-radius: 2px; }}
QSlider::handle {{
    background: palette(base);
    border: 1px solid {t.border_strong};
    width: 13px; height: 13px;
    border-radius: 7px;
}}
QSlider::handle:horizontal {{ margin: -5px 0; }}
QSlider::handle:vertical {{ margin: 0 -5px; }}
QSlider::handle:hover {{ border-color: {t.accent}; }}
/* }}}}}} */
'''


def tree_view_hover_style(t: Tokens) -> str:
    "Replaces the stock gradient-and-border hover, which no current UI has worn since Aero."
    return f'''
        QTreeView::item:hover {{
            background: {t.hover};
            border: 1px solid transparent;
            border-radius: 6px;
        }}
    '''
