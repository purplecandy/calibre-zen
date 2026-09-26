# Building calibre-zen

calibre-zen is a fork of calibre, not a plugin or a theme. It installs
alongside a normal calibre and shares nothing with it: separate config,
separate cache, separate lock, separate IPC socket, separate menu entries.
This file is how it gets built, and what is still missing.

## Status

| piece | state |
| --- | --- |
| runtime identity (config, cache, lock, IPC) | **done**, verified on macOS and Linux |
| macOS bundle identity (ids, URL scheme, executable) | **done** |
| Linux desktop + PATH identity | **done**, `calibre_postinstall` not yet exercised |
| Windows installer identity | via MSIX: `msix.json` carries the Store identity |
| application icon | **done** on all three: `.icns`, `.png`, `calibre-zen.exe`'s `.ico` and the Store logos, all from `imgsrc/calibre.svg` |
| Linux package | **done** -- `packaging/linux/package.sh`, x86_64 and arm64 |
| Linux Flatpak | **in progress** -- `packaging/flatpak/package.sh` wraps the Linux package for x86_64 and arm64; a Linux desktop check remains |
| macOS package | **done** -- `packaging/macos/package.sh`, universal `.dmg` |
| Windows package | **done** -- `packaging/windows/package.ps1`, x64 `.msi` (WiX), portable installer `.exe`, `.zip`, and `.msix` for the Store |
| release parity | **done** -- every kind of file an upstream release has: two `.txz`, `.dmg`, `.msi`, portable installer, source `.tar.xz` |
| CI | `.github/workflows/zen-ci.yml` on every push and pull request: lint, compile, tests (below). `.github/workflows/zen-package.yml` on pushes to `zen` and tags, one job per platform; the Windows job installs and removes the `.msi` and runs the portable installer |
| signing | macOS **Developer ID + notarization**, secret-gated; Windows: the Store signs the `.msix`, the rest is unsigned; Linux n/a |

## How it is built

**Nothing is compiled.** A calibre-zen package is calibre's own release
binary with this fork's Python laid on top.

A released calibre is Qt, a Python interpreter, some seventy native libraries
and calibre's own compiled extensions, plus one blob
(`python-lib.bypy.frozen`) holding upstream's Python as bytecode. Every
launcher in it honours `CALIBRE_DEVELOP_FROM`: point that at a directory and
the frozen importer looks there first, shadowing the blob. Kovid Goyal built
that so he could run his own source against a binary while developing. This
fork changes nothing native -- its whole diff against upstream is Python and
icon files -- so the same hook is enough to ship it.

Each `packaging/<os>/package.*` does the same five things:

1. Download the installer for the release pinned in
   `packaging/upstream.json` and refuse it unless its sha256 matches the
   digest GitHub published for that release. Three sources, in order: our
   own mirror of upstream's installers (below), then upstream's archive,
   `download.calibre-ebook.com/<version>/`, then GitHub. Upstream deletes a
   release's GitHub assets the day the next release ships, the archive
   keeps every version but is one server, and the mirror is ours. The
   digest check is the same whichever answered.
2. Unpack it, and put `src/` **beside the binary's own `resources/`
   directory** -- `<pkg>/src` on Linux, `Contents/Resources/src` on macOS,
   `app\src` on Windows. Develop mode looks for resources at
   `<CALIBRE_DEVELOP_FROM>/../resources`, so that placement makes it find
   the binary's complete resources (MathJax, hyphenation, fonts,
   translations) without duplicating any of it. The fork's own changed
   resource files, which are the icons, are copied in on top.
3. Add launchers that set two environment variables and exec the frozen
   binary: `CALIBRE_DEVELOP_FROM` selects the source, and
   `CALIBRE_ZEN_PACKAGED=1` tells `constants.py` to switch
   `is_running_from_develop` off. Develop mode would otherwise recompile the
   UI forms, `icons.rcc` and the RapydScript for the viewer, editor and
   content server on every launch, into the install directory.
