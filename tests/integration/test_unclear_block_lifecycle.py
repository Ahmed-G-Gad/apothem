# SPDX-License-Identifier: MIT

"""A recorded managed block that a code block of the operator's now holds.

For every adapter that writes a Markdown managed block, through the real CLI
on a clean HOME (and project): install, then put the block inside a code block
of the operator's that a later fence closes, as an operator who left a fence
open above it and added an example below would. No rule can say whether that
marker pair is Apothem's block or a quote of the operator's, so:

* a re-install changes no byte of the file, adds no second block, names the
  file and the line of the code block in a warning, and ends as partial
  (exit code 2), since the tool gets no current block from that file;
* verify fails until the operator fixes the file, and still reads the tool as
  installed;
* uninstall removes Apothem's other files, keeps every byte of the file,
  names it in a warning, and stays unfinished (exit code 2): the install
  record stays, so the next install still leaves the file as it is and the
  next uninstall names it again, until the operator fixes it.

That holds only when the merge sees the file's install record, so a harness
whose record is kept under another root than the one the merge reads would
show up here as a second block. A stray BEGIN marker whose END marker is
quoted in code above the real block, and an anchor saved with CR line endings,
are run through the CLI the same way.

The uninstall's text for such a stray BEGIN marker is followed too, with and
without an install record: you follow its numbered fix for the case that the
last pair is Apothem's block, which changes each BEGIN marker of yours; the
uninstall run again then finishes, and a later install or update keeps every
line of yours.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner

from apothem.cli import main
from apothem.lib import install_ledger
from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    complete_managed_block,
)
from apothem.lib.harness_registry import (
    HARNESS_REGISTRY,
    HarnessRegistryEntry,
    package_key_for_public_id,
)
from apothem.schemas import profile_minimal_path
from tests.unit.test_marker_fix_steps import _fixes
from tests.unit.test_marker_fix_steps import _follow as _follow_fix

_IDS = [entry.public_id for entry in HARNESS_REGISTRY]
_PROFILE = str(profile_minimal_path())


class _Sandbox:
    """A clean HOME and project, plus a CLI runner bound to one harness."""

    def __init__(
        self, entry: HarnessRegistryEntry, tmp_path: Path, mp: pytest.MonkeyPatch
    ) -> None:
        self.entry = entry
        self.home = tmp_path / "home"
        self.project = tmp_path / "project"
        self.home.mkdir()
        self.project.mkdir()
        mp.setenv("HOME", str(self.home))
        mp.setenv("USERPROFILE", str(self.home))
        mp.delenv("CODEX_HOME", raising=False)
        mp.delenv("XDG_CONFIG_HOME", raising=False)
        mp.delenv("OPENCLAW_WORKSPACE_DIR", raising=False)
        if entry.public_id == "open-claw":
            # A workspace OpenClaw has set up, so the install writes its rules
            # file there.
            workspace = self.home / ".openclaw" / "workspace"
            workspace.mkdir(parents=True)
            (workspace / "AGENTS.md").write_bytes(b"# My agent\n")
            (workspace / "SOUL.md").write_bytes(b"soul\n")

    def scope(self) -> list[str]:
        if self.entry.scope == "project":
            return ["--project", str(self.project)]
        return []

    def invoke(self, *args: str) -> tuple[int, str]:
        result = CliRunner().invoke(
            main, [*args, "--harness", self.entry.public_id, *self.scope()]
        )
        return result.exit_code, result.output

    def run(self, *args: str) -> dict[str, Any]:
        code, output = self.invoke(*args, "--json")
        assert code == 0, output
        payload: dict[str, Any] = json.loads(output)
        return payload

    def install(self) -> dict[str, Any]:
        return self.run("install", "--profile", _PROFILE)

    def partial(self, *args: str) -> dict[str, Any]:
        """Run *args* with --json over a file it leaves as it is.

        The run ends as partial: exit code 2, status ``partial``, and the
        file's warning carries ``left_as_is``.
        """
        code, output = self.invoke(*args, "--json")
        assert code == 2, output
        payload: dict[str, Any] = json.loads(output)
        assert payload["status"] == "partial", payload["status"]
        assert [
            w for w in payload["warnings"] if w.get("detail", {}).get("left_as_is")
        ], payload["warnings"]
        return payload


SandboxFactory = Callable[[str], _Sandbox]


@pytest.fixture
def sandbox_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SandboxFactory:
    def make(harness_id: str) -> _Sandbox:
        entry = next(e for e in HARNESS_REGISTRY if e.public_id == harness_id)
        return _Sandbox(entry, tmp_path, monkeypatch)

    return make


def _recorded_anchors(harness_id: str) -> list[Path]:
    """Return the managed-block files the latest install of *harness_id* wrote."""
    record = install_ledger.read_records(package_key_for_public_id(harness_id))[-1]
    anchors = [
        Path(target.path)
        for target in record.targets
        if target.mode == "sentinel_merge"
        and Path(target.path).suffix in {".md", ".mdc", ""}
        and Path(target.path).is_file()
    ]
    if not anchors:
        pytest.skip(f"{harness_id} writes no managed block on a clean install")
    return anchors


def _fence_around_the_block(anchor: Path, *, edit: bool) -> int:
    """Put *anchor*'s block in a code block the operator closes below it.

    With *edit*, a line inside the block is the operator's too, so the block no
    longer reads as the one an install writes: only the install record keeps
    the next install from adding a second block. Returns the 1-based line of
    the fence that opens the code block.
    """
    text = anchor.read_bytes().decode("utf-8")
    block = complete_managed_block(text)
    assert block is not None, text[:200]
    at = text.index(block)
    if edit:
        begin_end = at + len(APOTHEM_BLOCK_BEGIN) + 1
        text = text[:begin_end] + "a line I added\n" + text[begin_end:]
    head = text[:at] + "My notes:\n\n```\nmake test\n\n"
    tail = text[at:] + "\nMore examples:\n\n```sh\nls\n```\n"
    anchor.write_bytes((head + tail).encode("utf-8"))
    return head.count("\n") - 2


def _warnings_naming(payload: dict[str, Any], anchor: Path, line: int) -> list[str]:
    return [
        str(warning["message"])
        for warning in payload["warnings"]
        if anchor.name in str(warning["message"])
        and f"code block that opens at line {line}" in str(warning["message"])
    ]


def _other_files(harness_id: str, anchors: list[Path]) -> list[Path]:
    """Return the paths besides *anchors* the latest install record lists."""
    record = install_ledger.read_records(package_key_for_public_id(harness_id))[-1]
    return [
        Path(target.path)
        for target in record.targets
        if Path(target.path) not in anchors and Path(target.path).exists()
    ]


def _assert_uninstall_unfinished(
    box: _Sandbox, anchors: list[Path], others: list[Path]
) -> None:
    """Uninstall: it runs, names each anchor once, removes the rest, stays open.

    lifecycle-1: one of the pairs may be Apothem's block, so the uninstall
    does not finish (exit code 2) and the install record stays.
    """
    code, output = box.invoke("uninstall", "--yes", "--json")
    assert code == 2, output
    payload = json.loads(output)
    assert "not installed" not in json.dumps(payload["results"]), payload["results"]
    for anchor in anchors:
        named = [
            warning
            for warning in payload["warnings"]
            if warning.get("detail", {}).get("kept_reason") == "unclear-block"
            and Path(str(warning["path"])) == anchor
        ]
        assert len(named) == 1, payload["warnings"]
        assert named[0]["detail"]["marker_left"] == "1"
    assert [
        row
        for row in payload["results"]
        if "marker lines Apothem cannot tell from your text" in str(row["message"])
    ], payload["results"]
    assert _kinds(box)[-1] == "uninstall-incomplete"
    assert others, "the install wrote no other file to check"
    assert [path for path in others if not path.exists()], others


def _kinds(box: _Sandbox) -> list[str]:
    """Return the kinds of the sandbox harness's ledger records, in order."""
    key = package_key_for_public_id(box.entry.public_id)
    return [record.kind for record in install_ledger.read_records(key)]


