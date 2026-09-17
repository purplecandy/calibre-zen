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
# Two outputs: a .zip anyone can unpack, and an .msix for the Microsoft Store,
# which signs it on submission. The Store identity comes from msix.json.
#
# Runs on Windows only: the precompile and smoke-test steps execute the
# downloaded binary, and MSVC and the Windows SDK build the launcher and the
# package. The zip is unsigned: SmartScreen warns until it has a reputation.
#
# Usage:  powershell -File packaging\windows\package.ps1
#
# Environment:
#   CALIBRE_ZEN_UPSTREAM_CACHE  where downloads are kept   (.calibre-zen\upstream)
#   CALIBRE_ZEN_BUILD_DIR       staging area, wiped         (build\windows)
#   CALIBRE_ZEN_DIST_DIR        where the .zip lands        (dist)
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
    Say "downloading $($Asset.name)"
    $url = "https://github.com/$UpstreamRepo/releases/download/v$Version/$($Asset.name)"
    Native 'curl.exe' @('-fL', '--retry', '3', '-o', "$Msi.part", $url)
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

Say "building $AppName.exe"
$LauncherBuild = Join-Path $Build 'launcher'
New-Item -ItemType Directory -Force -Path $LauncherBuild | Out-Null
Copy-Item (Join-Path $PSScriptRoot 'launcher.c') $LauncherBuild
Copy-Item (Join-Path $Assets 'calibre-zen.ico') (Join-Path $LauncherBuild 'calibre-zen.ico')
$rc = Get-Content (Join-Path $PSScriptRoot 'launcher.rc') -Raw
$rc = $rc.Replace('@VERSION_COMMA@', $MsixVersion.Replace('.', ',')).Replace('@VERSION_DOT@', $MsixVersion).Replace('@DISPLAY_NAME@', $DisplayName)
Set-Content (Join-Path $LauncherBuild 'launcher.rc') $rc -Encoding ASCII
$vcvars = Find-VcVars
# A batch file rather than one long cmd /c string: PowerShell re-quotes
# arguments on the way to cmd.exe and the nested quotes do not survive.
$bat = @"
@echo off
call "$vcvars" >nul || exit /b 1
cd /d "$LauncherBuild" || exit /b 1
rc /nologo launcher.rc || exit /b 1
cl /nologo /O2 /W4 /MT /DUNICODE /D_UNICODE launcher.c launcher.res /Fe:$($AppName).exe /link /SUBSYSTEM:WINDOWS /DYNAMICBASE /NXCOMPAT user32.lib || exit /b 1
"@
$batPath = Join-Path $LauncherBuild 'build.cmd'
[System.IO.File]::WriteAllText($batPath, ($bat -replace "`r?`n", "`r`n"), [System.Text.Encoding]::ASCII)
& cmd.exe /c $batPath
if ($LASTEXITCODE -ne 0) { Die "building the launcher failed with $LASTEXITCODE" }
Copy-Item (Join-Path $LauncherBuild "$AppName.exe") (Join-Path $Stage "$AppName.exe")
$fv = (Get-Item (Join-Path $Stage "$AppName.exe")).VersionInfo
Write-Host "    $AppName.exe $($fv.FileVersion) `"$($fv.FileDescription)`""

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
"$((Get-FileHash -Algorithm SHA256 $Out).Hash.ToLower())  $(Split-Path $Out -Leaf)" | Set-Content "$Out.sha256" -Encoding ASCII
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
"$((Get-FileHash -Algorithm SHA256 $OutMsix).Hash.ToLower())  $(Split-Path $OutMsix -Leaf)" | Set-Content "$OutMsix.sha256" -Encoding ASCII
Say ("msix: {0:N0} MB {1}" -f ((Get-Item $OutMsix).Length / 1MB), $OutMsix)
Write-Host "    identity $($Msix.identity_name) / $($Msix.publisher) / $MsixVersion -- unsigned, for Store submission"
