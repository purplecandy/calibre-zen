# Build the Windows calibre-zen package by wrapping calibre's own installer.
#
# Nothing is compiled. calibre's .msi for the release pinned in
# packaging/upstream.json is downloaded, checked against its published sha256
# and unpacked with an administrative install (msiexec /a: file extraction,
# nothing is registered); this fork's src/ goes beside the install's
# app\resources directory; .cmd launchers that set CALIBRE_DEVELOP_FROM are
# added so the frozen calibre runs the fork's Python instead of its own, and a
# small calibre-zen.exe (launcher.c) does the same for the GUI, because an exe
# can carry an icon, a signature and be an MSIX entry point where a .cmd
# cannot. Forms, icons and bytecode are compiled here, once, so the installed
# tree is never written to.
#
# Four outputs, the same kinds calibre itself releases plus the Store's: a
# .zip anyone can unpack; an .msi built with WiX from upstream's own template
# (wix-template.xml), which installs beside calibre and upgrades itself; a
# portable installer .exe (portable-installer.cpp, upstream's, with a deflate
# payload) that unpacks a Calibre Zen Portable folder; and an .msix for the
# Microsoft Store, which signs it on submission. The Store identity comes
# from msix.json.
#
# Runs on Windows only: the precompile and smoke-test steps execute the
# downloaded binary, MSVC and the Windows SDK build the launchers, the
# installer and the MSIX, and WiX (a .NET tool, installed here if missing)
# builds the .msi. Only the .msix is ever signed: SmartScreen warns about the
# others until they have a reputation.
#
# Usage:  powershell -File packaging\windows\package.ps1
#
# Environment:
#   CALIBRE_ZEN_UPSTREAM_CACHE  where downloads are kept   (.calibre-zen\upstream)
#   CALIBRE_ZEN_BUILD_DIR       staging area, wiped         (build\windows)
#   CALIBRE_ZEN_DIST_DIR        where the outputs land      (dist)
#   CALIBRE_ZEN_INSTALL_TEST=1  also install the .msi (per machine, then
#                               uninstall it) and run the portable installer,
#                               and check what they put on disk. For CI: a
#                               developer's machine should not be installed to.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Say($m) { Write-Host "==> $m" }
function Die($m) { Write-Error "package.ps1: $m"; exit 1 }
function Native { # run a native command, fail on non-zero exit
    param([string]$exe, [string[]]$argv)
    & $exe @argv
    if ($LASTEXITCODE -ne 0) { Die "$exe exited with $LASTEXITCODE" }
}
function RunPy { # run Python source with the bundle's calibre-debug. Through a
    # file: PowerShell strips the inner quotes out of a -c argument on the way
    # to a native exe, and Python then sees os.environ[NAME].
    param([string]$exe, [string]$code)
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("zen-" + [guid]::NewGuid() + ".py")
    [System.IO.File]::WriteAllText($tmp, $code, (New-Object System.Text.UTF8Encoding $false))
    try { Native $exe @('-e', $tmp) } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}

function Write-Sha256([string]$path) { # <file>.sha256 beside it, sha256sum's format
    "$((Get-FileHash -Algorithm SHA256 $path).Hash.ToLower())  $(Split-Path $path -Leaf)" | Set-Content "$path.sha256" -Encoding ASCII
}
function Find-SdkTool([string]$name) { # newest Windows 10/11 SDK's x64 copy of a tool
    $kits = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
    $t = Get-ChildItem -Path $kits -Directory -Filter '10.*' -ErrorAction SilentlyContinue |
        Sort-Object { [version]$_.Name } -Descending |
        ForEach-Object { Join-Path $_.FullName "x64\$name" } |
        Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $t) { Die "$name not found under $kits; the Windows SDK is required" }
    return $t
}
function Find-VcVars { # the MSVC environment script, via vswhere
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path $vswhere)) { Die 'vswhere.exe not found; Visual Studio Build Tools are required' }
    $vs = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    $bat = Join-Path $vs 'VC\Auxiliary\Build\vcvars64.bat'
    if (-not (Test-Path $bat)) { Die "vcvars64.bat not found under $vs" }
    return $bat
}

$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Pin = Get-Content (Join-Path $Repo 'packaging\upstream.json') -Raw | ConvertFrom-Json
$Version = $Pin.version
$Asset = $Pin.assets.'windows-x64'
$UpstreamRepo = $Pin.repo
Say "calibre $Version for Windows x64, from $UpstreamRepo"