@pytest.mark.parametrize(
    ("harness_id", "edit"),
    [
        *[(harness_id, True) for harness_id in _IDS],
        ("codex", False),
        ("claude-code", False),
    ],
)
def test_a_recorded_block_inside_an_operator_code_block_is_left_alone(
    harness_id: str, edit: bool, sandbox_factory: SandboxFactory
) -> None:
    box = sandbox_factory(harness_id)
    box.install()
    anchors = _recorded_anchors(harness_id)
    others = _other_files(harness_id, anchors)
    lines = {anchor: _fence_around_the_block(anchor, edit=edit) for anchor in anchors}
    before = {anchor: anchor.read_bytes() for anchor in anchors}

    again = box.partial("install", "--profile", _PROFILE)
    after_install = {anchor: anchor.read_bytes() for anchor in anchors}
    verify, verify_output = box.invoke("verify", "--json")
    _assert_uninstall_unfinished(box, anchors, others)
    after_uninstall = {anchor: anchor.read_bytes() for anchor in anchors}

    assert after_install == before
    for anchor in anchors:
        assert after_install[anchor].count(APOTHEM_BLOCK_BEGIN.encode()) == 1
        assert _warnings_naming(again, anchor, lines[anchor]), again["warnings"]
    assert verify != 0, verify_output
    assert json.loads(verify_output)["installed"] is True
    assert after_uninstall == before


