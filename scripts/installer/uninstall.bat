@echo off
rem SPDX-License-Identifier: MIT
rem POSIX->PowerShell flag translation: the documented POSIX uninstall flags
rem (--yes / -y, --harness NAME, --remove-source) are mapped to uninstall.ps1's
rem PowerShell parameters so a CMD user gets the same flag UX as the .sh / .ps1
rem siblings. A --harness value and any already-PowerShell-style or other token
rem pass through verbatim. %~dp0 is captured before the loop because `shift`
rem also rewrites %0.
setlocal
set "HERE=%~dp0"
set "ARGS="
:parse
if "%~1"=="" goto run
set "TOKEN=%~1"
set "OUT=%1"
if /I "%TOKEN%"=="--yes"           set "OUT=-Yes"
if /I "%TOKEN%"=="-y"              set "OUT=-Yes"
if /I "%TOKEN%"=="--harness"       set "OUT=-Harness"
if /I "%TOKEN%"=="--remove-source" set "OUT=-RemoveSource"
set "ARGS=%ARGS% %OUT%"
shift
goto parse
:run
powershell -NoProfile -ExecutionPolicy Bypass -File "%HERE%uninstall.ps1"%ARGS%
exit /b %ERRORLEVEL%
