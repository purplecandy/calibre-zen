/*
 * portable-installer.cpp: the self-extracting installer for Calibre Zen
 * Portable.
 *
 * calibre-zen's copy of bypy/windows/portable-installer.cpp, Copyright (C)
 * Kovid Goyal, GPL v3. Two changes, both so it builds with nothing but MSVC
 * and the Windows SDK, as package.ps1 does:
 *
 *   - The payload is a plain deflate .zip embedded as the resource "extra",
 *     opened straight from memory by XUnzip. Upstream lzip-compresses a
 *     stored zip and links easylzma to undo that; we have no easylzma and a
 *     deflate zip is about the same size.
 *   - The names: the folder is "Calibre Zen Portable" and the launchers are
 *     calibre-zen-portable.exe, zen-ebook-viewer-portable.exe and
 *     zen-ebook-edit-portable.exe, so an install can sit beside calibre's own
 *     Calibre Portable. Inside the folder the layout is upstream's, because
 *     calibre's portable mode (CALIBRE_PORTABLE_BUILD, get_portable_base) is
 *     built around it: Calibre\ holds the program, Calibre Library\ and
 *     Calibre Settings\ hold the user's data.
 *
 * Usage: portable-installer.exe [target-folder]. With a folder it installs or
 * upgrades there without asking; without one it asks.
 */

#ifndef UNICODE
#define UNICODE
#endif

#ifndef _UNICODE
#define _UNICODE
#endif

#include <Windows.h>
#include <Shlobj.h>
#include <Shlwapi.h>
#include <Shellapi.h>
#include <Psapi.h>
#include <wchar.h>
#include <stdio.h>
#include <io.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <VersionHelpers.h>

#include "XUnzip.h"

#define BUFSIZE 4096
#define arraysz(x) (sizeof(x) / sizeof(x[0]))

#define PORTABLE_DIR L"Calibre Zen Portable"
#define UNPACK_DIR L"_unpack_calibre_zen_portable"
#define MAIN_LAUNCHER L"calibre-zen-portable.exe"
#define VIEWER_LAUNCHER L"zen-ebook-viewer-portable.exe"
#define EDITOR_LAUNCHER L"zen-ebook-edit-portable.exe"

// The frozen binaries keep upstream's names inside Calibre\, so these are
// what a running install shows up as.
static const LPCWSTR calibre_processes[] = {L"calibre.exe", L"calibre-parallel.exe", L"ebook-viewer.exe", L"ebook-edit.exe"};

// Error handling {{{

static void
show_error(LPCWSTR msg) {
    MessageBeep(MB_ICONERROR);
    MessageBox(NULL, msg, L"Error", MB_OK | MB_ICONERROR);
}

static void
show_detailed_error(LPCWSTR preamble, LPCWSTR msg, int code) {
    LPWSTR buf;
    buf = (LPWSTR)LocalAlloc(LMEM_ZEROINIT, sizeof(WCHAR) * (wcslen(msg) + wcslen(preamble) + 80));

    _snwprintf_s(buf, LocalSize(buf) / sizeof(WCHAR), _TRUNCATE, L"%s\r\n  %s (Error Code: %d)\r\n", preamble, msg, code);

    show_error(buf);
    LocalFree(buf);
}

static void
show_zip_error(LPCWSTR preamble, LPCWSTR msg, ZRESULT code) {
    LPWSTR buf;
    char msgbuf[1024] = {0};

    FormatZipMessage(code, msgbuf, 1024);

    buf = (LPWSTR)LocalAlloc(LMEM_ZEROINIT, sizeof(WCHAR) * (wcslen(preamble) + wcslen(msg) + 1100));

    _snwprintf_s(buf, LocalSize(buf) / sizeof(WCHAR), _TRUNCATE, L"%s\r\n  %s (Error: %S)\r\n", preamble, msg, msgbuf);

    show_error(buf);
    LocalFree(buf);
}

static void
show_last_error(LPCWSTR preamble) {
    WCHAR *msg = NULL;
    DWORD dw = GetLastError();

    FormatMessage(
        FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
        NULL,
        dw,
        MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
        (LPWSTR)&msg,
        0,
        NULL);

    show_detailed_error(preamble, msg, (int)dw);
}

// }}}

// Load and extract data {{{

