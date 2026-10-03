# SPDX-License-Identifier: MIT

"""Per-subcommand ``--help`` epilog blocks for the apothem CLI.

Each block carries Examples, Related commands, and Exit codes. The blocks are
line-structured, so every paragraph is marked with Click's no-rewrap marker
(see :func:`_keep_line_structure` at the end of this module); without it Click
re-flows each list into one run-on paragraph.
"""

from __future__ import annotations

_EP_INSTALL = """
Examples:
  apothem install --harness claude-code
  apothem install --harness all --project .
  apothem install --harness claude-code --dry-run
  apothem install --harness cursor --profile ~/profile.yaml --json

Related commands:
  installing  Continuous-form alias for install
  update      Re-apply current profile to a harness
  uninstall   Remove a harness configuration
  verify      Check installation status

Exit codes:
  0  Adapter installed successfully
  1  Expected validation, profile, harness, project, or adapter error
  2  Partial batch materialization after at least one write
  64 Usage error: unknown option or command, or a missing or invalid value
"""

_EP_UNINSTALL = """
Examples:
  apothem uninstall --harness claude-code
  apothem uninstall --harness all --project . --yes
  apothem uninstall --harness claude-code --yes

Related commands:
  install      Install a harness configuration
  uninstalling Continuous-form alias for uninstall
  verify       Check installation status

Exit codes:
  0  Adapter uninstalled or was not installed
  1  Harness not found, confirmation declined or unavailable
     (non-interactive or JSON mode without --yes), or every removal failed
  2  Partial removal — at least one harness removed before a failure
  64 Usage error: unknown option or command, or a missing or invalid value
"""

_EP_ROLLBACK = """
Examples:
  apothem rollback --harness claude-code --last
  apothem rollback --harness claude-code --install-id 01J9Z…  --yes
  apothem rollback --harness cursor --project . --last --json

Related commands:
  install    Install a harness configuration
  uninstall  Remove a harness configuration
  verify     Check installation status

Exit codes:
  0  Pre-install state restored from the recorded backups
  1  No matching install record, unknown install-id, harness/project error,
     or confirmation declined or unavailable without --yes
  2  Partial restore after at least one backup was restored
  64 Usage error: unknown option or command, or a missing or invalid value
"""

_EP_UPDATE = """
Examples:
  apothem update --harness claude-code
  apothem update --harness all --project .
  apothem update --harness claude-code --dry-run

Related commands:
  install   Install a harness configuration
  updating  Continuous-form alias for update
  verify    Check installation status

Exit codes:
  0  Adapter updated successfully
  1  Expected validation, profile, harness, project, or adapter error
  2  Partial batch materialization after at least one write
  64 Usage error: unknown option or command, or a missing or invalid value
"""

_EP_VERIFY = """
Examples:
  apothem verify --harness claude-code
  apothem verify --harness all --project .
  apothem verify --harness claude-code --profile ~/profile.yaml
  apothem verify --harness claude-code --json

Notes:
  Without --profile the check is structural (targets present and valid).
  With --profile it also requires fidelity: a drifted install fails verify.

Related commands:
  install Install a harness configuration
  update  Re-apply current profile to a harness
  status  Report install/verify/drift across every harness

Exit codes:
  0  Harness is verified (with --profile, also faithful to it)
  1  Harness is not verified (missing/invalid, or drifted from --profile)
  64 Usage error: unknown option or command, or a missing or invalid value
"""

_EP_STATUS = """
Examples:
  apothem status
  apothem status --project .
  apothem status --profile ~/profile.yaml
  apothem status --json

Notes:
  --profile selects the drift baseline; without it the default profile
  (~/.config/apothem/profile.yaml) is used.

Related commands:
  verify          Verify a specific harness installation
  diff            Preview pending changes for a harness
  harnesses list  List all registered harnesses

Exit codes:
  0  Status reported (drift is reported, not an error)
  1  Expected validation error (invalid --profile or missing --project path)
  2  At least one adapter failed to report its status
  64 Usage error: unknown option or command, or a missing or invalid value
"""

_EP_DIFF = """
Examples:
  apothem diff --harness claude-code
  apothem diff --harness cursor --project .
  apothem diff --harness claude-code --json

Related commands:
  status   Report install/verify/drift across every harness
  verify   Verify a specific harness installation
  install  Apply the previewed changes

Exit codes:
  0  Diff reported (pending changes are reported, not an error)
  1  Expected validation, profile, harness, or project error
  64 Usage error: unknown option or command, or a missing or invalid value
"""

_EP_DOCTOR = """
Examples:
  apothem doctor
  apothem doctor --project .
  apothem doctor --json

Checks each installed harness: its verify must pass and every hook command
its install registered must start (run with a no-op payload). A harness that
is not installed is reported, not failed. Project-scope harnesses are checked
when --project names their root.

Related commands:
  harnesses list  List all registered harnesses
  verify          Check a specific harness

Exit codes:
  0  All checks passed (also when no harness is installed yet)
  1  An installed harness does not verify, a registered hook command cannot
     start, an adapter could not be loaded or probed, or the shared profile
     is present but failed schema validation
  64 Usage error: unknown option or command, or a missing or invalid value
"""

_EP_PROFILE_SHOW = """
Examples:
  apothem profile show
  apothem profile show --json

Related commands:
  profile init  Create a schema-valid shared profile
  profile set   Set a key in the shared profile
  profile edit  Open the profile in the system editor

Exit codes:
  0  Success
  1  Profile missing or invalid
  64 Usage error: unknown option or command, or a missing or invalid value
"""

