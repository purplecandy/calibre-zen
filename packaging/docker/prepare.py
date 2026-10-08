# The Python half of the image's start-up, run by entrypoint.sh as the
# library's owner through calibre-debug, so it uses calibre's own APIs:
#
#   zen-calibre-debug -e prepare.py -- USERDB [--create-library DIR]
#
# Creates an empty library when asked, adds or updates the user named by
# CALIBRE_ZEN_USERNAME, and prints "auth=1" or "auth=0" as its last line:
# whether the user database holds anyone, which is what turns the login on.
# The password is read from the environment or a file, never the command
# line, so it does not show in ps.
#
# calibre-debug runs Python with -OO, so checks are ifs, never asserts. It
# also runs this file in its own module's namespace, so every name here is
# prefixed to stay clear of calibre.debug's.
import os
import sys


def zen_say(msg):
    print('calibre-zen:', msg, file=sys.stderr, flush=True)


def zen_fail(msg):
    zen_say(msg)
    raise SystemExit(1)


def zen_create_library(path):
    from calibre.db.legacy import LibraryDatabase

    zen_say(f'creating an empty library in {path}')
    LibraryDatabase(path).close()
    if not LibraryDatabase.exists_at(path):
        zen_fail(f'could not create a library in {path}')


def zen_password():
    pw = os.environ.get('CALIBRE_ZEN_PASSWORD', '')
    path = os.environ.get('CALIBRE_ZEN_PASSWORD_FILE', '')
    if path:
        try:
            with open(path) as f:
                pw = f.read().strip()
        except OSError as e:
            zen_fail(f'cannot read CALIBRE_ZEN_PASSWORD_FILE: {e}')
    return pw


def zen_sync_user(userdb):
    from calibre.srv.users import UserManager, validate_username

    m = UserManager(userdb)
    name = os.environ.get('CALIBRE_ZEN_USERNAME', '').strip()
    if name:
        pw = zen_password()
        # calibre's own two rules (calibre.srv.users.validate_password), with
        # fixed messages, so nothing taken from the password reaches the log.
        if not pw:
            zen_fail('CALIBRE_ZEN_PASSWORD is empty. Set a password for the user.')
        if not pw.isascii():
            zen_fail('CALIBRE_ZEN_PASSWORD must use only English letters, digits and symbols.')
        warn = validate_username(name)
        if warn:
            zen_say(f'CALIBRE_ZEN_USERNAME: {warn}')
        if m.has_user(name):
            m.change_password(name, pw)
            m.set_readonly(name, False)
            zen_say(f'updated the password for {name}')
        else:
            m.add_user(name, pw)
            zen_say(f'added the user {name}')
    return bool(m.all_user_names)


def zen_main(args):
    if not args:
        zen_fail('usage: prepare.py USERDB [--create-library DIR]')
    userdb, rest = args[0], args[1:]
    if rest[:1] == ['--create-library']:
        if len(rest) != 2:
            zen_fail('--create-library needs a folder')
        zen_create_library(rest[1])
    auth = zen_sync_user(userdb)
    print(f'auth={int(auth)}', flush=True)


zen_main(sys.argv[1:])