4. Compile all of that once, with the bundle's own Python so the bytecode
   matches its interpreter: the 96 `_ui.py` forms, `icons.rcc` with the
   fork's images, and `__pycache__` for the whole tree.
5. Launch the result headless (`QT_QPA_PLATFORM=offscreen`), check it
   reports the fork's identity and installs the overlay, and **fail if
   anything under the tree changed** -- a package may be installed
   read-only, and on macOS Gatekeeper runs a downloaded app from a read-only
   translocated mount.

The constraint this buys is a single one: **the Python shipped must be from
the same calibre tag as the binary it shadows**, because the Python calls
the compiled extensions by name and argument shape. The release branch
therefore sits on an upstream release tag, never on master, and the scripts
refuse to run if `numeric_version` and `upstream.json` disagree.

```bash
packaging/linux/package.sh [x86_64|arm64]   # on Linux  -> dist/calibre-zen-<v>-linux-<arch>.txz
packaging/flatpak/package.sh [x86_64|arm64] # after the Linux script -> dist/calibre-zen-<v>-linux-<arch>.flatpak
packaging/macos/package.sh                  # on macOS  -> dist/calibre-zen-<v>-macos.dmg
powershell -File packaging\windows\package.ps1   # on Windows -> dist\calibre-zen-<v>-windows-x64.{msi,zip,msix}
                                                 #            + dist\calibre-zen-portable-installer-<v>.exe
```

### Versions

`<v>` is the fork's own version, `zen_version` in `src/calibre/constants.py`,
starting at 0.1.0. It is the only version a user sees: the file names, the
macOS bundle's `CFBundleShortVersionString`, `calibre-zen.exe`'s version
info, the MSIX identity (as `<v>.0`, since the Store wants four parts) and
the GitHub release. A release tag is `v<v>`, and the workflow refuses a tag
that does not equal `v` + `zen_version`, which also keeps upstream's `v9.x`
tags from building anything if one is ever pushed here.

Beside it, `zen_display_name` (`Calibre Zen`) is what a person sees: the
macOS bundle name, Dock and menu bar, the Linux desktop entry, the Windows
Start menu and Store listing, and the main window's title, which the overlay
rewrites from `__appname__`. `__appname__` itself stays `calibre-zen`, because
the config directory, lock, socket and executable names derive from it.

calibre's own `numeric_version` and `__version__` stay exactly calibre's.
Plugins check them and the database schema is keyed off them, so they are
not the fork's to change; they say which calibre this is built on, and the
macOS Get Info string and the release notes state it.

Minutes each. The Linux script has been run in a bare `ubuntu:22.04`
container (four and a half minutes, most of it xz); the macOS one on a Mac.
The workflow runs all of them on plain hosted runners. Downloads are kept in
`.calibre-zen/upstream/`.

### The upstream mirror

Every calibre release this project has seen is copied into a release of
this repository, tagged `upstream-<version>` and marked pre-release so it
never shows as calibre-zen's "latest": the six files upstream publishes
(two Linux `.txz`, the `.dmg`, the `.msi`, the portable installer and the
source tarball), a `SHA256SUMS`, and a body that logs each file's size,
sha256, which published digest it was checked against and where the bytes
came from. Nothing is modified. The package scripts fetch from there first.

`packaging/upstream-mirror.py` does it, and
`.github/workflows/zen-upstream-mirror.yml` runs it daily against upstream's
latest release, so a new calibre is mirrored within a day of shipping and
before GitHub loses the previous one's files. The workflow can also be
dispatched with a version. It is idempotent: a release that has every file
is left alone. Digests come from the GitHub release while it still has
assets, and from `upstream.json` for the version the fork pins; a file with
neither (the source tarball of an old release) is recorded as "computed
here". The schedule only runs from the default branch.

Mirroring is not adopting. The pin moves only when we take an upstream release.

### Taking an upstream release

