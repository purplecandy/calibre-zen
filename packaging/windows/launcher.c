/*
 * calibre-zen.exe: start calibre's frozen calibre.exe on this fork's Python.
 *
 * The package is calibre's own Windows build with src/ laid beside
 * app\resources; the frozen launcher reads CALIBRE_DEVELOP_FROM and imports
 * from there instead of its own bytecode, and CALIBRE_ZEN_PACKAGED tells the
 * fork's constants.py not to rebuild forms and icons on launch. A .cmd can set
 * both, but a .cmd cannot be signed, cannot carry an icon, and cannot be an
 * MSIX entry point. This can.
 *
 * It sets the two variables, runs <its own directory>\calibre.exe with the
 * same arguments it was given, waits, and exits with calibre's exit code.
 * Everything calibre spawns inherits the environment.
 *
 * Built by packaging\windows\package.ps1 with MSVC:
 *   rc launcher.rc && cl /O2 /MT launcher.c launcher.res /link /SUBSYSTEM:WINDOWS
 */
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <string.h>
#include <wchar.h>

#define CAP 32768

static void fail(const wchar_t *what) {
    wchar_t msg[CAP];
    DWORD err = GetLastError();
    wcscpy_s(msg, CAP, L"calibre-zen could not start: ");
    wcscat_s(msg, CAP, what);
    if (err) {
        wchar_t *sys = NULL;
        if (FormatMessageW(FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
                           NULL, err, 0, (LPWSTR)&sys, 0, NULL) && sys) {
            wcscat_s(msg, CAP, L"\n\n");
            wcscat_s(msg, CAP, sys);
            LocalFree(sys);
        }
    }
    MessageBoxW(NULL, msg, L"calibre-zen", MB_ICONERROR | MB_OK);
    ExitProcess(1);
}

/* The arguments as given, i.e. GetCommandLineW() with its first token (this
 * executable, possibly quoted) removed. */
static const wchar_t *own_arguments(void) {
    const wchar_t *p = GetCommandLineW();
    if (*p == L'"') {
        p++;
        while (*p && *p != L'"') p++;
        if (*p == L'"') p++;
    } else {
        while (*p && *p != L' ' && *p != L'\t') p++;
    }
    while (*p == L' ' || *p == L'\t') p++;
    return p;
}

int WINAPI wWinMain(HINSTANCE hInstance, HINSTANCE hPrev, PWSTR pCmdLine, int nCmdShow) {
    static wchar_t dir[CAP], src[CAP], target[CAP], cmdline[CAP];
    (void)hInstance; (void)hPrev; (void)pCmdLine; (void)nCmdShow;

    DWORD n = GetModuleFileNameW(NULL, dir, CAP);
    if (n == 0 || n >= CAP) fail(L"it could not find its own location.");
    wchar_t *slash = wcsrchr(dir, L'\\');
    if (!slash) fail(L"its own path has no directory.");
    *slash = L'\0';

    wcscpy_s(src, CAP, dir);
    wcscat_s(src, CAP, L"\\app\\src");
    if (GetFileAttributesW(src) == INVALID_FILE_ATTRIBUTES)
        fail(L"the app\\src directory is missing beside it. The package is incomplete.");

    wcscpy_s(target, CAP, dir);
    wcscat_s(target, CAP, L"\\calibre.exe");
    if (GetFileAttributesW(target) == INVALID_FILE_ATTRIBUTES)
        fail(L"calibre.exe is missing beside it. The package is incomplete.");

    if (!SetEnvironmentVariableW(L"CALIBRE_DEVELOP_FROM", src)) fail(L"setting CALIBRE_DEVELOP_FROM.");
    if (!SetEnvironmentVariableW(L"CALIBRE_ZEN_PACKAGED", L"1")) fail(L"setting CALIBRE_ZEN_PACKAGED.");

    /* CreateProcess may modify the command line buffer, so it is our own copy. */
    wcscpy_s(cmdline, CAP, L"\"");
    wcscat_s(cmdline, CAP, target);
    wcscat_s(cmdline, CAP, L"\"");
    const wchar_t *args = own_arguments();
    if (*args) {
        wcscat_s(cmdline, CAP, L" ");
        wcscat_s(cmdline, CAP, args);
    }

    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));
    if (!CreateProcessW(target, cmdline, NULL, NULL, FALSE, 0, NULL, dir, &si, &pi))
        fail(L"launching calibre.exe.");
    CloseHandle(pi.hThread);
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD code = 0;
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hProcess);
    return (int)code;
}