$constants = Get-Content (Join-Path $Repo 'src\calibre\constants.py') -Raw
if ($constants -notmatch "(?m)^numeric_version = \((\d+), (\d+), (\d+)\)") { Die 'cannot read numeric_version' }
$srcVer = "$($Matches[1]).$($Matches[2]).$($Matches[3])"
if ($srcVer -ne $Version) { Die "src/calibre/constants.py is calibre $srcVer but upstream.json pins $Version; they must match" }
if ($constants -notmatch "(?m)^__appname__ = '([^']*)'") { Die 'cannot read __appname__' }
$AppName = $Matches[1]
if ($constants -notmatch "(?m)^zen_version = '([^']*)'") { Die 'cannot read zen_version' }
$ZenVersion = $Matches[1]
if ($constants -notmatch "(?m)^zen_display_name = '([^']*)'") { Die 'cannot read zen_display_name' }
$DisplayName = $Matches[1]
function Read-Constant([string]$name) { # a single-quoted string constant in constants.py
    if ($constants -notmatch "(?m)^$name = '([^']*)'") { Die "cannot read $name from constants.py" }
    return $Matches[1]
}
Say "$DisplayName $ZenVersion ($AppName)"

$Msix = Get-Content (Join-Path $PSScriptRoot 'msix.json') -Raw | ConvertFrom-Json
# The Store wants four parts with a 0 last, increasing on every submission;
# zen_version is bumped for a resubmission, so it is simply that plus .0.
$MsixVersion = "$ZenVersion.0"

$Cache = if ($env:CALIBRE_ZEN_UPSTREAM_CACHE) { $env:CALIBRE_ZEN_UPSTREAM_CACHE } else { Join-Path $Repo '.calibre-zen\upstream' }
$Build = if ($env:CALIBRE_ZEN_BUILD_DIR) { $env:CALIBRE_ZEN_BUILD_DIR } else { Join-Path $Repo 'build\windows' }
$Dist  = if ($env:CALIBRE_ZEN_DIST_DIR) { $env:CALIBRE_ZEN_DIST_DIR } else { Join-Path $Repo 'dist' }
$Stage = Join-Path $Build $AppName
New-Item -ItemType Directory -Force -Path $Cache, $Dist | Out-Null

# ---------------------------------------------------------------- download
$Msi = Join-Path $Cache $Asset.name
if (-not (Test-Path $Msi)) {
    # Our mirror first (upstream-mirror.py keeps a copy of every release we
    # have seen), then upstream's own archive, which keeps every version,
    # then GitHub, which loses a release's assets when the next one ships.
    # The digest check below is what makes the order a matter of
    # availability only.
    $urls = @(
        "https://github.com/$($Pin.mirror)/releases/download/upstream-$Version/$($Asset.name)",
        "$($Pin.archive)/$Version/$($Asset.name)",
        "https://github.com/$UpstreamRepo/releases/download/v$Version/$($Asset.name)"
    )
    $got = $false
    foreach ($url in $urls) {
        Say "downloading $url"
        & curl.exe -fL --retry 3 -o "$Msi.part" $url
        if ($LASTEXITCODE -eq 0) { $got = $true; break }
        Remove-Item "$Msi.part" -ErrorAction SilentlyContinue
    }
    if (-not $got) { Die "could not download $($Asset.name) from the mirror, the archive or GitHub" }
    Move-Item "$Msi.part" $Msi
}
Say 'verifying sha256'
$got = (Get-FileHash -Algorithm SHA256 $Msi).Hash.ToLower()
if ($got -ne $Asset.sha256.ToLower()) { Die "$($Asset.name) does not match the digest in upstream.json" }

