@echo off
rem SPDX-License-Identifier: MIT
:: Network install: curl -fsSL https://apothem.ahmedgad.com/install.bat -o install.bat ^&^& install.bat
rem
rem POSIX->PowerShell flag translation: the documented POSIX installer flags
rem (--clean, --fresh, --dry-run, --yes) are mapped to install.ps1's PowerShell
rem parameters so a CMD user gets the same flag UX as the .sh / .ps1 siblings.
rem Already-PowerShell-style tokens (-Clean, -Yes, ...) and any other argument
rem pass through verbatim, matching install.ps1's own handling. %~dp0 is captured
rem before the loop because `shift` also rewrites %0.
setlocal
set "HERE=%~dp0"
set "ARGS="
:parse
if "%~1"=="" goto run
set "TOKEN=%~1"
set "OUT=%1"
if /I "%TOKEN%"=="--clean"   set "OUT=-Clean"
if /I "%TOKEN%"=="--fresh"   set "OUT=-Fresh"
if /I "%TOKEN%"=="--dry-run" set "OUT=-DryRun"
if /I "%TOKEN%"=="--yes"     set "OUT=-Yes"
set "ARGS=%ARGS% %OUT%"
shift
goto parse
:run
powershell -NoProfile -ExecutionPolicy Bypass -File "%HERE%install.ps1"%ARGS%
exit /b %ERRORLEVEL%
