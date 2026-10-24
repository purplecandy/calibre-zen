#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
What the server's address opens: the new web app, or calibre's.

calibre's app stays where it is, at `/`, because every link into it lives
after the `#`: a book open in the reader is `/#book_id=12&fmt=EPUB&mode=read_book`,
and so are its bookmarks, its "open in a new tab" links, and the new app's
Read button. The browser never sends the part after `#`, so the server cannot
tell a bare visit from one of those, and a redirect at `/` would send them
all to the new app. The page can tell. So `/` still serves calibre's page,
with a small script put at the top of its <head>:

    the new app is home     a bare visit (no `#...`) stops loading the page
                            and replaces itself with app/. Anything after `#`
                            is calibre's, and stays.
    calibre's app is home   nothing moves.

and, either way, a link to the new app on calibre's home screen.

A tab that has been in calibre's app stays there: the script remembers it in
sessionStorage, so reloading calibre's home screen, which has no `#`, does not
jump to the new app. The new app's menu opens calibre's app as `/?ui=calibre`,
which counts too, and the link back clears it. calibre's app installed to a
home screen or dock also stays: its manifest starts at `/`, and someone who
installed it meant to open it.

calibre's service worker, at `/service_worker.js`, only ever answers for `/`
itself, network first. It caches this page, script and all, so offline a bare
visit still goes to app/, where the new app's own worker answers. A browser
that only ever opens the new app never runs calibre's script, so never gets
calibre's worker.

How it gets into the server: `serve.install` calls `install` last, once /app/
is added. The function behind calibre's index route is wrapped in place, as
reader_look.py wraps it for the reader's look, and ours goes outside that
one: it calls whatever is inside, which keeps calibre's redirect to a
trailing slash under a prefix (relative URLs need it, ours included), and
sends that page with the script added, cached per server like the app's own
files. With no build to go to, the page goes out as it came.