# ------------------------------------------------------------------ unpack
Say 'extracting the installer (administrative install)'
if (Test-Path $Build) { Remove-Item -Recurse -Force $Build }
$Extract = Join-Path $Build 'extract'
New-Item -ItemType Directory -Force -Path $Extract | Out-Null
$p = Start-Process -FilePath 'msiexec.exe' -ArgumentList @('/a', "`"$Msi`"", '/qn', "TARGETDIR=`"$Extract`"") -Wait -PassThru
if ($p.ExitCode -ne 0) { Die "msiexec /a exited with $($p.ExitCode)" }
$dbg = Get-ChildItem -Path $Extract -Recurse -Filter 'calibre-debug.exe' | Select-Object -First 1
if (-not $dbg) { Die 'calibre-debug.exe not found in the extracted installer' }
Move-Item $dbg.DirectoryName $Stage
Remove-Item -Recurse -Force $Extract
if (-not (Test-Path (Join-Path $Stage 'app\resources'))) { Die 'unexpected layout: no app\resources' }
# msiexec marks what it extracts read-only, and the precompile has to replace
# icons.rcc; the attribute means nothing once the tree is zipped anyway.
Native 'attrib.exe' @('-R', (Join-Path $Stage '*'), '/S', '/D')

# ------------------------------------------------------- the fork's Python
# Beside app\resources, because develop mode looks for resources at
# <CALIBRE_DEVELOP_FROM>\..\resources. Nothing is duplicated.
Say 'adding src\'
$SrcDest = Join-Path $Stage 'app\src'
& robocopy (Join-Path $Repo 'src') $SrcDest /E /NFL /NDL /NJH /NJS /NP /XD __pycache__ /XF *.pyc *_ui.py | Out-Null
if ($LASTEXITCODE -ge 8) { Die "robocopy failed with $LASTEXITCODE" }

if (-not (& git -C $Repo rev-parse -q --verify "refs/tags/v$Version" 2>$null)) {
    Say "fetching tag v$Version from $UpstreamRepo"
    Native 'git' @('-C', $Repo, 'fetch', '--depth=1', "https://github.com/$UpstreamRepo.git", 'tag', "v$Version")
}
Say "adding the fork's resource files"
$changed = & git -C $Repo diff --name-only --diff-filter=AM "v$Version" -- resources
if ($LASTEXITCODE -ne 0) { Die 'git diff against the upstream tag failed' }
foreach ($f in $changed) {
    if (-not $f) { continue }
    Write-Host "    $f"
    $dest = Join-Path $Stage ('app\' + ($f -replace '/', '\'))
    New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
    Copy-Item (Join-Path $Repo $f) $dest -Force
}

# --------------------------------------------------------------- launchers
# One per public launcher at the top of the install. Inside the tree the
# upstream names stay, because calibre spawns its helpers by basename; what a
# user runs is prefixed, following calibre.linux.path_name(). calibre-parallel
# is internal and inherits the environment.
Say 'writing launchers'
$ZenBin = Join-Path $Stage 'zen-bin'
New-Item -ItemType Directory -Force -Path $ZenBin | Out-Null
function Write-Launcher([string]$exe, [string]$path, [string]$here) {
    $body = @"
@echo off
rem ${AppName}: run calibre's frozen $exe on this fork's Python.
setlocal
set "here=$here"
set "CALIBRE_DEVELOP_FROM=%here%\app\src"
set "CALIBRE_ZEN_PACKAGED=1"
"%here%\$exe" %*
"@
    [System.IO.File]::WriteAllText($path, ($body -replace "`r?`n", "`r`n"), [System.Text.Encoding]::ASCII)
}
foreach ($exe in Get-ChildItem -Path $Stage -File -Filter '*.exe') {
    if ($exe.Name -eq 'calibre-parallel.exe') { continue }
    $stem = $exe.BaseName
    Write-Launcher $exe.Name (Join-Path $ZenBin "zen-$stem.cmd") '%~dp0..'
}
# The GUI gets a real executable. Assets first: the icon it embeds and the
# MSIX logos are rendered from the one SVG by the bundle's own Qt.
Say 'rendering the icon and the Store logos'
$Assets = Join-Path $Build 'assets'
New-Item -ItemType Directory -Force -Path $Assets | Out-Null
$env:QT_QPA_PLATFORM = 'offscreen'
Native (Join-Path $Stage 'calibre-debug.exe') @('-e', (Join-Path $PSScriptRoot 'render_assets.py'), '--', (Join-Path $Repo 'imgsrc\calibre.svg'), $Assets)

$vcvars = Find-VcVars
# Every executable we ship is built the same way: the sources, a generated
# zen_config.h force-included for compile-time choices, launcher.rc with its
# fields filled (plus, for the installer, the payload resource), and
# exe.manifest embedded. Returns the path of the .exe.
function Build-Exe {
    param(
        [string]$Name,               # the executable's basename
        [string]$Description,        # FileDescription in the version info
        [string[]]$Sources,          # .c / .cpp files, by path
        [hashtable]$Defines = @{},   # zen_config.h: NAME -> value (already spelled for C)
        [string[]]$Libs = @('user32.lib'),
        [string]$ExtraFlags = '',    # more cl options, e.g. /EHsc for C++
        [string]$Payload = ''        # a file to embed as the resource "extra"
    )
    $dir = Join-Path $Build "exe\$Name"
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Copy-Item (Join-Path $Assets 'calibre-zen.ico') (Join-Path $dir 'calibre-zen.ico')
    Copy-Item (Join-Path $PSScriptRoot 'exe.manifest') (Join-Path $dir 'exe.manifest')
    $cfg = ($Defines.GetEnumerator() | Sort-Object Key | ForEach-Object { "#define $($_.Key) $($_.Value)" }) -join "`r`n"
    [System.IO.File]::WriteAllText((Join-Path $dir 'zen_config.h'), "$cfg`r`n", [System.Text.Encoding]::ASCII)
    $rc = Get-Content (Join-Path $PSScriptRoot 'launcher.rc') -Raw
    $rc = $rc.Replace('@VERSION_COMMA@', $MsixVersion.Replace('.', ',')).Replace('@VERSION_DOT@', $MsixVersion).
        Replace('@DISPLAY_NAME@', $DisplayName).Replace('@FILE_DESCRIPTION@', $Description).Replace('@INTERNAL_NAME@', $Name)
    if ($Payload) { $rc += "`r`nextra extra `"$($Payload.Replace('\', '/'))`"`r`n" } # rc reads / as a path separator, \ as an escape
    [System.IO.File]::WriteAllText((Join-Path $dir 'launcher.rc'), ($rc -replace "`r?`n", "`r`n"), [System.Text.Encoding]::ASCII)
    $srcs = ($Sources | ForEach-Object { "`"$_`"" }) -join ' '
    # A batch file rather than one long cmd /c string: PowerShell re-quotes
    # arguments on the way to cmd.exe and the nested quotes do not survive.
    $bat = @"
@echo off
call "$vcvars" >nul || exit /b 1
cd /d "$dir" || exit /b 1
rc /nologo launcher.rc || exit /b 1
cl /nologo /O2 /W4 /MT /DUNICODE /D_UNICODE /DPSAPI_VERSION=1 /I"$dir" /FIzen_config.h $ExtraFlags $srcs launcher.res /Fe:$Name.exe /link /SUBSYSTEM:WINDOWS /DYNAMICBASE /NXCOMPAT /MANIFEST:EMBED /MANIFESTINPUT:exe.manifest $($Libs -join ' ') || exit /b 1
"@
    $batPath = Join-Path $dir 'build.cmd'
    [System.IO.File]::WriteAllText($batPath, ($bat -replace "`r?`n", "`r`n"), [System.Text.Encoding]::ASCII)
    & cmd.exe /c $batPath | Out-Host # not into the pipeline, which is this function's return value
    if ($LASTEXITCODE -ne 0) { Die "building $Name.exe failed with $LASTEXITCODE" }
    $exe = Join-Path $dir "$Name.exe"
    $fv = (Get-Item $exe).VersionInfo
    Write-Host ("    {0} {1} `"{2}`" {3:N1} MB" -f "$Name.exe", $fv.FileVersion, $fv.FileDescription, ((Get-Item $exe).Length / 1MB))
    return $exe
}

# The GUI, the viewer and the editor each get a real executable at the top of
# the tree: what the Start menu, the desktop and the Run dialog point at.
# Same source, a different target each (launcher.c).
Say 'building the launchers'
$LauncherC = Join-Path $PSScriptRoot 'launcher.c'
$Launchers = @(
    @{ Name = $AppName;           Target = 'calibre.exe';      Description = $DisplayName },
    @{ Name = 'zen-ebook-viewer'; Target = 'ebook-viewer.exe'; Description = "$DisplayName E-book viewer" },
    @{ Name = 'zen-ebook-edit';   Target = 'ebook-edit.exe';   Description = "$DisplayName Edit book" }
)
foreach ($l in $Launchers) {
    $exe = Build-Exe -Name $l.Name -Description $l.Description -Sources @($LauncherC) -Defines @{ ZEN_TARGET = "L`"$($l.Target)`"" }
    Copy-Item $exe (Join-Path $Stage "$($l.Name).exe")
}

# -------------------------------------------------------------- precompile
$WorkConfig = Join-Path ([System.IO.Path]::GetTempPath()) ("zen-config-" + [guid]::NewGuid())
New-Item -ItemType Directory -Force -Path $WorkConfig | Out-Null
$env:CALIBRE_DEVELOP_FROM = $SrcDest
$env:CALIBRE_CONFIG_DIRECTORY = $WorkConfig
$env:QT_QPA_PLATFORM = 'offscreen'
$Debug = Join-Path $Stage 'calibre-debug.exe'

Say 'compiling UI forms and icons.rcc'
$env:CALIBRE_FORCE_BUILD_UI_FORMS = '1'
RunPy $Debug @'
import os
from calibre.build_forms import build_forms
build_forms(os.environ['CALIBRE_DEVELOP_FROM'], summary=True)
'@
Remove-Item Env:CALIBRE_FORCE_BUILD_UI_FORMS

Say 'compiling bytecode'
RunPy $Debug @'
import compileall, os, sys
ok = compileall.compile_dir(os.environ['CALIBRE_DEVELOP_FROM'], quiet=1, workers=0)
sys.exit(0 if ok else 1)
'@

# ------------------------------------------------------------------- smoke
$env:CALIBRE_ZEN_PACKAGED = '1'
$Mark = Get-Date
Start-Sleep -Seconds 2 # file-time resolution
Say 'smoke test: identity'
$srcCheck = ($SrcDest -replace '\\', '/').ToLower()
RunPy $Debug @"
from calibre.constants import __appname__, numeric_version, config_dir, is_running_from_develop
# The bundle runs Python with -OO, which strips assert statements, so a
# check has to be an if. No quotes in here: this text sits inside shell
# strings of both kinds.
def check(ok, msg):
    if not ok:
        raise SystemExit(msg)
from calibre.utils.ipc import gui_socket_address
import calibre, calibre_zen
check(__appname__ == '$AppName', __appname__)
check('.'.join(map(str, numeric_version)) == '$Version', numeric_version)
check(not is_running_from_develop, 'develop mode is still on: the package would rebuild itself at launch')
check(calibre.__file__.replace(chr(92), '/').lower().startswith('$srcCheck'), calibre.__file__)
print('    appname   ', __appname__)
print('    version   ', '.'.join(map(str, numeric_version)))
print('    python    ', calibre.__file__)
print('    overlay   ', calibre_zen.__file__)
print('    gui pipe  ', gui_socket_address())
"@

Say 'smoke test: headless GUI with the overlay'
RunPy $Debug @'
from calibre.gui2 import Application
# The bundle runs Python with -OO, which strips assert statements, so a
# check has to be an if. No quotes in here: this text sits inside shell
# strings of both kinds.
def check(ok, msg):
    if not ok:
        raise SystemExit(msg)
app = Application([], force_calibre_style=True)
n = len(app.styleSheet())
check(n > 1000, f"overlay sheet is only {n} bytes")
print("    style sheet", n, "bytes")
'@

$written = Get-ChildItem -Path $Stage -Recurse -File | Where-Object { $_.LastWriteTime -gt $Mark }
if ($written) {
    $written | ForEach-Object { Write-Host "    $($_.FullName)" }
    Die 'the package wrote into itself at launch (above); it must not'
}
Remove-Item -Recurse -Force $WorkConfig

# --------------------------------------------------------------------- zip
$Out = Join-Path $Dist "$AppName-$ZenVersion-windows-x64.zip"
Say "packing $Out"
if (Test-Path $Out) { Remove-Item $Out }
Native 'tar.exe' @('-a', '-cf', $Out, '-C', $Build, $AppName)
Write-Sha256 $Out
Say ("zip: {0:N0} MB {1}" -f ((Get-Item $Out).Length / 1MB), $Out)

# -------------------------------------------------------------------- msix
# The same tree, plus the manifest and the logos, packed for the Store. A
# separate copy so the zip carries neither. Unsigned: the Store signs it.
Say 'staging the MSIX'
$MsixStage = Join-Path $Build 'msix'
& robocopy $Stage $MsixStage /E /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { Die "robocopy to the MSIX stage failed with $LASTEXITCODE" }
& robocopy (Join-Path $Assets 'Assets') (Join-Path $MsixStage 'Assets') /E /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { Die "robocopy of the logos failed with $LASTEXITCODE" }
$manifest = Get-Content (Join-Path $PSScriptRoot 'AppxManifest.xml') -Raw
$manifest = $manifest.Replace('@IDENTITY_NAME@', $Msix.identity_name).
    Replace('@PUBLISHER@', $Msix.publisher).
    Replace('@VERSION@', $MsixVersion).
    Replace('@DISPLAY_NAME@', $DisplayName).
    Replace('@PUBLISHER_DISPLAY_NAME@', $Msix.publisher_display_name).
    Replace('@DESCRIPTION@', $Msix.description)
[System.IO.File]::WriteAllText((Join-Path $MsixStage 'AppxManifest.xml'), $manifest, (New-Object System.Text.UTF8Encoding $false))

$OutMsix = Join-Path $Dist "$AppName-$ZenVersion-windows-x64.msix"
Say "packing $OutMsix"
if (Test-Path $OutMsix) { Remove-Item $OutMsix }
Native (Find-SdkTool 'makeappx.exe') @('pack', '/o', '/d', $MsixStage, '/p', $OutMsix)
Write-Sha256 $OutMsix
Say ("msix: {0:N0} MB {1}" -f ((Get-Item $OutMsix).Length / 1MB), $OutMsix)
Write-Host "    identity $($Msix.identity_name) / $($Msix.publisher) / $MsixVersion -- unsigned, for Store submission"
Remove-Item -Recurse -Force $MsixStage

# ---------------------------------------------------------------- portable
# Upstream's Calibre Portable layout (portable.cpp, get_portable_base), under
# our own folder name: three launchers at the top, the program in Calibre\,
# the user's data in Calibre Library\ and Calibre Settings\. The launchers
# are launcher.c again, in portable mode. The folder is zipped and embedded
# in the installer, which is upstream's portable-installer.cpp reading that
# zip straight from its resource.
Say 'staging Calibre Zen Portable'
$PortableName = "$DisplayName Portable"
$PortableStage = Join-Path (Join-Path $Build 'portable') $PortableName
New-Item -ItemType Directory -Force -Path (Join-Path $PortableStage 'Calibre Library'), (Join-Path $PortableStage 'Calibre Settings') | Out-Null
& robocopy $Stage (Join-Path $PortableStage 'Calibre') /E /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { Die "robocopy to the portable stage failed with $LASTEXITCODE" }
foreach ($l in $Launchers) {
    $exe = Build-Exe -Name "$($l.Name)-portable" -Description "$($l.Description) Portable" -Sources @($LauncherC) `
        -Defines @{ ZEN_TARGET = "L`"$($l.Target)`""; ZEN_PORTABLE = '1' }
    Copy-Item $exe (Join-Path $PortableStage "$($l.Name)-portable.exe")
}
# Only the installer's names for these three may be at the top; it moves
# them by name (portable-installer.cpp, move_program).
foreach ($n in @('calibre-zen-portable.exe', 'zen-ebook-viewer-portable.exe', 'zen-ebook-edit-portable.exe')) {
    if (-not (Test-Path (Join-Path $PortableStage $n))) { Die "portable stage is missing $n, which the installer expects" }
}

Say 'zipping the portable folder'
$PortableZip = Join-Path $Build "$AppName-portable.zip"
Native $Debug @('-e', (Join-Path $PSScriptRoot 'portable_zip.py'), '--', $PortableStage, $PortableZip)

Say 'building the portable installer'
$installer = Build-Exe -Name "$AppName-portable-installer" -Description "$PortableName Installer" `
    -Sources @((Join-Path $PSScriptRoot 'portable-installer.cpp'), (Join-Path $Repo 'bypy\windows\XUnzip.cpp')) `
    -ExtraFlags "/EHsc /I`"$(Join-Path $Repo 'bypy\windows')`"" `
    -Libs @('user32.lib', 'shell32.lib', 'ole32.lib', 'shlwapi.lib', 'psapi.lib', 'kernel32.lib') `
    -Payload $PortableZip
$OutPortable = Join-Path $Dist "$AppName-portable-installer-$ZenVersion.exe"
if (Test-Path $OutPortable) { Remove-Item $OutPortable }
Copy-Item $installer $OutPortable
Write-Sha256 $OutPortable
Say ("portable installer: {0:N0} MB {1}" -f ((Get-Item $OutPortable).Length / 1MB), $OutPortable)
Remove-Item $PortableZip
Remove-Item -Recurse -Force (Join-Path $Build 'portable')

# --------------------------------------------------------------------- msi
# WiX 5 as a .NET global tool, the way upstream's bypy/windows/wix.py has it.
# Pinned: the extensions must match the tool exactly.
$WixVersion = '5.0.2'
$Wix = Join-Path $env:USERPROFILE '.dotnet\tools\wix.exe'
if (-not (Test-Path $Wix)) {
    Say "installing WiX $WixVersion"
    Native 'dotnet' @('tool', 'install', '--global', 'wix', '--version', $WixVersion)
    if (-not (Test-Path $Wix)) { Die "dotnet tool install did not put wix.exe at $Wix" }
}
$got = (& $Wix --version).Trim()
if (-not $got.StartsWith($WixVersion)) { Die "wix.exe is $got, this script wants $WixVersion; run: dotnet tool update --global wix --version $WixVersion" }
foreach ($ext in @('WixToolset.Util.wixext', 'WixToolset.UI.wixext')) {
    if (-not (Test-Path (Join-Path $env:USERPROFILE ".wix\extensions\$ext\$WixVersion"))) {
        Native $Wix @('extension', 'add', '-g', "$ext/$WixVersion")
    }
}

Say 'writing the WiX source'
$WixDir = Join-Path $Build 'wix'
New-Item -ItemType Directory -Force -Path $WixDir | Out-Null
Native $Debug @('-e', (Join-Path $PSScriptRoot 'wix.py'), '--', $Stage, $WixDir,
    "APP=$AppName", "DISPLAY_NAME=$DisplayName", "VERSION=$ZenVersion", "CALIBRE_VERSION=$Version",
    "MANUFACTURER=$($Msix.publisher_display_name)", 'UPGRADE_CODE=23281CC8-300B-4CBA-9483-AD2EE9DAE364',
    "URL=https://github.com/$($Pin.mirror)",
    "MAIN_APP_UID=$(Read-Constant 'MAIN_APP_UID')", "VIEWER_APP_UID=$(Read-Constant 'VIEWER_APP_UID')", "EDITOR_APP_UID=$(Read-Constant 'EDITOR_APP_UID')",
    "MAIN_ICON=$(Join-Path $Assets 'calibre-zen.ico')", "LICENSE=$(Join-Path $Repo 'LICENSE.rtf')",
    "BANNER=$(Join-Path $Repo 'icons\wix-banner.bmp')", "DIALOG=$(Join-Path $Repo 'icons\wix-dialog.bmp')")

$OutMsi = Join-Path $Dist "$AppName-$ZenVersion-windows-x64.msi"
Say "building $OutMsi"
if (Test-Path $OutMsi) { Remove-Item $OutMsi }
Native $Wix @('build', '-arch', 'x64', '-culture', 'en-us', '-loc', (Join-Path $PSScriptRoot 'wix-en-us.wxl'), '-dcl', 'high',
    '-ext', 'WixToolset.Util.wixext', '-ext', 'WixToolset.UI.wixext', '-o', $OutMsi, (Join-Path $WixDir "$AppName.wxs"))
Remove-Item "$($OutMsi.Substring(0, $OutMsi.Length - 4)).wixpdb" -ErrorAction SilentlyContinue
Write-Sha256 $OutMsi
Say ("msi: {0:N0} MB {1}" -f ((Get-Item $OutMsi).Length / 1MB), $OutMsi)

# ------------------------------------------------------ install tests (CI)
if ($env:CALIBRE_ZEN_INSTALL_TEST -eq '1') {
    $IdentityCheck = @'
import os
from calibre.constants import __appname__, config_dir, isportable, is_running_from_develop
import calibre
# The bundle runs Python with -OO, which strips assert statements, so a
# check has to be an if.
def check(ok, msg):
    if not ok:
        raise SystemExit(msg)
check(__appname__ == os.environ['ZEN_EXPECT_APPNAME'], __appname__)
check(not is_running_from_develop, 'develop mode is still on')
check(calibre.__file__.lower().startswith(os.environ['ZEN_EXPECT_SRC'].lower()), calibre.__file__)
check(str(isportable) == os.environ['ZEN_EXPECT_PORTABLE'], f'isportable is {isportable}')
if isportable:
    check(config_dir.lower().rstrip(chr(92)) == os.environ['CALIBRE_CONFIG_DIRECTORY'].lower().rstrip(chr(92)), config_dir)
print('    appname   ', __appname__)
print('    python    ', calibre.__file__)
print('    config    ', config_dir)
print('    portable  ', isportable)
'@
    $env:ZEN_EXPECT_APPNAME = $AppName

    Say 'install test: msi'
    $log = Join-Path $Build 'msi-install.log'
    $p = Start-Process -FilePath 'msiexec.exe' -ArgumentList @('/i', "`"$OutMsi`"", '/qn', '/norestart', '/l*v', "`"$log`"") -Wait -PassThru
    if ($p.ExitCode -ne 0) { Get-Content $log -Tail 40; Die "msiexec /i exited with $($p.ExitCode)" }
    $Installed = Join-Path ${env:ProgramFiles} $DisplayName
    foreach ($f in @("$AppName.exe", 'zen-ebook-viewer.exe', 'zen-ebook-edit.exe', 'calibre.exe', 'app\src\calibre_zen\hooks.py', 'zen-bin\zen-calibre-debug.cmd')) {
        if (-not (Test-Path (Join-Path $Installed $f))) { Die "the msi did not install $f under $Installed" }
    }
    $env:ZEN_EXPECT_SRC = Join-Path $Installed 'app\src'
    $env:ZEN_EXPECT_PORTABLE = 'False'
    $env:CALIBRE_CONFIG_DIRECTORY = Join-Path ([System.IO.Path]::GetTempPath()) ("zen-msi-config-" + [guid]::NewGuid())
    # Through the installed wrapper, so what a user's shell would run is what is tested.
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("zen-" + [guid]::NewGuid() + ".py")
    [System.IO.File]::WriteAllText($tmp, $IdentityCheck, (New-Object System.Text.UTF8Encoding $false))
    Remove-Item Env:CALIBRE_DEVELOP_FROM, Env:CALIBRE_ZEN_PACKAGED -ErrorAction SilentlyContinue
    & (Join-Path $Installed 'zen-bin\zen-calibre-debug.cmd') '-e' $tmp
    if ($LASTEXITCODE -ne 0) { Die "the installed calibre-zen failed its identity check ($LASTEXITCODE)" }
    Remove-Item $tmp
    $p = Start-Process -FilePath 'msiexec.exe' -ArgumentList @('/x', "`"$OutMsi`"", '/qn', '/norestart') -Wait -PassThru
    if ($p.ExitCode -ne 0) { Die "msiexec /x exited with $($p.ExitCode)" }
    if (Test-Path (Join-Path $Installed 'calibre.exe')) { Die "uninstalling left calibre.exe under $Installed" }
    Remove-Item -Recurse -Force $env:CALIBRE_CONFIG_DIRECTORY -ErrorAction SilentlyContinue

    Say 'install test: portable installer'
    $PortableTarget = Join-Path ([System.IO.Path]::GetTempPath()) 'zen-portable-test'
    if (Test-Path $PortableTarget) { Remove-Item -Recurse -Force $PortableTarget }
    # With a folder argument it installs there and asks nothing -- unless
    # something fails, when it shows a message box and waits for a click
    # nobody will make, hence the deadline.
    $p = Start-Process -FilePath $OutPortable -ArgumentList @("`"$PortableTarget`"") -PassThru
    if (-not $p.WaitForExit(15 * 60 * 1000)) { $p.Kill(); Die 'the portable installer did not finish in 15 minutes; it is probably showing an error dialog' }
    if ($p.ExitCode -ne 0) { Die "the portable installer exited with $($p.ExitCode)" }
    $PortableDir = Join-Path $PortableTarget $PortableName
    foreach ($f in @('calibre-zen-portable.exe', 'zen-ebook-viewer-portable.exe', 'zen-ebook-edit-portable.exe', 'Calibre\calibre.exe', 'Calibre\app\src\calibre_zen\hooks.py', 'Calibre Library', 'Calibre Settings')) {
        if (-not (Test-Path (Join-Path $PortableDir $f))) { Die "the portable installer did not produce $f under $PortableDir" }
    }
    if (Test-Path (Join-Path $PortableDir '_unpack_calibre_zen_portable')) { Die 'the portable installer left its unpack folder behind' }
    # What calibre-zen-portable.exe sets, then the same identity check.
    $env:ZEN_EXPECT_SRC = Join-Path $PortableDir 'Calibre\app\src'
    $env:ZEN_EXPECT_PORTABLE = 'True'
    $env:CALIBRE_DEVELOP_FROM = $env:ZEN_EXPECT_SRC
    $env:CALIBRE_ZEN_PACKAGED = '1'
    $env:CALIBRE_CONFIG_DIRECTORY = Join-Path $PortableDir 'Calibre Settings'
    $env:CALIBRE_PORTABLE_BUILD = Join-Path $PortableDir 'Calibre\calibre.exe'
    RunPy (Join-Path $PortableDir 'Calibre\calibre-debug.exe') $IdentityCheck
    Remove-Item Env:CALIBRE_PORTABLE_BUILD, Env:CALIBRE_CONFIG_DIRECTORY
    Remove-Item -Recurse -Force $PortableTarget
}