static BOOL
load_data(LPVOID *data, DWORD *sz) {
    HRSRC rsrc;
    HGLOBAL h;

    rsrc = FindResourceW(NULL, L"extra", L"extra");
    if (rsrc == NULL) {
        show_last_error(L"Failed to find portable data in exe");
        return false;
    }

    h = LoadResource(NULL, rsrc);
    if (h == NULL) {
        show_last_error(L"Failed to load portable data from exe");
        return false;
    }

    *data = LockResource(h);
    if (*data == NULL) {
        show_last_error(L"Failed to lock portable data in exe");
        return false;
    }

    *sz = SizeofResource(NULL, rsrc);
    if (*sz == 0) {
        show_last_error(L"Failed to get size of portable data in exe");
        return false;
    }

    return true;
}

static BOOL
unzip(HZIP zipf, int nitems, IProgressDialog *pd) {
    int i = 0;
    ZRESULT res;
    ZIPENTRYW ze;

    for (i = 0; i < nitems; i++) {
        res = GetZipItem(zipf, i, &ze);
        if (res != ZR_OK) {
            show_zip_error(L"Failed to get zip item", L"", res);
            return false;
        }

        res = UnzipItem(zipf, i, ze.name, 0, ZIP_FILENAME);
        if (res != ZR_OK) {
            show_zip_error(L"Failed to extract zip item (is your disk full?):", ze.name, res);
            return false;
        }

        pd->SetLine(2, ze.name, true, NULL);
        pd->SetProgress(i, nitems);
    }

    return true;
}

static BOOL
extract(LPVOID cdata, DWORD csz) {
    BOOL ret = true;
    HZIP zipf = 0;
    ZIPENTRYW ze;
    ZRESULT res;
    int nitems;
    HRESULT hr;
    IProgressDialog *pd = NULL;

    hr = CoCreateInstance(CLSID_ProgressDialog, NULL, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&pd));

    if (FAILED(hr)) {
        show_error(L"Failed to create progress dialog");
        return false;
    }
    pd->SetTitle(L"Extracting " PORTABLE_DIR);
    pd->SetLine(1, L"Copying files...", true, NULL);
    pd->StartProgressDialog(NULL, NULL, PROGDLG_NORMAL | PROGDLG_AUTOTIME | PROGDLG_NOCANCEL, NULL);

    // The resource is the zip itself, read in place.
    zipf = OpenZip(cdata, csz, ZIP_MEMORY);
    if (zipf == 0) {
        show_last_error(L"Failed to open zipped portable data");
        ret = false;
        goto end;
    }

    res = GetZipItem(zipf, -1, &ze);
    if (res != ZR_OK) {
        show_zip_error(L"Failed to get count of items in portable data", L"", res);
        ret = false;
        goto end;
    }
    nitems = ze.index;

    if (!unzip(zipf, nitems, pd)) {
        ret = false;
        goto end;
    }
end:
    if (zipf != 0) CloseZip(zipf);
    pd->StopProgressDialog();
    pd->Release();
    return ret;
}

// }}}

// Find the portable folder and install/upgrade into it {{{

static BOOL
directory_exists(LPCWSTR path) {
    if (_waccess_s(path, 0) == 0) {
        struct _stat status;
        _wstat(path, &status);
        return (status.st_mode & S_IFDIR) != 0;
    }

    return FALSE;
}

static BOOL
file_exists(LPCWSTR path) {
    if (_waccess_s(path, 0) == 0) {
        struct _stat status;
        _wstat(path, &status);
        return (status.st_mode & S_IFREG) != 0;
    }

    return FALSE;
}

static LPWSTR
get_directory_from_user() {
    WCHAR name[MAX_PATH + 1] = {0};
    LPWSTR path = NULL;
    PIDLIST_ABSOLUTE ret;

    path = (LPWSTR)calloc(2 * MAX_PATH, sizeof(WCHAR));
    if (path == NULL) {
        show_error(L"Out of memory");
        return NULL;
    }

    int image = 0;
    BROWSEINFO bi = {
        NULL,
        NULL,
        name,
        L"Select the folder where you want to install or update " PORTABLE_DIR,
        BIF_RETURNONLYFSDIRS | BIF_DONTGOBELOWDOMAIN | BIF_USENEWUI,
        NULL,
        NULL,
        image};

    ret = SHBrowseForFolder(&bi);
    if (ret == NULL) { return NULL; }

    if (!SHGetPathFromIDList(ret, path)) {
        show_detailed_error(L"The selected folder is not valid: ", name, 0);
        return NULL;
    }

    return path;
}

static bool
is_dots(LPCWSTR name) {
    return wcscmp(name, L".") == 0 || wcscmp(name, L"..") == 0;
}

