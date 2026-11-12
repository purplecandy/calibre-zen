/*
 * The bundle's launchers: start calibre's frozen binaries on this fork's
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
 * One binary, two jobs, told apart by its own file name:
 *
 *   Contents/MacOS/calibre-zen
 *       The bundle's executable. Starts Contents/MacOS/calibre.
 *
 *   <nested>.app/Contents/MacOS/<program>-placeholder-for-codesigning
 *       The executable of each app calibre nests in the bundle: the viewer,
 *       the editor and the worker. macOS starts these itself when a book is
 *       opened from Finder, Spotlight or Open With, so nothing has set the
 *       variables above. Upstream's stub (bypy/macos/placeholder.c) starts
 *       <program> and sets nothing, which runs calibre's own Python. This
 *       copy starts the same <program> on the fork's. Beside it is a symlink
 *       called <program> into Contents/MacOS, which is how it finds the real
 *       program and the bundle around it. Like upstream's stub, it leaves
 *       argv alone.
 *
 * calibre itself never goes through a nested stub: it starts the viewer,
 * the editor and its workers by those symlinks, with the variables already
 * in the environment it inherited from the bundle's executable.
 *
 * Built once by packaging/macos/package.sh, universal, and copied over each
 * nested stub:
 *   clang -O2 -arch arm64 -arch x86_64 -o Contents/MacOS/calibre-zen launcher.c
 */
#include <libgen.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define NESTED_SUFFIX "-placeholder-for-codesigning"

static void fail(const char *what) {
    fprintf(stderr, "calibre-zen could not start: %s\n", what);
    exit(1);
}

/* `a/b` into `out`, or fail. */
static void join(char *out, size_t size, const char *a, const char *b) {
    if (snprintf(out, size, "%s/%s", a, b) >= (int)size) fail("path too long.");
}

int main(int argc, char **argv) {
    char exe[PATH_MAX], self[PATH_MAX], dir[PATH_MAX], name[PATH_MAX];
    char link[PATH_MAX], target[PATH_MAX], macos[PATH_MAX], path[PATH_MAX], src[PATH_MAX];
    uint32_t n = sizeof(exe);
    size_t len, suffix = strlen(NESTED_SUFFIX);
    int nested;
    (void)argc;

    if (_NSGetExecutablePath(exe, &n) != 0) fail("it could not find its own location.");
    if (realpath(exe, self) == NULL) fail("its own path does not resolve.");
    /* dirname() and basename() may write into their argument: give each a copy. */
    strlcpy(path, self, sizeof(path));
    strlcpy(dir, dirname(path), sizeof(dir));
    strlcpy(path, self, sizeof(path));
    strlcpy(name, basename(path), sizeof(name));

    len = strlen(name);
    nested = len > suffix && strcmp(name + len - suffix, NESTED_SUFFIX) == 0;
    if (nested) {
        name[len - suffix] = '\0'; /* ebook-viewer-placeholder-for-codesigning -> ebook-viewer */
    } else {
        strlcpy(name, "calibre", sizeof(name));
    }

    /* For the bundle's executable this is MacOS/calibre itself; for a nested
     * stub it is the symlink beside it, resolved into the bundle's MacOS/. */
    join(link, sizeof(link), dir, name);
    if (realpath(link, target) == NULL || access(target, X_OK) != 0)
        fail("the program it starts is missing from Contents/MacOS. The bundle is incomplete.");

    strlcpy(path, target, sizeof(path));
    strlcpy(macos, dirname(path), sizeof(macos));
    join(path, sizeof(path), macos, "../Resources/src");
    if (realpath(path, src) == NULL || access(src, R_OK) != 0)
        fail("Contents/Resources/src is missing. The bundle is incomplete.");

    if (setenv("CALIBRE_DEVELOP_FROM", src, 1) != 0) fail("setting CALIBRE_DEVELOP_FROM.");
    if (setenv("CALIBRE_ZEN_PACKAGED", "1", 1) != 0) fail("setting CALIBRE_ZEN_PACKAGED.");

    if (!nested) argv[0] = target;
    execv(target, argv);
    perror("calibre-zen: exec");
    return 1;
}