Follow [Update the upstream calibre release](docs/guides/updating-upstream-calibre.md) for the source merge, installer digests, matching-runtime tests, and pull request checks.

### Per platform

**Linux.** The `.txz` unpacks to `calibre-zen/`. `calibre-zen` at the top
starts the GUI; `zen-bin/` holds one wrapper per tool, prefixed as
`calibre.linux.path_name()` prefixes them (`zen-calibredb`,
`zen-ebook-convert`, ...), so `zen-bin` can go on `PATH` beside a normal
calibre. The upstream names inside the tree are kept, because calibre spawns
its helpers by basename. Both x86_64 and arm64, since upstream ships both.

`install-zen.sh` is also in the archive and attached to each release. It can
download the latest Linux archive or install one already downloaded beside its
`.sha256` file. It checks the digest, extracts into a temporary folder, and
checks the launchers before moving the folder into place. The Linux CI job
installs its built archive this way and runs `zen-calibredb --version`.

The Flatpak wraps that same `.txz`. Its desktop entries and icons are generated
by calibre-zen's Linux postinstall step, then renamed to the Flatpak app id.
It uses the same file and device permissions as calibre's Flatpak so libraries
and readers remain available. Its launcher reads the native calibre-zen config
directory, including installed plugins, instead of starting with a separate
Flatpak config. The release workflow attaches the bundle to the GitHub
release. Flathub is not part of this packaging workflow.

**macOS.** The bundle's executable is a shell script that sets the two
variables and execs `Contents/MacOS/calibre`; everything calibre spawns from
there inherits them. `Info.plist` gets the fork's name, bundle id
`io.github.purplecandy.calibre-zen` and URL scheme; `CFBundleIconName` is
removed, because it points into `Assets.car`, which cannot be rebuilt
without Xcode, and left in place it wins over `CFBundleIconFile` and the
Dock shows calibre's icon. The icon is rendered from `imgsrc/calibre.svg`
by `render_icon.py`, which also gives it the shape macOS expects and does not
apply for you: Apple's template is a rounded square of 824 points on a
1024-point canvas, corner radius 185.4, with a soft shadow beneath, and a
full-bleed square artwork placed as-is sits in Launchpad as a hard square
among rounded ones. The bundle's executable is a small compiled launcher
(`launcher.c`), not a script: LaunchServices refuses to start a quarantined
bundle whose executable is a shell script, with "The application can't be
opened", before Gatekeeper is consulted, so notarization passes and the
double-click still fails. It never shows on the machine that built the
bundle, where nothing is quarantined; test downloads on another Mac. Signing is covered below; unsigned builds are sealed
ad hoc with `--deep`, because the main executable's own signature seals a
hash of `Info.plist` and rewriting the plist invalidates it too. The result
ships as a `.dmg`, because a `.zip` unpacked
by Archive Utility can lose the frameworks' symlinks and the extended
attributes the signature is sealed against. Upstream's bundle is universal,
so one build covers Intel and Apple Silicon.

**Windows.** Upstream's `.msi` is unpacked with an administrative install
(`msiexec /a`), which extracts files and registers nothing; the read-only
attribute it leaves on everything is cleared. Three launchers built from
`launcher.c` with MSVC sit at the top of the tree, `calibre-zen.exe`,
`zen-ebook-viewer.exe` and `zen-ebook-edit.exe`, each embedding the icon and
version info; each sets the two variables and runs its frozen target with
the same arguments. They are what the Start menu, the desktop and the Run
dialog point at; the tools in `zen-bin\` are `.cmd` wrappers. Four outputs
from that one tree:

- **`.msi`**, built with WiX 5 from `wix-template.xml`, which is upstream's
  own template with the fork's identity: its own `UpgradeCode` (so it
  upgrades itself and never calibre), its own folder under Program Files,
  Start menu folder and registry keys, `zen-bin\` on `PATH` rather than the
  folder holding `calibre.exe`, Run-dialog entries for the three launchers
  only, and no `calibre://` handler. `wix.py` walks the staged tree and
  writes one component per file, as upstream's `bypy/windows/wix.py` does.
  Installing a newer `.msi` over an older one is the upgrade path.