static bool
rmtree(LPCWSTR path) {
    SHFILEOPSTRUCTW op;
    WCHAR buf[4 * MAX_PATH + 2] = {0};

    if (GetFullPathName(path, 4 * MAX_PATH, buf, NULL) == 0) return false;

    op.hwnd = NULL;
    op.wFunc = FO_DELETE;
    op.pFrom = buf;
    op.pTo = NULL;
    op.fFlags = FOF_NOCONFIRMATION | FOF_NOERRORUI | FOF_SILENT | FOF_NOCONFIRMMKDIR;
    op.fAnyOperationsAborted = false;
    op.hNameMappings = NULL;
    op.lpszProgressTitle = NULL;

    return SHFileOperationW(&op) == 0;
}

static BOOL
find_portable_dir(LPCWSTR base, LPWSTR *result, BOOL *existing) {
    WCHAR buf[4 * MAX_PATH] = {0};

    _snwprintf_s(buf, 4 * MAX_PATH, _TRUNCATE, L"%s\\" MAIN_LAUNCHER, base);
    *existing = true;

    if (file_exists(buf)) {
        *result = _wcsdup(base);
        if (*result == NULL) {
            show_error(L"Out of memory");
            return false;
        }
        return true;
    }

    WIN32_FIND_DATA fdFile;
    HANDLE hFind = NULL;
    _snwprintf_s(buf, 4 * MAX_PATH, _TRUNCATE, L"%s\\*", base);

    if ((hFind = FindFirstFileEx(buf, FindExInfoStandard, &fdFile, FindExSearchLimitToDirectories, NULL, 0)) != INVALID_HANDLE_VALUE) {
        do {
            if (is_dots(fdFile.cFileName)) continue;

            if (fdFile.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
                _snwprintf_s(buf, 4 * MAX_PATH, _TRUNCATE, L"%s\\%s\\" MAIN_LAUNCHER, base, fdFile.cFileName);
                if (file_exists(buf)) {
                    *result = _wcsdup(buf);
                    if (*result == NULL) {
                        show_error(L"Out of memory");
                        return false;
                    }
                    PathRemoveFileSpec(*result);
                    FindClose(hFind);
                    return true;
                }
            }
        } while (FindNextFile(hFind, &fdFile));
        FindClose(hFind);
    }

    *existing = false;
    _snwprintf_s(buf, 4 * MAX_PATH, _TRUNCATE, L"%s\\" PORTABLE_DIR, base);
    if (!CreateDirectory(buf, NULL) && GetLastError() != ERROR_ALREADY_EXISTS) {
        show_last_error(L"Failed to create " PORTABLE_DIR L" folder");
        return false;
    }
    *result = _wcsdup(buf);
    if (*result == NULL) {
        show_error(L"Out of memory");
        return false;
    }

    return true;
}

static LPWSTR
make_unpack_dir() {
    WCHAR buf[4 * MAX_PATH] = {0};
    LPWSTR ans = NULL;

    if (directory_exists(UNPACK_DIR)) rmtree(UNPACK_DIR);

    if (!CreateDirectory(UNPACK_DIR, NULL) && GetLastError() != ERROR_ALREADY_EXISTS) {
        show_last_error(L"Failed to create temporary folder to unpack into");
        return ans;
    }

    if (!GetFullPathName(UNPACK_DIR, 4 * MAX_PATH, buf, NULL)) {
        show_last_error(L"Failed to resolve path");
        return NULL;
    }

    ans = _wcsdup(buf);
    if (ans == NULL) show_error(L"Out of memory");
    return ans;
}

static BOOL
move_launcher(LPCWSTR name) {
    WCHAR from[4 * MAX_PATH] = {0}, to[4 * MAX_PATH] = {0}, msg[4 * MAX_PATH] = {0};
    _snwprintf_s(from, 4 * MAX_PATH, _TRUNCATE, PORTABLE_DIR L"\\%s", name);
    _snwprintf_s(to, 4 * MAX_PATH, _TRUNCATE, L"..\\%s", name);
    if (MoveFileEx(from, to, MOVEFILE_REPLACE_EXISTING) == 0) {
        _snwprintf_s(msg, 4 * MAX_PATH, _TRUNCATE, L"Failed to move %s, make sure calibre is not running", name);
        show_last_error(msg);
        return false;
    }
    return true;
}

