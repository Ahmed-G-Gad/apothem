@echo off
rem SPDX-License-Identifier: MIT
rem update exposes no CLI flags - it is driven entirely by environment overrides
rem (APOTHEM_REF, APOTHEM_HARNESS, APOTHEM_SOURCE, ...), mirroring update.sh,
rem which parses no arguments either. There is thus no POSIX->PowerShell flag to
rem translate, so %* passes through verbatim.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0update.ps1" %*