- **Portable installer `.exe`**: upstream's `portable-installer.cpp` and
  `XUnzip.cpp`, compiled here, with the folder zipped by `portable_zip.py`
  (deflate; upstream lzip-compresses a stored zip and links easylzma, which
  we do not have) embedded as a resource. It unpacks **Calibre Zen
  Portable**, upstream's portable layout under the fork's folder name: three
  `-portable.exe` launchers (`launcher.c` in portable mode, setting
  `CALIBRE_PORTABLE_BUILD` and pointing settings at `Calibre Settings\`), the
  program in `Calibre\`, the library in `Calibre Library\`. Running a newer
  installer over an existing folder upgrades it and keeps the data.
- **`.zip`** anyone can unpack.
- **`.msix`** for the **Microsoft Store**, which signs packages itself, so
  no certificate is needed for Windows. The MSIX is the same tree plus
  `AppxManifest.xml` and the logo set, all rendered from `imgsrc/calibre.svg`
  by `render_assets.py` with the bundle's Qt and Pillow.

With `CALIBRE_ZEN_INSTALL_TEST=1` (CI sets it) the script also installs the
`.msi` per machine, runs the fork's identity check through the installed
`zen-bin\zen-calibre-debug.cmd`, uninstalls it and checks the folder is
gone; then runs the portable installer into a temp folder and checks the
layout and that calibre reports itself portable with settings in the right
place. WiX is a .NET global tool, installed by the script if missing, and
pinned because its extensions must match it exactly.
The Store identity (`Package/Identity/Name`, `Publisher`,
`PublisherDisplayName`) is copied from Partner Center into
`packaging/windows/msix.json` and must match exactly. The package version is
`zen_version` plus `.0`, four parts with a 0 last as the Store requires, and
a resubmission bumps `zen_version`.
The app declares `runFullTrust`, as every classic desktop app in the Store
does: calibre spawns workers, opens named pipes and talks to devices. Two
things MSIX changes at runtime, both already accounted for: the install
folder is read-only, which the no-writes check guarantees, and
`%APPDATA%\calibre-zen` is redirected into the package's own data area, so
uninstalling removes settings (the library, wherever the user put it, is
untouched). To sideload the `.msix` for testing, sign it with a self-signed
certificate whose subject equals the manifest's `Publisher` and trust that
certificate on the test machine; the Store handles signing for everyone else.

### Signing

**macOS** is signed and notarized when the credentials are present, and
built unsigned when they are not, so a fork of this repo with no secrets
still gets a package. `packaging/macos/sign.py` does the work: an inside-out
walk that signs nested code before the bundle containing it (Apple documents
`--deep` as a repair tool, not a way to sign for distribution), hardened
runtime with calibre's entitlements, then a notarization ticket stapled to
the **bundle**, so it survives being dragged out of the image, and a second
one on the **image**, because macOS assesses a quarantined disk image when
it is opened and refuses a signed but unnotarized one before anyone reaches
the app inside. It reads everything from the environment; the variables are
listed at the top of the file. Locally:

```bash
CALIBRE_ZEN_SIGN_IDENTITY='Developer ID Application: …' CALIBRE_ZEN_NOTARY_KEY=… \
CALIBRE_ZEN_NOTARY_KEY_ID=… CALIBRE_ZEN_NOTARY_ISSUER=… CALIBRE_ZEN_NOTARIZE=1 \
  packaging/macos/package.sh
```

In CI the same code runs off six repository secrets: `MACOS_CERT_P12` and
`MACOS_CERT_PASSWORD` (the Developer ID certificate, base64), `MACOS_SIGN_IDENTITY`,
`MACOS_NOTARY_KEY` (the App Store Connect `.p8`, base64), `MACOS_NOTARY_KEY_ID`
and `MACOS_NOTARY_ISSUER`. The certificate is imported into a keychain that
exists only for that job and is deleted afterwards.

**Windows** goes through the Microsoft Store, which signs the `.msix` on
submission; no certificate of ours is involved. The `.msi`, the portable
installer and the `.zip` are unsigned and SmartScreen warns about them until
they build a reputation; the `.exe` files inside are upstream's, signed by
Kovid Goyal, except the launchers we build.

**Linux** has nothing to sign.

## Updating

The channel from a push to a user's machine, and what each part promises:

1. **One version, one place.** `zen_version` in `src/calibre/constants.py`
   is bumped and the commit lands on `zen`; a `v<zen_version>` tag drafts the
   release. Nothing else is edited by hand to make one.
2. **The release publishes its own feed.** The release job writes
   `latest.json` beside the packages -- the zen and calibre versions, the
   release page, every file with its sha256 and size -- and GitHub serves the
   newest *published* release's copy at

       https://github.com/purplecandy/calibre-zen/releases/latest/download/latest.json

   A draft is not "latest" until it is published, and the `upstream-<version>`
   mirror entries are pre-releases, so neither can announce itself.
3. **The app reads only our releases.** `src/calibre_zen/update.py` points
   calibre's daily check at that feed. The status bar and the dialog name the
   fork's release and Get update opens its page. Nothing on a user's machine
   ever contacts upstream about versions.
4. **The app installs it.** The dialog downloads the package for this
   install, checks it against the feed's sha256 and size, and on **Install
   and restart** quits and hands over to a helper: the `.msi` runs
   `msiexec /passive` over the old one, the portable installer upgrades the
   Calibre Zen Portable folder it is given, and on macOS the new app, copied
   beside the old one before quitting, is swapped in with two renames. A copy
   that something else updates, the Store, Homebrew or Flatpak, is pointed
   there instead, and the `.txz` is replaced by hand as calibre's is.
   `src/calibre_zen/README.md` has the details.

Not done, and recorded here rather than implied: package-manager channels
(winget, Homebrew tap, Flathub), delta updates, and a signed feed. The feed
and the packages are trusted on GitHub's TLS and the release's own digests,
plus the Developer ID team on macOS.

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

Because the packages run the fork's own `constants.py`, every row above is
simply true at runtime; nothing is patched in after the fact.

### Command-line tools

Inside the installation the executables keep upstream's names. calibre shells
out to `calibre-parallel`, `ebook-convert` and friends **by basename**
(`utils/ipc/launch.py` resolves them against `sys.executables_location`), so
renaming them there would mean chasing every call site, and getting one wrong
is a runtime failure inside a worker nobody is watching.

Only what reaches `PATH` is prefixed, because that is the only place a
normally-installed calibre can be collided with:

```
calibre-zen        the GUI
zen-calibredb      -> <install>/calibredb
zen-ebook-convert  -> <install>/ebook-convert
zen-calibre-server -> <install>/calibre-server
…
```

`calibre.linux.path_name()` is the single rule, and `zen-bin/` in the Linux
and Windows packages follows it. On macOS nothing is put on `PATH` at all --
upstream does not either. Running `Contents/MacOS/calibredb` directly gets
you stock calibre's identity, exactly as it would in a stock install.

## Testing

There is no build, so there is no build to break; what breaks is Python at
import time, or behaviour. `zen ci` (`.github/workflows/zen-ci.yml`) runs on
every push and pull request, in a few minutes, and answers three questions:

1. **Does it lint?** `ruff check` over the whole tree with the repo's own
   `pyproject.toml` (upstream is clean at a release tag, so anything reported
   is ours), `ruff format --check` over `src/calibre_zen` and `packaging`,
   and shellcheck over the launchers and package scripts. The ruff version is
   pinned in the workflow; run the same one locally with `uvx ruff@<version>`.
2. **Does it compile?** Every `.py` under `src/`, byte-compiled by the pinned
   calibre release's own interpreter, which is the one a package ships with.
   A syntax error anywhere fails in under a minute.
3. **Does it work?** `./zen-test`: this fork's unit tests and an end-to-end
   run of the real main window, offscreen, on a real library -- see
   `src/calibre_zen/README.md`, "Tests". On the runner it uses the same
   Linux release binary a package wraps, fetched and verified by
   `.github/actions/calibre-runtime`, which also owns the list of Qt runtime
   libraries the package workflow installs.

Locally, `./zen-test` finds `calibre.app` on macOS or `calibre-debug` on PATH,
insists the version matches `src/calibre/constants.py`, and runs in about
five seconds after the first launch has compiled the forms.

`zen package` is the slower check and runs only on pushes to `zen` and on
tags: it builds each platform's package and smoke-tests it headless.

## The fork's edits to upstream files

All marked `# calibre-zen:` so a merge conflict is obvious.

| file | change |
| --- | --- |
| `src/calibre/constants.py` | `__appname__`; `CALIBRE_ZEN_PACKAGED` turns `is_running_from_develop` off |
| `src/calibre/utils/ipc/__init__.py` | the IPC socket derived from `__appname__` |
| `src/calibre/linux.py` | `path_name()`, `desktop_id()`: prefixed PATH names and desktop ids |
| `src/calibre/gui2/__init__.py` | the overlay's entry point after `PaletteManager` |
| `setup/install.py` | also copies `.qss`, `.svg`, `.ttf` out of `src/` |
| `bypy/macos/__main__.py` | bundle identity, for the day a real build is wanted |

## If a real build is ever needed

calibre's own build system is `bypy`, a separate repository. It compiles all
~71 dependencies from source, Qt and Chromium included, then the program, on
a jammy chroot for Linux and inside QEMU virtual machines for macOS and
Windows. Its author keeps those machines, and the compiled dependency tree
inside them, between releases; on hosted CI the tree has to be rebuilt or
stored externally, and rebuilding does not fit in one six-hour job. The
`ci-linux` branch holds the experiments that established how far it gets
and how a run can resume from a cache. None of that is needed while the
fork changes only Python, which is the fork's rule.

## Open items

- **Upstream's inner `.exe` icons.** `calibre-zen.exe` carries the fork's
  icon; `calibre.exe`, `ebook-viewer.exe` and the rest inside the package
  still carry calibre's, and show it in the taskbar while running. Replacing
  those means re-signing upstream's executables or regenerating the `.ico`
  resources in them; not done.
- **The installer's pictures.** The `.msi` dialogs show upstream's
  `icons/wix-banner.bmp` and `wix-dialog.bmp`, and the portable installer
  carries the app icon where upstream has a separate `install.ico`. The
  fork's own art for both is not drawn yet.
- **A URL scheme.** The macOS bundle registers `calibre-zen://`, but the GUI
  only answers to `calibre://` (`gui2/ui.py`), so the `.msi` registers no
  scheme at all: taking `calibre://` would take it from calibre. Either the
  fork learns its own scheme or the macOS registration goes.
- **A Linux installer.** The `.txz` unpacks anywhere; `calibre_postinstall`
  (the fork's `linux.py`) should create the `.desktop` entries and `PATH`
  links under the prefixed names, but has not been run from a package yet.
- **`oeb/reader.py`** stamps `[http://{appname}-ebook.com]` into converted
  books, which for this fork is a URL that does not exist. Cosmetic, but it
  ends up inside people's files.

## Upstream

This fork tracks upstream **release tags** and merges on a cycle. The
identity patch is narrow on purpose and every hunk is marked `calibre-zen:`
so a conflict is obvious. The styling overlay in `src/calibre_zen/` touches
no upstream file at all; see `src/calibre_zen/README.md`.

calibre is GPL v3 and so is this. Kovid Goyal's copyright notices stay where
they are: the fork's name is added to them, never substituted.
