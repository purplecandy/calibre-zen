# Reviewing calibre-zen

calibre-zen is a fork of calibre that restyles and partly rebuilds the Qt
Widgets interface. Almost all of its own code is under `src/calibre_zen/`,
laid over an unmodified calibre. Most pull requests are written by an AI
agent and reviewed by one person who reads code well but does not write
Python day to day. Review for that person: judge the approach, the scope and
the complexity, and check the rules below. Do not review style.

## Facts about this codebase

Get these right before flagging anything.

- **Python 3.14.** The tree and the shipped interpreter are both 3.14. In
  particular `except A, B:` without parentheses is valid (PEP 758) and is
  what the formatter writes. Do not report it.
- **The interpreter runs with `-OO`.** `assert` statements are stripped at
  runtime, so an `assert` in `src/calibre_zen/` is a check that never runs.
  Report those. Checks must be `if ...: raise`.
- **Nothing is compiled or built.** A package is calibre's own release binary
  with this fork's Python laid on top. `src/calibre/` must stay on the
  upstream release tag pinned in `packaging/upstream.json`.
- **Lint and formatting are CI's job.** `ruff check`, `ruff format` and
  shellcheck run on every PR (`.github/workflows/zen-ci.yml`). Do not comment
  on formatting, import order, quotes or line length.
- **Tests run with `./zen-test`**, headless, on a real calibre binary; the
  end-to-end module opens the real main window on a temporary library.

## Rules to enforce

These are the repository's own rules, from `.claude/CLAUDE.md` and
`src/calibre_zen/README.md`. A violation is a finding even when the code works.

1. **No upstream edits for looks or behaviour.** Files under `src/calibre/`
   may change only for: the four-line overlay hook in `gui2/__init__.py`,
   fork identity (`constants.py`, `utils/ipc/__init__.py`, `linux.py`, marked
   `# calibre-zen:`), and single added lines of
   `widget.setProperty('zenVariant', ...)`. Anything else under `src/calibre/`
   is wrong even if small; the fix belongs in `src/calibre_zen/`, wrapping
   from outside.
2. **Where a look change goes, in order:** a token in `theme/tokens/`, then a
   rule in `theme/qss/app/`, then an entry in `theme/rewrite.py`. A colour or
   radius literal inside a `.qss` template or a Python widget is a finding
   unless it appears exactly once and means nothing elsewhere.
3. **QSS templates use `$name`, never `{}`.** A template may only name a
   semantic or component token. Rules are written against `Chrome`, never
   against a scheme's own colour map.
4. **Behaviour needs a test.** A change to `filters/`, `centre/` or `status/`
   that alters what the app does should touch `src/calibre_zen/tests/`.
   A new token or template rule is already covered by `test_theme.py`.
5. **Nothing under `.claude/` is committed.** If a PR adds or changes a file
   there, say so.
6. **Every commit carries** `Co-authored-by: Nadeem Siddique <nadeem@kibibyte.in>`
   when authored by `purple-agent`.
7. **Prose a user reads** (docs in `site/`, release notes, onboarding and
   in-app strings) is plain: short sentences, two-sentence paragraphs, no
   long punctuation, never bossy. Code comments are exempt.

## What the reviewer wants to hear about

Lead with these. One clear comment beats five small ones.

- **A simpler way to do the same thing.** If a change adds a class, a layer of
  indirection, a new environment variable or a new configuration knob that
  the stated goal does not need, say what the smaller version would be.
- **Scope creep.** Files or behaviour changed that the PR description does
  not explain.
- **Risk to `git pull` from upstream.** Anything that widens the diff against
  `src/calibre/` or depends on a private detail of a calibre widget that is
  likely to move.
- **Silent failure.** A `try/except` that swallows an error without a
  comment saying why losing it is acceptable; a wrapped method that no longer
  calls the original; a feature that degrades without leaving a trace.
- **Behaviour that a test would not notice.** Point at the module in
  `src/calibre_zen/tests/` where a test belongs.
- **Anything a person could not undo** from the toolbar or a setting, such
  as a change that writes into the user's library or config in a new way.

## What not to report

- Formatting, naming preferences, docstring wording, import order.
- Python 3.13 or older concerns.
- Suggestions to add type hints, logging or docstrings for their own sake.
- "Consider adding a test" without naming what the test would assert.
