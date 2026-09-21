#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
The test runner. Started by ./zen-test as

    calibre-debug -e src/calibre_zen/tests/main.py -- [module ...] [-k pattern] [--list] [-q]

with the tree on the path and a temporary config directory in force. It
refuses to run any other way, because a test that writes into a person's real
calibre-zen settings is worse than no test.

The bundle runs Python with -OO, which strips `assert` statements, so nothing
in this package relies on a bare assert. unittest's own assertions are
method calls and are unaffected.
"""

import importlib
import os
import sys
import unittest

PACKAGE = 'calibre_zen.tests'


def die(msg: str) -> None:
    print('zen-test:', msg, file=sys.stderr)
    raise SystemExit(2)


def guard() -> None:
    if os.environ.get('CALIBRE_ZEN_TEST') != '1':
        die('run the tests through ./zen-test, which isolates the config directory')
    config = os.environ.get('CALIBRE_CONFIG_DIRECTORY', '')
    work = os.environ.get('CALIBRE_ZEN_TEST_DIR', '')
    if not (config and work and config.startswith(work)):
        die('CALIBRE_CONFIG_DIRECTORY is not inside the test directory; refusing to touch real settings')


def modules() -> list[str]:
    here = os.path.dirname(os.path.abspath(__file__))
    names = sorted(f[:-3] for f in os.listdir(here) if f.startswith('test_') and f.endswith('.py'))
    return names


def build_suite(wanted: list[str], patterns: list[str]) -> unittest.TestSuite:
    loader = unittest.defaultTestLoader
    if patterns:
        loader.testNamePatterns = [p if any(c in p for c in '*?[') else f'*{p}*' for p in patterns]
    suite = unittest.TestSuite()
    available = modules()
    for name in wanted or available:
        if '.' in name:
            # A dotted path into a module: Class or Class.method.
            dotted = name if name.startswith(PACKAGE + '.') else f'{PACKAGE}.{name}'
            if not dotted.split('.')[2].startswith('test_'):
                parts = dotted.split('.')
                parts[2] = 'test_' + parts[2]
                dotted = '.'.join(parts)
            suite.addTests(loader.loadTestsFromName(dotted))
            continue
        module = name if name.startswith('test_') else 'test_' + name
        if module not in available:
            die(f'no test module {module}.py; have: {", ".join(available)}')
        suite.addTests(loader.loadTestsFromModule(importlib.import_module(f'{PACKAGE}.{module}')))
    return suite


def flatten(suite) -> list:
    out = []
    stack = [suite]
    while stack:
        s = stack.pop()
        for t in s:
            if isinstance(t, unittest.TestSuite):
                stack.append(t)
            else:
                out.append(t)
    return out


def banner() -> None:
    import calibre
    from calibre.constants import __appname__, __version__, config_dir, zen_version

    print(f'{__appname__} {zen_version} on calibre {__version__}, python {sys.version.split()[0]}')
    print('  source ', os.path.dirname(calibre.__file__))
    print('  config ', config_dir)
    print('  platform', os.environ.get('QT_QPA_PLATFORM', ''))


def main(argv: list[str]) -> int:
    guard()
    wanted, patterns = [], []
    verbosity = 2
    list_only = False
    it = iter(argv)
    for a in it:
        if a == '-k':
            patterns.append(next(it, '') or die('-k needs a pattern'))
        elif a == '--list':
            list_only = True
        elif a == '-q':
            verbosity = 1
        elif a.startswith('-'):
            die(f'unknown option {a}')
        else:
            wanted.append(a)

    suite = build_suite(wanted, patterns)
    tests = flatten(suite)
    if list_only:
        for t in tests:
            print(t.id().removeprefix(PACKAGE + '.'))
        return 0
    if not tests:
        die('no tests matched')

    banner()
    print(f'  {len(tests)} tests\n')
    result = unittest.TextTestRunner(verbosity=verbosity, stream=sys.stdout).run(suite)
    # An import error inside a test module shows up as a test named
    # "_FailedTest"; that is a failure of the suite, not of one test.
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
