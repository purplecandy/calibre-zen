#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The host's command line: calibre-server's own options, with two changes.

The defaults are the GUI's Sharing settings -- server-config.txt, the file
Preferences -> Sharing over the net writes -- instead of calibre-server's
built-in ones, so a host serves the way the person set sharing up. Anything
given on the command line still wins, because the settings go in as the
parser's defaults and optparse only uses a default when the flag is absent.

And there are two more options: --auto-add DIR and --no-auto-add, plus a
hidden one, --zen-library DIR, for ./calibre-zen.

--zen-library is how the launcher names the library it chose. It cannot be a
positional argument like a library named by hand, because calibre-server's
positional arguments change meaning with --manage-users: there they are the
user command (`add bob secret`), and a library added to them would become a
password. An option is never one of them.

There are two parsers. `full_parser` is calibre-server's own, from
calibre.srv.standalone, and is what the host itself parses with. Importing it
pulls in the whole server -- the database layer, the handler, every route
module -- which a tray that only wants to know a port should not pay for. So
`light_parser` builds the same option set from calibre.srv.opts alone, and
spells out the handful of options standalone adds on top. test_host checks the
two still agree, so an option upstream adds shows up as a failing test rather
than a tray that cannot parse its own arguments.
"""

import os
import sys
from optparse import SUPPRESS_HELP

USAGE = '''\
%prog [options] [path to library folder...]

Run calibre-zen's host: the calibre Content server, set up from the Sharing
settings in calibre-zen's preferences, plus a watched folder for adding books.
With no library given, the libraries calibre-zen knows about are served.
'''

# The options calibre.srv.standalone.create_option_parser adds to the ones in
# calibre.srv.opts: (flag, dest, takes a value).
STANDALONE_ONLY = (
    ('--log', 'log', True),
    ('--access-log', 'access_log', True),
    ('--custom-list-template', 'custom_list_template', True),
    ('--search-the-net-urls', 'search_the_net_urls', True),
    ('--daemonize', 'daemonize', False),  # Linux only, as in standalone
    ('--pidfile', 'pidfile', True),
    ('--auto-reload', 'auto_reload', False),
    ('--manage-users', 'manage_users', False),
)

# Every spelling of "all interfaces" calibre accepts for listen_on.
ANY_ADDRESS = frozenset(('', '0.0.0.0', '::', '::0', '::0.0.0.0'))


def daemonize_supported() -> bool:
    from calibre.constants import ismacos, iswindows

    return not (iswindows or ismacos)


def full_parser():
    "calibre-server's parser, with the Sharing defaults and the host's own options."
    from calibre.srv.standalone import create_option_parser

    parser = create_option_parser()
    _finish(parser)
    return parser


def light_parser():
    "The same options without importing the server. For launch.local_url and the tray."
    from calibre.srv.opts import opts_to_parser

    parser = opts_to_parser(USAGE)
    for flag, dest, takes_value in STANDALONE_ONLY:
        if dest == 'daemonize' and not daemonize_supported():
            continue
        if takes_value:
            parser.add_option(flag, dest=dest, default=None)
        else:
            parser.add_option(flag, dest=dest, default=False, action='store_true')
    _finish(parser)
    return parser


def _finish(parser) -> None:
    parser.prog = 'calibre-zen --host'
    parser.set_usage(USAGE)
    parser.add_option(
        '--auto-add',
        dest='auto_add',
        default=None,
        metavar='DIR',
        help='Watch DIR and add every book that lands in it, then delete the file, as the main window does.'
        ' By default the folder set in Preferences -> Adding books -> Automatic adding is watched, if there is one.',
    )
    parser.add_option(
        '--no-auto-add',
        dest='no_auto_add',
        default=False,
        action='store_true',
        help='Do not watch any folder, even the one set in the preferences.',
    )
    parser.add_option(
        '--zen-library',
        dest='zen_library',
        default=None,
        metavar='DIR',
        help=SUPPRESS_HELP,  # ./calibre-zen's library: served after any named ones, ignored by --manage-users
    )
    parser.set_defaults(**sharing_defaults())


def sharing_defaults() -> dict:
    """
    Every server option's value from server-config.txt, falling back to
    calibre's own default for anything the file does not set. Read fresh each
    time: the tray rewrites the file and restarts the host.
    """
    from calibre.srv.opts import DEFAULT_CONFIG, Options, options, parse_config_file

    try:
        # parse_config_file locks the file, which creates it. Only read one
        # that is there: asking for a port should not write a settings file.
        config = parse_config_file(DEFAULT_CONFIG) if os.path.exists(DEFAULT_CONFIG) else Options()
    except ValueError as err:
        print(f'calibre-zen host: ignoring {DEFAULT_CONFIG}: {err}', file=sys.stderr)
        config = Options()
    return {name: getattr(config, name) for name in options}


def parse(argv, parser=None):
    "(opts, libraries) for a host started with `argv`, which does not include a program name."
    parser = parser or full_parser()
    opts, args = parser.parse_args(list(argv))
    return opts, list(args)


def auto_add_folder(opts) -> tuple[str | None, bool]:
    """
    The folder to watch and whether it was asked for on the command line.
    A folder from the preferences is only a default: when it is not usable it
    is skipped with a message, as the main window does. One given with
    --auto-add has to work.
    """
    if opts.no_auto_add:
        return None, False
    if opts.auto_add:
        return os.path.abspath(os.path.expanduser(opts.auto_add)), True
    from calibre.utils.config import JSONConfig

    # The GUI's gprefs, read as a plain file so the host never imports the
    # main window's preferences machinery to learn one path.
    path = JSONConfig('gui').get('auto_add_path')
    return (path or None), False


def local_address(opts) -> str:
    "The address to reach a host with these options from this computer."
    from calibre.utils.network import format_addr_for_url

    listen_on = (opts.listen_on or '').strip()
    host = '127.0.0.1' if listen_on in ANY_ADDRESS else listen_on
    return format_addr_for_url(host)
