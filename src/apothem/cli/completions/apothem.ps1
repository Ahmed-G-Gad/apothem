# SPDX-License-Identifier: MIT

# Apothem shell completion for PowerShell.
# Append to your PowerShell profile ($PROFILE) to enable, then restart the shell:
#   apothem completion powershell >> $PROFILE
Register-ArgumentCompleter -Native -CommandName apothem -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)
    $env:_APOTHEM_COMPLETE = "powershell_complete"
    $env:COMP_WORDS = $commandAst.ToString()
    $env:COMP_CWORD = $cursorPosition
    try {
        apothem | ForEach-Object {
            $type, $value, $help = $_ -split ",", 3
            if ($value) {
                $tooltip = if ($help) { $help } else { $value }
                [System.Management.Automation.CompletionResult]::new(
                    $value, $value, 'ParameterValue', $tooltip
                )
            }
        }
    } finally {
        Remove-Item Env:_APOTHEM_COMPLETE
        Remove-Item Env:COMP_WORDS
        Remove-Item Env:COMP_CWORD
    }
}