@pytest.mark.parametrize("harness_id", ["codex", "claude-code"])
def test_a_stray_begin_whose_end_is_quoted_in_code_cuts_nothing(
    harness_id: str, sandbox_factory: SandboxFactory
) -> None:
    """residual-1: re-install and uninstall keep every line; verify fails."""
    box = sandbox_factory(harness_id)
    box.install()
    [anchor] = _recorded_anchors(harness_id)
    others = _other_files(harness_id, [anchor])
    stray = (
        f"{APOTHEM_BLOCK_BEGIN}\nop text A\n```\n{APOTHEM_BLOCK_END}\n```\n"
        "op text B\n\n"
    ).encode()
    anchor.write_bytes(stray + anchor.read_bytes())
    before = anchor.read_bytes()

    again = box.partial("install", "--profile", _PROFILE)
    after_install = anchor.read_bytes()
    verify, verify_output = box.invoke("verify", "--json")
    _assert_uninstall_unfinished(box, [anchor], others)

    assert after_install == before
    assert _warnings_naming(again, anchor, 3), again["warnings"]
    assert verify != 0, verify_output
    assert json.loads(verify_output)["installed"] is True
    assert anchor.read_bytes() == before


@pytest.mark.parametrize("harness_id", ["codex", "claude-code"])
def test_an_unclear_block_keeps_the_install_open_until_you_fix_it(
    harness_id: str, sandbox_factory: SandboxFactory, tmp_path: Path
) -> None:
    """lifecycle-1: the uninstall used to finish and close the install record.

    The tool kept loading the old block, a later install added a second
    block beside it without a word, and the next uninstall left the old one
    for good. Now the record stays: the install leaves the file as it is and
    names it, and the next uninstall names it again and stays unfinished.
    """
    box = sandbox_factory(harness_id)
    box.install()
    [anchor] = _recorded_anchors(harness_id)
    line = _fence_around_the_block(anchor, edit=True)
    before = anchor.read_bytes()

    first, first_output = box.invoke("uninstall", "--yes", "--json")
    again = box.partial("install", "--profile", _profile_with(tmp_path, ["A rule."]))
    after_install = anchor.read_bytes()
    second, second_output = box.invoke("uninstall", "--yes", "--json")

    assert first == 2, first_output
    assert after_install == before
    assert _warnings_naming(again, anchor, line), again["warnings"]
    assert second == 2, second_output
    assert _unclear_text(json.loads(second_output), anchor)
    assert _kinds(box)[-1] == "uninstall-incomplete"
    assert anchor.read_bytes() == before


