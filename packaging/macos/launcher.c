/*
 * Contents/MacOS/calibre-zen: start calibre's frozen binary on this fork's
 * Python.
 *
 * The bundle is calibre's own with src/ laid beside Contents/Resources/
 * resources; the frozen launcher reads CALIBRE_DEVELOP_FROM and imports from
 * there instead of its own bytecode, and CALIBRE_ZEN_PACKAGED tells the fork's
 * constants.py not to rebuild forms and icons on launch.
 *
 * This used to be a three-line shell script, which notarizes and passes
 * spctl, and then fails at the double-click: Gatekeeper wants the process it
 * launches to be a signed Mach-O the bundle's seal covers, and a script's
 * interpreter is /bin/sh. A compiled launcher is signed with the hardened
 * runtime and entitlements like every other executable in MacOS/.
 *
 * The viewer and the editor are apps nested inside the bundle
 * (ebook-viewer.app, ebook-edit.app, headless.app), and what opens a book from
 * Finder is the nested viewer, started by LaunchServices rather than by this
 * launcher. Without variables of its own it runs calibre's unmodified viewer.
 * So each nested app's stub executable is built from this same source with
 * -DZEN_NESTED, the program it stands for (-DZEN_EXE_NAME) and the way from its
 * own MacOS directory back to the bundle's (-DZEN_REL_PATH). Like upstream's
 * stub, it leaves argv alone.
 *
 * Built by packaging/macos/package.sh, universal:
 *   clang -O2 -arch arm64 -arch x86_64 -o Contents/MacOS/calibre-zen launcher.c
 */
#include <libgen.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#ifndef ZEN_EXE_NAME
#define ZEN_EXE_NAME "calibre" /* the frozen program to start, in the bundle's MacOS directory */
#endif
#ifndef ZEN_REL_PATH
#define ZEN_REL_PATH "." /* from this executable's directory to the bundle's MacOS directory */
#endif

static void fail(const char *what) {
    fprintf(stderr, "calibre-zen could not start: %s\n", what);
    exit(1);
}

int main(int argc, char **argv) {
    char exe[PATH_MAX], self[PATH_MAX], dir[PATH_MAX], macos[PATH_MAX], path[PATH_MAX], src[PATH_MAX], target[PATH_MAX];
    uint32_t n = sizeof(exe);
    (void)argc;

    if (_NSGetExecutablePath(exe, &n) != 0) fail("it could not find its own location.");
    if (realpath(exe, self) == NULL) fail("its own path does not resolve.");
    strlcpy(dir, dirname(self), sizeof(dir)); /* this app's Contents/MacOS */

    /* The bundle's Contents/MacOS: this directory itself, or the way back to it. */
    if (snprintf(macos, sizeof(macos), "%s/%s", dir, ZEN_REL_PATH) >= (int)sizeof(macos)) fail("path too long.");

    if (snprintf(path, sizeof(path), "%s/../Resources/src", macos) >= (int)sizeof(path)) fail("path too long.");
    if (realpath(path, src) == NULL || access(src, R_OK) != 0) fail("Contents/Resources/src is missing. The bundle is incomplete.");

    if (snprintf(target, sizeof(target), "%s/%s", macos, ZEN_EXE_NAME) >= (int)sizeof(target)) fail("path too long.");
    if (access(target, X_OK) != 0) fail("the program this launcher starts is missing from Contents/MacOS. The bundle is incomplete.");

    if (setenv("CALIBRE_DEVELOP_FROM", src, 1) != 0) fail("setting CALIBRE_DEVELOP_FROM.");
    if (setenv("CALIBRE_ZEN_PACKAGED", "1", 1) != 0) fail("setting CALIBRE_ZEN_PACKAGED.");

#ifndef ZEN_NESTED
    argv[0] = target;
#endif
    execv(target, argv);
    perror("calibre-zen: exec calibre");
    return 1;
}
