@echo off
rem SPDX-License-Identifier: MIT

setlocal
set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%apothem.ps1" %*
