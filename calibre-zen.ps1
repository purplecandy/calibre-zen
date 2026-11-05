# calibre-zen.ps1 -- run calibre-zen from this source tree on Windows ("develop from" mode).
#
# The Windows twin of ./calibre-zen, which is macOS only. Nothing is installed
# or built: the interpreter, Qt and the compiled extensions come from an
# installed Calibre Zen of the same calibre version, and only the Python in
# .\src is read from this tree, so an edit takes effect on the next launch.
#
# Run it as .\calibre-zen.cmd, which needs no change to PowerShell's execution
# policy. Anything it does not know is passed to the app:
#
#   .\calibre-zen.cmd                          the GUI, in debug mode (output stays in this window)
#   .\calibre-zen.cmd -Lang he                 in Hebrew; any language code calibre has
#   .\calibre-zen.cmd -Library D:\books        open a library other than .calibre-zen\library
#   .\calibre-zen.cmd -Fresh                   forget the settings first (first run again)
#   .\calibre-zen.cmd -- C:\books\a.epub       arguments after -- go to the app untouched
#   .\calibre-zen.cmd -Tool calibredb list     run one of the bundled tools instead
#
# Settings live in .calibre-zen\config, apart from your normal calibre, and the
# default library in .calibre-zen\library holds no books of yours. Both are
# git-ignored. Calibre's own welcome wizard is skipped; this fork's onboarding is not.
#
# Environment:
#   CALIBRE_ZEN_BUNDLE  the install to borrow the binary from
#                       (default: C:\Program Files\Calibre Zen)
param(
    [string]$Library,
    [string]$Lang,
    [string]$Bundle,
    [string]$Tool,
    [switch]$Fresh,
    [Parameter(ValueFromRemainingArguments = $true)] [string[]]$Rest
)
$ErrorActionPreference = 'Stop'

function Die([string]$msg) {
    [Console]::Error.WriteLine("calibre-zen: $msg")
    exit 1
}

$Repo = $PSScriptRoot
if (-not $Bundle) { $Bundle = $env:CALIBRE_ZEN_BUNDLE }
if (-not $Bundle) { $Bundle = Join-Path $env:ProgramFiles 'Calibre Zen' }
$Debug = Join-Path $Bundle 'calibre-debug.exe'
if (-not (Test-Path $Debug)) {
    Die "cannot find calibre-debug.exe in '$Bundle'. Install Calibre Zen (https://github.com/purplecandy/calibre-zen/releases), or set CALIBRE_ZEN_BUNDLE to its folder."
}

# develop-from only works when the binary and this tree are the same calibre
# version: the compiled extensions must match the Python code.
$SrcVer = ([regex]::Match((Get-Content (Join-Path $Repo 'src\calibre\constants.py') -Raw),
    '(?m)^numeric_version = \((\d+), (\d+), (\d+)\)')).Groups
$SrcVer = "$($SrcVer[1]).$($SrcVer[2]).$($SrcVer[3])"
$AppVer = [regex]::Match((& $Debug --version | Out-String), 'calibre ([\d.]+)').Groups[1].Value
if ($SrcVer -ne $AppVer -and $SrcVer -ne "$AppVer.0") {
    [Console]::Error.WriteLine("calibre-zen: warning: this tree is calibre $SrcVer but '$Bundle' is $AppVer. Expect breakage; install the matching Calibre Zen.")
}

# Its own application identity is the installed Calibre Zen's, so they share one
# single-instance lock: with that running, this launch would hand its arguments
# to it, and nothing from this tree would start.
$running = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($Bundle, [StringComparison]::OrdinalIgnoreCase) -and $_.ProcessName -eq 'calibre' }
if ($running -and -not $Tool) {
    Die "an installed Calibre Zen is running (pid $(($running | ForEach-Object Id) -join ', ')); close it first, or this launch would hand over to it instead of starting."
}

$State = Join-Path $Repo '.calibre-zen'
$Config = Join-Path $State 'config'
if ($Fresh -and (Test-Path $Config)) { Remove-Item $Config -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Config | Out-Null
if (-not $Library) { $Library = Join-Path $State 'library' }
New-Item -ItemType Directory -Force -Path $Library | Out-Null
$Library = (Resolve-Path $Library).Path

$env:CALIBRE_DEVELOP_FROM = Join-Path $Repo 'src'
$env:CALIBRE_ZEN_PACKAGED = '1' # use the source, but rebuild nothing: forms and icons come with the binary's tree
$env:CALIBRE_CONFIG_DIRECTORY = $Config
if ($Lang) { $env:CALIBRE_OVERRIDE_LANG = $Lang } else { Remove-Item Env:CALIBRE_OVERRIDE_LANG -ErrorAction SilentlyContinue }

# Point the settings at the chosen library and skip calibre's welcome wizard, so
# the GUI and the bundled tools agree which library this is. Through calibre's
# own config code, which knows where each setting is kept.
& $Debug -c "import sys; from calibre.utils.config import dynamic, prefs; prefs['library_path'] = sys.argv[1]; dynamic.set('welcome_wizard_was_run', True)" -- $Library
if ($LASTEXITCODE -ne 0) { Die 'could not write the settings' }

if ($Tool) {
    $exe = Join-Path $Bundle "$Tool.exe"
    if (-not (Test-Path $exe)) { Die "no tool called '$Tool' in '$Bundle'" }
    & $exe @Rest
} else {
    & $Debug -e (Join-Path $State 'bootstrap.py') -- --with-library $Library @Rest
}
exit $LASTEXITCODE
