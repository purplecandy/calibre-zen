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

How it gets into the server: `serve.install` calls `install` once /app/ is
added. calibre's index route is taken out of the router and put back wrapped.
The wrap calls calibre's own, which keeps its redirect to a trailing slash
under a prefix (relative URLs need it, ours included), then serves that file
with the script added, cached per server like the app's own files. With no
build to go to, calibre's page goes out untouched.

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


def is_calibres_index(endpoint) -> bool:
    fn = getattr(endpoint, 'f', endpoint)  # the router holds a RouteFunction around it
    return getattr(fn, '__module__', '') == 'calibre.srv.code' and getattr(fn, '__name__', '') == 'index'


def make_route(orig, choice: str):
    from calibre.srv.routes import endpoint
    from calibre_zen.web import serve

    # The same public route, with the same caching: none of calibre's own,
    # only the ETag a cached copy gets.
    @endpoint('', auth_required=False, cache_control=orig.cache_control)
    def zen_home(ctx, rd):
        f = orig(ctx, rd)
        path = getattr(f, 'name', None)
        if not isinstance(path, str) or not serve.is_built(serve.DIST):
            return f
        mtime = os.fstat(f.fileno()).st_mtime_ns
        f.close()

        def generate():
            with open(path, 'rb') as page:
                return inject(page.read(), choice)

        return rd.generate_static_output(f'zen-home:{choice}:{mtime}', generate)

    zen_home.zen_wrapped = orig
    zen_home.zen_choice = choice
    return zen_home


def install(router, choice: str | None = None) -> bool:
    """
    Wrap calibre's `/` in a router calibre has already finalized, and finalize
    it again. False when something other than calibre's index is at `/`.
    """
    route = router.routes.get('')
    if route is None:
        return False
    orig = route.endpoint
    if getattr(orig, 'zen_wrapped', None) is not None:
        return True
    if not is_calibres_index(orig):
        # A content-server plugin serves `/`. Its page stays as it is.
        print('calibre-zen: the server address keeps its own page:', orig)
        return False
    del router.routes['']
    router.endpoints.discard(orig)
    router.add(make_route(orig, choice or home()))
    router.finalize()
    return True