The setting is read once, when the server starts, which is when calibre's own
Sharing settings take effect: CALIBRE_ZEN_WEB_HOME first (`app` or
`calibre`, for Docker and the host), then `zen_web_home` in gui.json, which
Preferences -> Sharing over the net sets (sharing.py), then DEFAULT.
"""

import json
import os

ENV_VAR = 'CALIBRE_ZEN_WEB_HOME'
PREF_KEY = 'zen_web_home'
APP = 'app'
CALIBRE = 'calibre'
CHOICES = (APP, CALIBRE)
DEFAULT = APP

# Kept in the tab's sessionStorage while it is in calibre's app.
STAY_KEY = 'zen-calibre-app'
# The query the new app's menu opens calibre's app with: /?ui=calibre.
STAY_QUERY = 'ui=calibre'

SCRIPT = '''\
<script>/* calibre-zen: web/switch.py */
(function () {
  var home = %(home)s, key = %(key)s, link = %(link)s
  var hash = location.hash.length > 1
  var marked = location.search.indexOf(%(query)s) > -1
  var installed = navigator.standalone === true ||
    (window.matchMedia && !window.matchMedia('(display-mode: browser)').matches)
  var stay = home !== 'app' || hash || marked || installed
  try {
    if (hash || marked) sessionStorage.setItem(key, '1')
    else if (sessionStorage.getItem(key)) stay = true
  } catch (e) {}
  if (!stay) {
    window.stop()
    location.replace('app/')
    return
  }
  if (marked) history.replaceState(history.state, '', location.pathname + location.hash)
  // calibre's page falls back to document.scripts[0] for its own script.
  if (document.currentScript) document.currentScript.remove()

  function onHome() {
    var q = new URLSearchParams(location.hash.slice(1))
    var panel = q.get('panel'), mode = q.get('mode')
    return (!panel || panel === 'home') && (!mode || mode === 'book_list')
  }
  function add() {
    var a = document.createElement('a')
    a.id = 'zen-new-app'
    a.href = 'app/'
    a.textContent = link
    a.addEventListener('click', function () {
      try { sessionStorage.removeItem(key) } catch (e) {}
    })
    var s = a.style
    s.position = 'fixed'
    s.top = '0.6rem'
    s.right = '0.75rem'
    s.zIndex = '1000'
    s.padding = '0.25rem 0.75rem'
    s.borderRadius = '999px'
    s.font = '600 0.85rem/1.3 system-ui, sans-serif'
    s.textDecoration = 'none'
    s.color = 'var(--calibre-color-window-foreground, inherit)'
    s.background = 'var(--calibre-color-window-background, transparent)'
    s.border = '1px solid currentColor'
    document.body.appendChild(a)
    var update = function () {
      a.hidden = !onHome()
      // Centred on calibre's top bar, whatever its height.
      var bar = document.querySelector('.main-top-bar')
      if (bar && !a.hidden) s.top = Math.max(0, (bar.offsetHeight - a.offsetHeight) / 2) + 'px'
    }
    update()
    // calibre moves between screens with pushState, which fires no event.
    new MutationObserver(update).observe(document.body, { childList: true, subtree: true })
    window.addEventListener('popstate', update)
  }
  if (document.body) add()
  else document.addEventListener('DOMContentLoaded', add)
})()
</script>
'''

LINK_TEXT = 'Open the new web app'


def from_env() -> str | None:
    "The environment's choice, or None when it makes none."
    value = (os.environ.get(ENV_VAR) or '').strip().lower()
    if not value:
        return None
    if value in CHOICES:
        return value
    print(f'calibre-zen: ignoring {ENV_VAR}={value!r}, which is not one of {", ".join(CHOICES)}')
    return None


def stored() -> str | None:
    "The choice made in Preferences, read from gui.json as a plain file, so the host never imports the GUI."
    try:
        from calibre.utils.config import JSONConfig

        value = JSONConfig('gui').get(PREF_KEY)
    except Exception:
        return None
    return value if value in CHOICES else None


def home() -> str:
    "What the server's address opens: the environment first, then the stored choice, then DEFAULT."
    return from_env() or stored() or DEFAULT


def script(choice: str) -> bytes:
    return (
        SCRIPT
        % {
            'home': json.dumps(choice),
            'key': json.dumps(STAY_KEY),
            'query': json.dumps(STAY_QUERY),
            'link': json.dumps(LINK_TEXT),
        }
    ).encode('utf-8')


def inject(page: bytes, choice: str) -> bytes:
    "calibre's page with the script first in its <head>. A page without one goes out as it is."
    head = b'<head>'
    at = page.find(head)
    if at < 0:
        return page
    at += len(head)
    return page[:at] + b'\n' + script(choice) + page[at:]


def calibres_index(fn):
    """
    calibre's own index function under any wraps around it (reader_look.py's,
    ours), each of which names the one inside as __wrapped__. None when the
    root is something else.
    """
    fn = getattr(fn, 'f', fn)  # the router holds a RouteFunction around it
    while fn is not None:
        if getattr(fn, '__module__', '') == 'calibre.srv.code' and getattr(fn, '__name__', '') == 'index':
            return fn
        fn = getattr(fn, '__wrapped__', None)
    return None


def wrap(orig, choice: str):
    "`orig` -- calibre's index, or a wrap of it -- with the script added to whatever page it sends."
    from calibre.srv.http_response import StaticOutput
    from calibre_zen.web import serve

    def index(ctx, rd):
        out = orig(ctx, rd)
        if not serve.is_built(serve.DIST):
            return out
        if isinstance(out, StaticOutput):
            # reader_look.py's page, already made once for this server.
            key = out.etag

            def generate():
                return inject(out.data, choice)

        else:
            path = getattr(out, 'name', None)
            if not isinstance(path, str):
                return out
            key = os.fstat(out.fileno()).st_mtime_ns
            out.close()

            def generate():
                with open(path, 'rb') as f:
                    return inject(f.read(), choice)

        return rd.generate_static_output(f'zen-home:{choice}:{key}', generate)

    index.zen_home = choice
    index.__wrapped__ = orig
    index.__name__ = getattr(orig, '__name__', 'index')
    return index


def install(router, choice: str | None = None) -> bool:
    """
    Wrap the function behind `/` in place, as reader_look.py does: same route,
    same login rule, same caching. Called last, so the script goes into the
    page every other wrap has made. False when something other than calibre's
    index is at `/`.
    """
    from dataclasses import replace

    route = router.routes.get('')
    if route is None:
        return False
    fn = route.endpoint.f
    if getattr(fn, 'zen_home', None) is not None:
        return True
    if calibres_index(fn) is None:
        # A content-server plugin serves `/`. Its page stays as it is.
        print('calibre-zen: the server address keeps its own page:', fn)
        return False
    route.endpoint = replace(route.endpoint, f=wrap(fn, choice or home()))
    return True