@pytest.mark.parametrize("harness_id", ["codex", "claude-code"])
def test_a_new_profile_adds_no_second_block_beside_your_code_block(
    harness_id: str, sandbox_factory: SandboxFactory, tmp_path: Path
) -> None:
    """lifecycle-r4-1: why the install record holds such a file back.

    Apothem's block, as the install wrote it, sits in a code block of yours,
    and the profile has changed since, so the pair matches no block this
    release renders for it. Holding back only a pair that matches such a
    block would add a second block here, which the tool would load beside
    the old one; the install record holds the file back instead, and the
    update ends as partial.
    """
    box = sandbox_factory(harness_id)
    box.install()
    [anchor] = _recorded_anchors(harness_id)
    line = _fence_around_the_block(anchor, edit=False)
    before = anchor.read_bytes()

    again = box.partial("update", "--profile", _profile_with(tmp_path, ["A rule."]))

    assert anchor.read_bytes() == before
    assert before.count(APOTHEM_BLOCK_BEGIN.encode()) == 1
    assert _warnings_naming(again, anchor, line), again["warnings"]


def test_an_anchor_saved_with_cr_endings_shows_no_drift(
    sandbox_factory: SandboxFactory,
) -> None:
    """cr-5: line endings do not count, CR alone included."""
    box = sandbox_factory("codex")
    box.install()
    [anchor] = _recorded_anchors("codex")
    anchor.write_bytes(
        anchor.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r")
    )

    code, output = box.invoke("verify", "--profile", _PROFILE)
    box.install()
    again, again_output = box.invoke("verify", "--profile", _PROFILE)

    assert code == 0, output
    assert again == 0, again_output


# --- following the uninstall's text ---------------------------------------------

B = APOTHEM_BLOCK_BEGIN
E = APOTHEM_BLOCK_END

#: A BEGIN marker of yours whose END marker you quote in a code block (lines
#: 1 to 4), above Apothem's block; every line of yours starts with "OP ".
_STRAY = f"{B}\nOP text A\n```\n{E}\n```\nOP text B\n\n"
#: The same under another BEGIN marker of yours, one that starts no pair.
_TWO_BEGINS = f"{B}\nOP stray\n\n{_STRAY}"
#: A rule whose code block Apothem's block never closes, so its END marker
#: reads as code too.
_OPEN_RULE = "Run the tests with:\n```bash"


def _block_file(harness_id: str) -> Path:
    """Return the one file the install keeps Apothem's block in.

    For Open-Claw it is the rules file in the workspace, apothem/AGENTS.md.
    """
    anchors = _recorded_anchors(harness_id)
    if harness_id == "open-claw":
        anchors = [a for a in anchors if a.parts[-2:] == ("apothem", "AGENTS.md")]
    [anchor] = anchors
    return anchor


def _op_lines(anchor: Path) -> list[str]:
    """Return the lines of yours in *anchor*, in order."""
    return [
        line
        for line in anchor.read_bytes().decode("utf-8").split("\n")
        if line.startswith("OP ")
    ]


def _unclear_text(payload: dict[str, Any], anchor: Path) -> str:
    """Return the one warning that names *anchor* as a file Apothem cannot read."""
    [message] = [
        str(warning["message"])
        for warning in payload["warnings"]
        if warning.get("detail", {}).get("kept_reason") == "unclear-block"
        and Path(str(warning["path"])) == anchor
    ]
    return message


def _follow(anchor: Path, message: str) -> None:
    """Edit *anchor* as you would after reading the uninstall's *message*.

    Apothem's block is the last marker pair the text names, so follow the
    numbered fix for the case that it is Apothem's block, step by step in the
    order printed: it changes each BEGIN marker of yours and each that starts
    no pair.
    """
    fixes = [
        (int(claim[1]), fix)
        for label, fix in _fixes(message)
        if (claim := re.fullmatch(r"lines (\d+) to \d+ are Apothem's block", label))
    ]
    _, fix = max(fixes)
    text = anchor.read_bytes().decode("utf-8")
    lines = text.split("\n")[:-1] if text.endswith("\n") else text.split("\n")
    kept, _, _ = _follow_fix(lines, fix)
    anchor.write_bytes("".join(f"{line}\n" for line in kept).encode("utf-8"))


def _profile_with(tmp_path: Path, rules: list[str]) -> str:
    """Write the minimal profile with *rules* added; return its path."""
    data = yaml.safe_load(Path(_PROFILE).read_text(encoding="utf-8"))
    data["rules"] = rules
    path = tmp_path / "profile-with-rules.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return str(path)