static BOOL
move_program() {
    if (!move_launcher(MAIN_LAUNCHER)) return false;
    if (!move_launcher(VIEWER_LAUNCHER)) return false;
    if (!move_launcher(EDITOR_LAUNCHER)) return false;

    if (directory_exists(L"..\\Calibre")) {
        if (!rmtree(L"..\\Calibre")) {
            show_error(L"Failed to delete the Calibre program folder. Make sure calibre is not running.");
            return false;
        }
    }

    if (MoveFileEx(PORTABLE_DIR L"\\Calibre", L"..\\Calibre", 0) == 0) {
        Sleep(4000); // Sleep and try again
        if (MoveFileEx(PORTABLE_DIR L"\\Calibre", L"..\\Calibre", 0) == 0) {
            show_last_error(
                L"Failed to move calibre program folder. This is usually caused by an antivirus program or a file sync program like DropBox. Turn them off "
                L"temporarily and try again. Underlying error: ");
            return false;
        }
    }

    if (!directory_exists(L"..\\Calibre Library")) { MoveFileEx(PORTABLE_DIR L"\\Calibre Library", L"..\\Calibre Library", 0); }

    if (!directory_exists(L"..\\Calibre Settings")) { MoveFileEx(PORTABLE_DIR L"\\Calibre Settings", L"..\\Calibre Settings", 0); }

    return true;
}
// }}}

static BOOL
find_running_calibre_processes(LPWSTR *running_processes, int *count) {
    DWORD processes[4096], needed, num;
    unsigned int i;
    WCHAR name[4 * MAX_PATH] = L"<unknown>";
    HANDLE h;
    DWORD len;
    LPWSTR fname = NULL;
    BOOL found[arraysz(calibre_processes)] = {FALSE};
    *count = 0;

    if (!EnumProcesses(processes, sizeof(processes), &needed)) return true;
    num = needed / sizeof(DWORD);

    for (i = 0; i < num; i++) {
        if (processes[i] == 0) continue;
        h = OpenProcess(PROCESS_QUERY_INFORMATION, FALSE, processes[i]);
        if (h != NULL) {
            len = GetProcessImageFileNameW(h, name, 4 * MAX_PATH);
            CloseHandle(h);
            if (len != 0) {
                name[len] = 0;
                fname = PathFindFileName(name);
                for (int j = 0; j < arraysz(calibre_processes); j++) {
                    if (!found[j] && wcscmp(fname, calibre_processes[j]) == 0) {
                        found[j] = TRUE;
                        running_processes[*count] = _wcsdup(calibre_processes[j]);
                        (*count)++;
                        break;
                    }
                }
            }
        }
    }

    return *count > 0;
}

static BOOL
ensure_not_running() {
    LPWSTR running_processes[arraysz(calibre_processes)] = {NULL};
    int count = 0;
    WCHAR msg[4 * MAX_PATH] = {0};
    WCHAR *msg_ptr;
    size_t remaining;
    int result;

    while (TRUE) {
        // Reset buffer pointers for each iteration
        msg_ptr = msg;
        remaining = arraysz(msg);
        wmemset(msg, 0, remaining);

        // Check for running processes
        if (!find_running_calibre_processes(running_processes, &count)) return true;

        // Build the message with list of running processes
        int written = _snwprintf_s(msg_ptr, remaining, _TRUNCATE, L"The following calibre processes are currently running:\r\n\r\n");
        if (written > 0) {
            msg_ptr += written;
            remaining -= written;
        }

        for (int i = 0; i < count; i++) {
            written = _snwprintf_s(msg_ptr, remaining, _TRUNCATE, L"  - %s\r\n", running_processes[i]);
            if (written > 0) {
                msg_ptr += written;
                remaining -= written;
            }
        }

        written = _snwprintf_s(
            msg_ptr,
            remaining,
            _TRUNCATE,
            L"\r\nPlease quit calibre before installing or upgrading " PORTABLE_DIR L".\r\n\r\n"
            L"Click 'Retry' after quitting calibre, or 'Abort' to cancel installation.");

        // Show dialog with Retry and Abort buttons
        result = MessageBox(NULL, msg, L"calibre is running", MB_RETRYCANCEL | MB_ICONEXCLAMATION | MB_TOPMOST);

        // Free allocated memory
        for (int i = 0; i < count; i++) {
            if (running_processes[i] != NULL) {
                free(running_processes[i]);
                running_processes[i] = NULL;
            }
        }
        count = 0;

        if (result == IDCANCEL) return false; // User chose to abort
        // If IDRETRY, loop continues to check again
    }

    return true;
}

static void
launch_calibre() {
    STARTUPINFO si;
    PROCESS_INFORMATION pi;

    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    ZeroMemory(&pi, sizeof(pi));


    if (CreateProcess(_wcsdup(MAIN_LAUNCHER), NULL, NULL, NULL, FALSE, CREATE_UNICODE_ENVIRONMENT | CREATE_NEW_PROCESS_GROUP, NULL, NULL, &si, &pi) ==
        0) {
        show_last_error(L"Failed to launch " PORTABLE_DIR);
    }

    // Close process and thread handles.
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
}

