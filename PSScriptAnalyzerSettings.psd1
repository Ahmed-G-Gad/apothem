# SPDX-License-Identifier: MIT

@{
    # PSScriptAnalyzer settings for the repository's PowerShell scripts. This
    # file is the single source of the severities and excluded rules for both
    # CI callers, which pass no other filter:
    #
    #   - `.github/workflows/installer-lint.yml` lints `scripts/installer/`
    #     on every pull request to main.
    #   - `.github/workflows/publish-static-site.yml` lints the copies it
    #     stages in `site/dist/` before each Pages deploy.
    #
    # Both run, from the repository root:
    #
    #     Invoke-ScriptAnalyzer -Path <dir> -Settings PSScriptAnalyzerSettings.psd1
    #
    # Always pass `-Settings`. `Invoke-ScriptAnalyzer` loads this file on its
    # own only when `-Path` is the repository root or a file in it, so a run
    # on `scripts/installer/` without the flag applies no exclusions.
    # A command-line `-Severity` or `-ExcludeRule` is merged with the values
    # below and can only widen them, so set a severity or a rule exclusion
    # here, never at a call site.
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
        'PSUseBOMForUnicodeEncodedFile',
        # Moved here from the Static Site build's `-ExcludeRule` list so
        # that both CI callers read one list. The rule flags a function
        # named New-, Set-, Remove-, Start-, Stop-, Restart-, Reset- or
        # Update- that does not declare `SupportsShouldProcess`. No
        # PowerShell script in this repository defines such a function.
        'PSUseShouldProcessForStateChangingFunctions'
    )
}