def _assert_your_lines_kept(box: _Sandbox, anchor: Path, mine: list[str]) -> None:
    """Your lines are all there, with one BEGIN marker (Apothem's); verify passes."""
    verify, verify_output = box.invoke("verify", "--json")
    assert _op_lines(anchor) == mine
    assert anchor.read_bytes().count(B.encode()) == 1
    assert verify == 0, verify_output


@pytest.mark.parametrize(
    ("harness_id", "above"),
    [
        pytest.param("codex", _STRAY, id="codex"),
        pytest.param("claude-code", _STRAY, id="claude-code"),
        pytest.param("open-claw", _STRAY, id="open-claw"),
        pytest.param("codex", _TWO_BEGINS, id="codex-two-begins"),
    ],
)
def test_following_the_uninstall_text_keeps_your_lines(
    harness_id: str, above: str, sandbox_factory: SandboxFactory
) -> None:
    """regress-1, messages-1, diff-1, diff-2: the later install then cuts nothing.

    Deleting only Apothem's block would leave your BEGIN marker and the END
    marker you quote as a whole block, which the install replaces. The
    uninstall stays unfinished until you follow its text (lifecycle-1); run
    again then, it finishes.
    """
    box = sandbox_factory(harness_id)
    box.install()
    anchor = _block_file(harness_id)
    anchor.write_bytes(above.encode() + anchor.read_bytes())
    mine = _op_lines(anchor)

    code, output = box.invoke("uninstall", "--yes", "--json")
    assert code == 2, output
    _follow(anchor, _unclear_text(json.loads(output), anchor))
    again, again_output = box.invoke("uninstall", "--yes")
    finished = _kinds(box)[-1]
    box.install()

    assert again == 0, again_output
    assert finished == "uninstall"
    _assert_your_lines_kept(box, anchor, mine)


@pytest.mark.parametrize("harness_id", ["codex", "claude-code"])
def test_following_the_uninstall_text_without_a_record_keeps_your_lines(
    harness_id: str, sandbox_factory: SandboxFactory
) -> None:
    """messages-2: the uninstall stays unfinished; the update it names cuts nothing."""
    box = sandbox_factory(harness_id)
    box.install()
    [anchor] = _recorded_anchors(harness_id)
    anchor.write_bytes(_STRAY.encode() + anchor.read_bytes())
    mine = _op_lines(anchor)
    install_ledger.ledger_path(package_key_for_public_id(harness_id)).unlink()

    code, output = box.invoke("uninstall", "--yes", "--json")
    assert code == 2, output
    _follow(anchor, _unclear_text(json.loads(output), anchor))
    box.run("update", "--profile", _PROFILE)

    _assert_your_lines_kept(box, anchor, mine)


def test_following_the_text_when_a_rule_leaves_a_code_block_open_keeps_your_lines(
    sandbox_factory: SandboxFactory, tmp_path: Path
) -> None:
    """oracle-1: Apothem's END marker reads as code too, so its pair is named apart.

    The block is one an earlier release wrote: this release closes the code
    block the rule opens before the END marker (markers-4), so here that
    closer is taken out again. The install text's fix for that pair changes
    your BEGIN marker at line 1 as well, and so does the uninstall's.
    """
    box = sandbox_factory("codex")
    profile = _profile_with(tmp_path, [_OPEN_RULE])
    box.run("install", "--profile", profile)
    [anchor] = _recorded_anchors("codex")
    lines = anchor.read_bytes().decode("utf-8").split("\n")
    end = lines.index(E)
    assert lines[end - 1] == "```", lines[end - 3 : end + 1]
    earlier = "\n".join([*lines[: end - 1], *lines[end:]])
    anchor.write_bytes(_STRAY.encode() + earlier.encode())
    mine = _op_lines(anchor)

    again = box.partial("install", "--profile", profile)
    code, output = box.invoke("uninstall", "--yes", "--json")
    assert code == 2, output
    _follow(anchor, _unclear_text(json.loads(output), anchor))
    finished, finished_output = box.invoke("uninstall", "--yes")
    box.run("install", "--profile", profile)

    assert finished == 0, finished_output
    _assert_your_lines_kept(box, anchor, mine)
    assert [
        warning
        for warning in again["warnings"]
        if "Change line 1: add a word inside its comment." in str(warning["message"])
    ], again["warnings"]
