# Give this instance its own application identity ("calibre-zen") so it does
# not collide with a normally-installed calibre. calibre's single-instance
# lock, cache directory and default config directory are all derived from
# calibre.constants.__appname__, which modules bind by value at import time --
# so this must run before anything else imports it.
import sys

import calibre.constants as constants

APPNAME = 'calibre-zen'
constants.__appname__ = APPNAME
constants.DEBUG = True

from calibre.utils.lock import singleinstance_path  # noqa: E402  (must follow the patch)

if '--zen-selftest' in sys.argv:
    print('appname   :', constants.__appname__)
    print('lock file :', singleinstance_path('GUI'))
    raise SystemExit(0)

from calibre.gui2.main import main  # noqa: E402

raise SystemExit(main(['calibre-zen'] + sys.argv[1:]))
