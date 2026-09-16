# Building calibre-zen

calibre-zen is a fork of calibre, not a plugin or a theme. It installs
alongside a normal calibre and shares nothing with it: separate config,
separate cache, separate lock, separate IPC socket, separate menu entries.
This file is how it gets built, and what is still missing.

## Status

| piece | state |
| --- | --- |
| runtime identity (config, cache, lock, IPC) | **done**, verified on macOS |
| macOS bundle identity (ids, URL scheme, executable) | **done**, not yet built |
| Linux desktop + PATH identity | **done**, *not verified* -- no Linux here |
| Windows installer identity | **not started** |
| application icon | **not started** -- needs a design, see below |
| CI pipeline | **not started** |
| a built installer for any platform | **not yet** |

Everything marked "done" is a source change that has been linted and, where a
Mac can exercise it, run. Nothing has been through bypy yet.

## What makes it a separate application

calibre derives most of its identity from `calibre.constants.__appname__`, so
the fork's identity is one string, and everything that has to differ is derived
from it rather than spelled out again. That is deliberate: a merge from
upstream should conflict in one place, not twenty.

```
__appname__ = 'calibre-zen'          src/calibre/constants.py
```

| what | calibre | calibre-zen |
| --- | --- | --- |
| config | `~/Library/Preferences/calibre` | `…/calibre-zen` |
| cache | `~/Library/Caches/calibre` | `…/calibre-zen` |
| single-instance lock | `calibre-singleinstance-…` | `calibre-zen-singleinstance-…` |
| GUI IPC socket | `/tmp/calibre-501-gui.sock` | `/tmp/calibre-zen-501-gui.sock` |
| Windows pipe | `\\.\pipe\CalibreGUI` | `\\.\pipe\CalibreZenGUI` |
| macOS bundle id | `net.kovidgoyal.calibre` | `io.github.purplecandy.calibre-zen` |
| URL scheme | `calibre://` | `calibre-zen://` |
| Linux desktop id | `calibre-gui.desktop` | `calibre-zen-gui.desktop` |
| Linux icon theme name | `calibre-gui` | `calibre-zen-gui` |

**One of those was a bug, not a rename.** Upstream derives the single-instance
lock from `__appname__` but hardcodes the IPC socket as
`/tmp/calibre-{uid}-gui.sock`. The two disagreed: the lock would let both
applications start, and then `Listener.start_listening` answers
`AddressInUseError` by calling `removeServer()` -- so whichever started second
silently took over the other's socket, and "open in calibre" from the file
manager went to the wrong application. Deriving the socket from `__appname__`
too is what actually makes coexistence work.

### Command-line tools

Inside the installation the executables keep upstream's names. calibre shells
out to `calibre-parallel`, `ebook-convert` and friends **by basename**
(`utils/ipc/launch.py` resolves them against `sys.executables_location`), so
renaming them there would mean chasing every call site, and getting one wrong
is a runtime failure inside a worker nobody is watching.

Only what reaches `PATH` is prefixed, because that is the only place a
normally-installed calibre can be collided with:

```
calibre-zen        the GUI, unprefixed -- it is already the app's name
zen-calibredb      -> <install>/calibredb
zen-ebook-convert  -> <install>/ebook-convert
zen-calibre-server -> <install>/calibre-server
…
```

`calibre.linux.path_name()` is the single rule. On macOS nothing is put on
`PATH` at all -- upstream does not either -- so there is nothing to prefix; add
`calibre-zen.app/Contents/MacOS` to your `PATH` by hand if you want the tools.

## How calibre builds installers, and what that means here

calibre's build system is `bypy`, a separate repository:

```bash
git clone https://github.com/kovidgoyal/bypy.git   # sibling of this repo,
                                                   # or set BYPY_LOCATION
```

Two stages, per platform: build all ~71 dependencies from source (Qt, Python,
PyQt, podofo, hunspell…), then build the program.

```bash
./setup.py build_dep macos     # hours. Output: bypy/b/macos
./setup.py osx --dont-sign --dont-notarize   # minutes. Output: dist/
```

Its README says building *must* run on Linux, and the macOS and Windows stages
run inside QEMU VMs you create by hand. **That is true of the documented path,
but it is not a property of the build itself.** `bypy/macos.py` only does
rsync-over-SSH into the VM and then runs, inside it:

```
python <root>/bypy BYPY_ROOT=<root> BYPY_ARCH=macos BYPY_UNIVERSAL=true  dependencies
python <root>/bypy BYPY_ROOT=<root> BYPY_ARCH=macos BYPY_UNIVERSAL=true  program
```

`dependencies` and `program` are ordinary sub-commands that run on whatever
machine invokes them. The VM is transport, not a requirement -- which is what
makes a CI pipeline on native runners plausible without any virtualisation.

### Why the shipped bundle cannot simply be patched

There is no Python source anywhere inside a built calibre. `compile_py_modules`
runs `freeze_python()`, which compiles every module into
`Frameworks/calibre-launcher.dylib` and deletes the source tree; what is left
(`Frameworks/plugins/python-lib.bypy.frozen`) is a single opaque blob. So a
calibre-zen build is a real build. There is no shortcut that reskins a
downloaded `.dmg`.

## The intended pipeline

Dependencies are the slow half and they change rarely, so they are built once
and reused -- which is what calibre's own CI does, downloading a prebuilt
tarball rather than compiling Qt on every run, and what `bypy export` exists to
produce.

```
once per platform, when a dependency version changes
  dependencies  ->  sw.tar.xz  ->  published as a release asset

every calibre-zen release
  fetch sw.tar.xz  ->  program  ->  dist/calibre-zen-<version>.{dmg,msi,txz}
```

Targets, in the order they are worth doing:

1. **Linux** -- cheapest to build, and the only one that needs no signing at
   all: a plain `.txz` that unpacks anywhere.
2. **macOS** -- a `.dmg`.
3. **Windows** -- an `.msi`.

### Signing

Deliberately skipped for now. Unsigned builds still install; they warn:

- macOS: Gatekeeper refuses a double-click. Right-click -> Open, once, per
  machine. Worth saying so on the download page rather than letting people
  discover it.
- Windows: SmartScreen warns until the download builds reputation.
- Linux: nothing to sign.

Revisit when there are enough users for the warnings to cost more than the
certificates (Apple Developer ~$99/yr; a Windows OV certificate a few hundred).

## Open items

- **An icon.** The bundle still points at calibre's. Two identical icons in the
  Dock is the one place coexistence visibly fails, and a logo is a design
  decision, not a build detail. `icons/icns/make_iconsets.py` generates every
  size from a single `icon.svg`, so this is one file away.
- **Windows installer identity** -- `bypy/windows/__main__.py` and the WiX
  template still say calibre.
- **`oeb/reader.py`** stamps `[http://{appname}-ebook.com]` into converted
  books, which for this fork is a URL that does not exist. Cosmetic, but it
  ends up inside people's files.
- **Version.** `numeric_version` is still calibre's, which is load-bearing --
  plugin compatibility and the database schema both key off it. A separate
  calibre-zen version needs to sit beside it rather than replace it.

## Upstream

This fork tracks `upstream/master` and merges on a cycle. The identity patch is
narrow on purpose -- `constants.py`, `utils/ipc/__init__.py`, `linux.py` and
`bypy/macos/__main__.py` -- and every hunk is marked `calibre-zen:` so a
conflict is obvious. The styling overlay in `src/calibre_zen/` touches no
upstream file at all; see `src/calibre_zen/README.md`.

calibre is GPL v3 and so is this. Kovid Goyal's copyright notices stay where
they are: the fork's name is added to them, never substituted.