void
makedirs(LPWSTR path) {
    WCHAR *p = path;
    while (*p) {
        if ((*p == L'\\' || *p == L'/') && p != path && *(p - 1) != L':') {
            *p = 0;
            CreateDirectory(path, NULL);
            *p = L'\\';
        }
        p++;
    }
    CreateDirectory(path, NULL);
}

int WINAPI
wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, PWSTR pCmdLine, int nCmdShow) {
    (void)hPrevInstance;
    (void)pCmdLine;
    (void)nCmdShow;
    (void)hInstance;
    LPVOID cdata = NULL;
    DWORD csz = 0;
    int ret = 1, argc;
    HRESULT hr;
    LPWSTR tgt = NULL, dest = NULL, *argv, unpack_dir = NULL;
    BOOL existing = false, launch = false, automated = false;
    WCHAR buf[4 * MAX_PATH] = {0}, mb_msg[4 * MAX_PATH] = {0}, fdest[4 * MAX_PATH] = {0};

    if (!load_data(&cdata, &csz)) return ret;
    if (!IsWindows10OrGreater()) {
        show_error(L"Your version of Windows is too old. calibre requires Windows 10 or greater.");
        return ret;
    }

    hr = CoInitialize(NULL);
    if (FAILED(hr)) {
        show_error(L"Failed to initialize COM");
        return ret;
    }

    // Get the target folder for installation
    argv = CommandLineToArgvW(GetCommandLine(), &argc);
    if (argv == NULL) {
        show_last_error(L"Failed to get command line");
        return ret;
    }
    if (argc > 1) {
        tgt = argv[1];
        automated = true;
        if (!directory_exists(tgt)) {
            if (GetFullPathName(tgt, MAX_PATH * 4, fdest, NULL) == 0) {
                show_last_error(L"Failed to resolve target folder");
                goto end;
            }
            makedirs(fdest);
        }

    } else {
        tgt = get_directory_from_user();
        if (tgt == NULL) goto end;
    }

    if (!directory_exists(tgt)) {
        show_detailed_error(L"The specified folder does not exist: ", tgt, 1);
        goto end;
    }

    // Ensure the path to the portable folder is not too long
    do {
        if (!find_portable_dir(tgt, &dest, &existing)) goto end;

        if (GetFullPathName(dest, MAX_PATH * 4, fdest, NULL) == 0) {
            show_last_error(L"Failed to resolve target folder");
            goto end;
        }
        free(dest);
        dest = NULL;

        if (wcslen(fdest) > 58) {
            _snwprintf_s(buf, 4 * MAX_PATH, _TRUNCATE, L"Path to " PORTABLE_DIR L" (%s) too long. It must be less than 59 characters.", fdest);
            if (!existing) RemoveDirectory(fdest);
            show_error(buf);
            tgt = get_directory_from_user();
            if (tgt == NULL) goto end;
        }
    } while (wcslen(fdest) > 58);

    // Confirm the user wants to upgrade
    if (existing && !automated) {
        _snwprintf_s(mb_msg, 4 * MAX_PATH, _TRUNCATE, L"An existing install of " PORTABLE_DIR L" was found at %s. Do you want to upgrade it?", fdest);
        if (MessageBox(NULL, mb_msg, L"Upgrade " PORTABLE_DIR L"?", MB_ICONEXCLAMATION | MB_YESNO | MB_TOPMOST) != IDYES) goto end;
    }

    if (existing) {
        if (!ensure_not_running()) goto end;
    }

    // Make a temp dir to unpack into
    if (!SetCurrentDirectoryW(fdest)) {
        show_detailed_error(L"Failed to change to unzip folder: ", fdest, 0);
        goto end;
    }

    if ((unpack_dir = make_unpack_dir()) == NULL) goto end;
    if (!SetCurrentDirectoryW(unpack_dir)) {
        show_detailed_error(L"Failed to change to unpack folder: ", fdest, 0);
        goto end;
    }

    // Extract files
    if (!extract(cdata, csz)) goto end;

    // Move files from temp dir to the install dir
    if (!move_program()) goto end;

    ret = 0;
    if (!automated) {
        _snwprintf_s(mb_msg, 4 * MAX_PATH, _TRUNCATE, PORTABLE_DIR L" successfully installed to %s. Launch calibre?", fdest);
        launch = MessageBox(NULL, mb_msg, L"Success", MB_ICONINFORMATION | MB_YESNO | MB_TOPMOST) == IDYES;
    }

end:
    if (unpack_dir != NULL) {
        SetCurrentDirectoryW(L"..");
        rmtree(unpack_dir);
        free(unpack_dir);
    }
    CoUninitialize();
    if (launch) launch_calibre();
    return ret;
}
