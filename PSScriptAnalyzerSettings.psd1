# SPDX-License-Identifier: MIT

@{
    # PSScriptAnalyzer settings consumed by the project's CI gate and
    # local smoke tests via:
    #
    #     Invoke-ScriptAnalyzer -Path . -Recurse `
    #         -Settings ./PSScriptAnalyzerSettings.psd1 `
    #         -Severity Error,Warning
    #
    # `Invoke-ScriptAnalyzer` does NOT auto-load this file; the
    # `-Settings` flag is required at the call site. The CI shell-lint
    # job and the local pre-commit script-analyzer pass `-Settings
    # ./PSScriptAnalyzerSettings.psd1` explicitly.
    Severity = @('Error', 'Warning')
    ExcludeRules = @(
        # Install scripts produce styled, user-facing console output
        # (banners, progress markers, success/failure indicators).
        # `Write-Host` is the right idiom for that output: it bypasses
        # the pipeline so progress markers do not pollute callers'
        # output streams. Per `src/apothem/rules/code-craft-shell.md`
        # M13.5, install/uninstall surfaces are CLI UX, not pipeline
        # producers.
        'PSAvoidUsingWriteHost',
        # The shell scripts in this repository are pure ASCII; PowerShell
        # source files are encoded UTF-8-no-BOM by convention. The
        # BOM-required convention conflicts with the cross-platform
        # working-tree LF discipline declared in `.gitattributes`.
        'PSUseBOMForUnicodeEncodedFile'
    )
}