_EP_PROFILE_INIT = """
Examples:
  apothem profile init
  apothem profile init --profile ./profile.yaml --force

Related commands:
  profile show  Display the shared profile
  profile edit  Open the profile in the system editor

Exit codes:
  0  Profile scaffold created
  1  Profile exists or cannot be written
  64 Usage error: unknown option or command, or a missing or invalid value
"""

_EP_PROFILE_SET = """
Examples:
  apothem profile set identity.name "Ada Lovelace"
  apothem profile set preferences.style concise
  apothem profile set seriousness SHARED
  apothem profile set enforcement.sprints true

KEY is a dotted path into the profile; VALUE is stored literally (bare words are
not coerced) except true/false and explicit [..]/{..} input. The result is
validated against the schema before writing; an invalid set is refused.

Related commands:
  profile show  Display the shared profile
  profile edit  Open the profile in the system editor

Exit codes:
  0  Key set successfully
  1  Invalid key, value, or unwritable profile (profile unchanged)
  64 Usage error: unknown option or command, or a missing or invalid value
"""

_EP_PROFILE_EDIT = """
Examples:
  apothem profile edit

Related commands:
  profile show  Display the shared profile
  profile set   Set a key in the shared profile

Exit codes:
  0  Editor exited normally
  64 Usage error: unknown option or command, or a missing or invalid value
"""

_EP_HARNESSES_LIST = """
Examples:
  apothem harnesses list
  apothem harnesses list --json

Related commands:
  harnesses show  Show details for a specific harness
  doctor          Run system diagnostics

Exit codes:
  0  Success
  1  Every adapter failed to load or report
  2  At least one adapter listed, at least one failed
  64 Usage error: unknown option or command, or a missing or invalid value
"""

_EP_HARNESSES_SHOW = """
Examples:
  apothem harnesses show claude-code
  apothem harnesses show claude-code --json

Related commands:
  harnesses list  List all registered harnesses

Exit codes:
  0  Success
  1  Harness not found
  64 Usage error: unknown option or command, or a missing or invalid value
"""

_EP_BACKUPS_PRUNE = """
Examples:
  apothem backups prune
  apothem backups prune --keep 3 --dry-run
  apothem backups prune --harness claude-code --keep 1 --json

A backup set that a kept install record, or the latest install record of any
install root, still references is never removed, so rollback of the latest
install keeps working.

Related commands:
  rollback   Restore a harness to the state before its recorded install
  uninstall  Remove a harness configuration

Exit codes:
  0  Pruned, or nothing to prune
  1  Unknown harness, or no harness could be pruned (unreadable ledger, or a
     backup set that could not be removed)
  2  Partial prune: at least one harness pruned before a failure
  64 Usage error: unknown option or command, or a missing or invalid value
     (including --keep below 1)
"""

_EP_COMPLETION = """
Examples:
  apothem completion bash >> ~/.bashrc
  apothem completion zsh  >> ~/.zshrc
  apothem completion fish > ~/.config/fish/completions/apothem.fish
  apothem completion powershell >> $PROFILE

Enabling completion is opt-in — this command only prints the script; it never
edits your shell startup files. Append the output to the file shown above (or
source it ad-hoc), then restart the shell.

Exit codes:
  0  Completion script emitted
  64 Unsupported shell requested, or another usage error
"""

_EP_QUICKSTART = """
Examples:
  apothem quickstart
  apothem quickstart --harness claude-code --yes
  apothem quickstart --harness all --project . --yes
  apothem quickstart --harness claude-code --json

Without --harness, quickstart asks which harness to install; a run that
cannot ask (--yes, --json, or no terminal) must name one. 'all' installs
every supported harness and is never the default.

Related commands:
  install   Materialize a harness from the shared profile
  verify    Confirm an installation is live
  doctor    Check environment + installation health

Exit codes:
  0  Guided run completed
  1  Expected validation, profile, harness, project, or adapter error
  2  Partial batch materialization after at least one write
  64 Usage error: unknown option or command, or a missing or invalid value
"""

_EP_MIGRATE_WORKSPACE = """
Examples:
  apothem migrate-workspace
  apothem migrate-workspace --project .
  apothem migrate-workspace --dry-run --json

Migrates a legacy per-harness data home (.apothem/<harness>/...) and a legacy
.plans/ tree into the single shared .apothem/{plans,memory,learning,contexts}
working directory. Per-harness memory/contexts/learning stores union-merge by
id; learning signals concatenate-dedup; .plans/ moves under .apothem/plans/.
Every consumed source is backed up first; a conflicting record is skipped, never
overwritten. The migration is idempotent — re-running on a migrated tree is a
no-op.

Related commands:
  install   Materialize a harness from the shared profile
  status    Report installed harnesses + drift

Exit codes:
  0  Migration completed (or no legacy layout found)
  1  Expected validation or project error
  64 Usage error: unknown option or command, or a missing or invalid value
"""


def _keep_line_structure(epilog: str) -> str:
    """Prefix every paragraph of *epilog* with Click's no-rewrap marker.

    Click re-wraps help text paragraph by paragraph; a paragraph whose first
    line is ``\\b`` is printed with its line breaks and indentation intact.
    """
    paragraphs = epilog.strip("\n").split("\n\n")
    return "\n" + "\n\n".join(f"\b\n{paragraph}" for paragraph in paragraphs) + "\n"


# Mark every epilog defined above, so a new _EP_* block cannot forget it.
for _name, _value in list(globals().items()):
    if _name.startswith("_EP_") and isinstance(_value, str):
        globals()[_name] = _keep_line_structure(_value)
