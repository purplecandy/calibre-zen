@echo off
rem Runs calibre-zen.ps1 without needing PowerShell's execution policy changed. See that file.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0calibre-zen.ps1" %*
exit /b %errorlevel%
