# SPDX-License-Identifier: MIT

"""An unedited copy of an earlier release's template is still Apothem's.

An operator-owned ``write_text`` entry that targets a plain-text file (not
JSON or YAML, which the structured stripper handles key by key) is deleted on
uninstall only while it is an unedited template. A release that changes the
template would strand every unedited copy an earlier release wrote, so the
manifest entry lists the SHA-256 digest of each earlier shipped text
(``earlier_digests``) and the removal accepts a match with any of them.

This module pins the loader checks, the removal rule, and a guard that fails
when a shipped template changes without its previous digest recorded. The
guard has two layers: a hardcoded record of the latest release's digests that
runs everywhere (a CI checkout is shallow and has no tags), and a check
against every release tag that runs wherever the tags are present. The
release-preflight CI job checks out every tag and runs this module, and a
test there fails once a release newer than the pinned one exists, so the
record cannot go stale unnoticed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver_removal import _plain_file_remainder
from apothem.harnesses.glm import GlmAdapter
from apothem.lib import propagation
from apothem.lib.install_ledger import LedgerTarget

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STRUCTURED_SUFFIXES = {".json", ".yaml", ".yml"}

#: The latest release the guard pins, and the digest of each plain-file
#: template as that release shipped it, keyed by (harness, manifest source).
#: Refresh both when a release is cut; the git-backed test below checks every
#: digest here against the tag.
_LATEST_RELEASE = "v1.3.0"
_LATEST_RELEASE_DIGESTS = {
    ("glm", "harnesses/glm/templates/glm.toml"): (
        "bbea03200583fb815a36c50fd0b093ea120b1bdcf7e79d85fbf404b2ff261a31"
    ),
}

#: The last release whose glm.toml differs from the current template, and that
#: copy's digest. The GLM uninstall tests write this copy, so they keep testing
#: an earlier text when the latest release ships the current one.
_GLM_EARLIER_RELEASE = "v1.2.2"
_GLM_EARLIER_DIGEST = "12b32d3e8dfb53d85b8ac702e6d335a6617a140bf66015cc2f18a7a4a302fc10"
_GLM_EARLIER_FIXTURE = (
    _REPO_ROOT / "tests" / "fixtures" / "templates" / "glm-v1.2.2.toml"
)

_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64


def _plain_file_entries() -> list[tuple[str, propagation.InstallEntry]]:
    """Return every operator-owned ``write_text`` entry aimed at a plain file.

    JSON and YAML targets are stripped key by key and never compared as a
    whole, so a template change needs no digest there.
    """
    found: list[tuple[str, propagation.InstallEntry]] = []
    for harness, rules in propagation.load_manifest().items():
        for entry in rules.install:
            if (
                entry.mode == "write_text"
                and entry.ownership_class == "operator-owned"
                and Path(entry.target).suffix.lower() not in _STRUCTURED_SUFFIXES
            ):
                found.append((harness, entry))
    return found


def _current_digest(entry: propagation.InstallEntry) -> str:
    source = install_driver.resolve_source(entry.source)
    return propagation.text_digest(source.read_text(encoding="utf-8"))


def _git(*args: str) -> subprocess.CompletedProcess[bytes] | None:
    try:
        return subprocess.run(  # fixed argv, no shell
            ["git", *args],  # git on PATH
            cwd=_REPO_ROOT,
            capture_output=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _release_tags() -> list[str]:
    done = _git("tag", "--list", "v[0-9]*")
    if done is None or done.returncode != 0:
        return []
    return done.stdout.decode("utf-8").split()


def _text_at_tag(tag: str, source: str) -> str | None:
    """Return a source file as *tag* shipped it, or ``None`` if it did not."""
    done = _git("show", f"{tag}:src/apothem/{source}")
    if done is None or done.returncode != 0:
        return None
    return done.stdout.decode("utf-8")


def _require_release_tags() -> list[str]:
    """Return the release tags, skipping only where the checkout carries none.

    A CI checkout is shallow and has no tags; the hardcoded latest-release
    record still guards there. Where tags are present, a pinned release that
    is not among them is a stale or mistyped pin, so the test fails.
    """
    tags = _release_tags()
    if not tags:
        pytest.skip("this checkout carries no release tags")
    assert _LATEST_RELEASE in tags, (
        f"_LATEST_RELEASE names {_LATEST_RELEASE}, which is not a tag here; "
        "fix the pin or run git fetch --tags"
    )
    return tags


def _target(*, created: bool | None) -> LedgerTarget:
    return LedgerTarget(
        path="/p/file.toml",
        mode="write_text",
        ownership_class="operator-owned",
        created=created,
    )


def _manifest(entry_fields: str) -> str:
    return (
        "harnesses:\n"
        "  demo:\n"
        "    install:\n"
        "      - source: a.toml\n"
        "        target: b.toml\n" + entry_fields
    )


# --- loader ---------------------------------------------------------------


def test_text_digest_ignores_line_ending_style() -> None:
    assert propagation.text_digest("a\r\nb\n") == propagation.text_digest("a\nb\n")
    assert propagation.text_digest("a\nb\n") != propagation.text_digest("a\nc\n")


def test_earlier_digests_parse_in_order() -> None:
    rules = propagation._parse_manifest_text(
        _manifest(
            "        mode: write_text\n"
            "        ownership_class: operator-owned\n"
            "        earlier_digests:\n"
            f'          - "{_DIGEST_A}"\n'
            f'          - "{_DIGEST_B}"\n'
        )
    )
    (entry,) = rules["demo"].install
    assert entry.earlier_digests == (_DIGEST_A, _DIGEST_B)


def test_earlier_digests_default_to_none() -> None:
    rules = propagation._parse_manifest_text(
        _manifest("        mode: write_text\n        ownership_class: operator-owned\n")
    )
    assert rules["demo"].install[0].earlier_digests == ()


@pytest.mark.parametrize(
    ("digests", "message"),
    [
        ('"abc"', "64-character"),
        ('"' + "A" * 64 + '"', "64-character"),
        ("42", "64-character"),
        (f'"{_DIGEST_A}", "{_DIGEST_A}"', "twice"),
    ],
)
def test_earlier_digests_reject_a_malformed_list(digests: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        propagation._parse_manifest_text(
            _manifest(
                "        mode: write_text\n"
                "        ownership_class: operator-owned\n"
                f"        earlier_digests: [{digests}]\n"
            )
        )


def test_earlier_digests_must_be_a_list() -> None:
    with pytest.raises(ValueError, match="must be a list"):
        propagation._parse_manifest_text(
            _manifest(
                "        mode: write_text\n"
                "        ownership_class: operator-owned\n"
                f'        earlier_digests: "{_DIGEST_A}"\n'
            )
        )


@pytest.mark.parametrize(
    "fields",
    [
        "        mode: replace_tree\n        ownership_class: operator-owned\n",
        "        mode: write_text\n        ownership_class: apothem-owned\n",
    ],
)
def test_earlier_digests_only_belong_to_operator_owned_write_text(fields: str) -> None:
    with pytest.raises(ValueError, match="earlier_digests"):
        propagation._parse_manifest_text(
            _manifest(fields + f'        earlier_digests: ["{_DIGEST_A}"]\n')
        )


# --- removal --------------------------------------------------------------


def test_current_template_copy_is_deleted() -> None:
    text = "name = 1\n"
    assert (
        _plain_file_remainder(
            text, text, earlier_digests=(), recorded=_target(created=True)
        )
        is None
    )


def test_earlier_template_copy_is_deleted_when_apothem_created_it() -> None:
    old = "name = 0\n"
    remainder = _plain_file_remainder(
        old,
        "name = 1\n",
        earlier_digests=(propagation.text_digest(old),),
        recorded=_target(created=True),
    )
    assert remainder is None


def test_earlier_template_copy_is_kept_without_a_record() -> None:
    # No record means nothing shows Apothem wrote the earlier copy: the root
    # was never installed, was already uninstalled, or lost its ledger.
    old = "name = 0\n"
    assert (
        _plain_file_remainder(
            old,
            "name = 1\n",
            earlier_digests=(propagation.text_digest(old),),
            recorded=None,
        )
        == old
    )


def test_earlier_template_copy_is_deleted_with_a_legacy_record() -> None:
    # Ledger records before v1.2.0 carry no created flag; they still show
    # Apothem installed here, so an unedited earlier copy goes.
    old = "name = 0\n"
    assert (
        _plain_file_remainder(
            old,
            "name = 1\n",
            earlier_digests=(propagation.text_digest(old),),
            recorded=_target(created=None),
        )
        is None
    )


def test_current_template_copy_is_deleted_without_a_record() -> None:
    text = "name = 1\n"
    assert _plain_file_remainder(text, text, earlier_digests=(), recorded=None) is None


def test_earlier_template_copy_the_operator_placed_is_kept() -> None:
    old = "name = 0\n"
    assert (
        _plain_file_remainder(
            old,
            "name = 1\n",
            earlier_digests=(propagation.text_digest(old),),
            recorded=_target(created=False),
        )
        == old
    )


def test_current_template_copy_the_operator_placed_is_kept() -> None:
    text = "name = 1\n"
    assert (
        _plain_file_remainder(
            text, text, earlier_digests=(), recorded=_target(created=False)
        )
        == text
    )


def test_an_edited_earlier_copy_is_kept() -> None:
    old = "name = 0\n"
    edited = old + "extra = true\n"
    assert (
        _plain_file_remainder(
            edited,
            "name = 1\n",
            earlier_digests=(propagation.text_digest(old),),
            recorded=_target(created=True),
        )
        == edited
    )


def test_an_unrecorded_text_is_kept() -> None:
    old = "name = 0\n"
    assert (
        _plain_file_remainder(
            old, "name = 1\n", earlier_digests=(_DIGEST_A,), recorded=None
        )
        == old
    )


def _glm_provider(project: Path) -> Path:
    return project / ".apothem" / "providers" / "glm.toml"


def _glm_entry() -> propagation.InstallEntry:
    (entry,) = propagation.load_manifest()["glm"].install
    return entry


def _glm_earlier_text() -> str:
    """Return glm.toml as the last release with a different template shipped it.

    It is read from a committed copy so the uninstall tests run in a checkout
    without tags; a git-backed test below checks the copy against the tag.
    """
    old = _GLM_EARLIER_FIXTURE.read_text(encoding="utf-8")
    assert propagation.text_digest(old) == _GLM_EARLIER_DIGEST
    assert old != _glm_current_text()
    return old


def _glm_current_text() -> str:
    source = install_driver.resolve_source(_glm_entry().source)
    return source.read_text(encoding="utf-8")


def test_glm_records_the_digests_of_every_earlier_release() -> None:
    entry = _glm_entry()
    # v1.0.1 through v1.1.0, then v1.2.0 through v1.2.2.
    assert entry.earlier_digests == (
        "6cb35635c4b74bf83c4f0abd1800a4676ffba5d4c8165e18e73c53dc4cad787d",
        _GLM_EARLIER_DIGEST,
    )


def test_glm_uninstall_removes_an_unedited_copy_an_earlier_release_wrote(
    tmp_path: Path,
) -> None:
    old = _glm_earlier_text()
    project = tmp_path / "project"
    project.mkdir()
    adapter = GlmAdapter()
    adapter.install({}, project=project)
    provider = _glm_provider(project)
    provider.write_text(old, encoding="utf-8", newline="\n")

    adapter.uninstall(project=project)

    assert not provider.exists()


def test_glm_uninstall_keeps_an_earlier_copy_the_operator_placed(
    tmp_path: Path,
) -> None:
    old = _glm_earlier_text()
    project = tmp_path / "project"
    provider = _glm_provider(project)
    provider.parent.mkdir(parents=True)
    provider.write_text(old, encoding="utf-8", newline="\n")
    adapter = GlmAdapter()

    adapter.install({}, project=project)
    adapter.uninstall(project=project)

    assert provider.read_text(encoding="utf-8") == old


def test_glm_earlier_fixture_matches_the_tag() -> None:
    _require_release_tags()
    shipped = _text_at_tag(_GLM_EARLIER_RELEASE, _glm_entry().source)
    assert shipped == _glm_earlier_text()


def test_glm_uninstall_keeps_an_earlier_copy_without_an_install_record(
    tmp_path: Path,
) -> None:
    # A root Apothem never installed: nothing shows Apothem wrote this copy.
    old = _glm_earlier_text()
    project = tmp_path / "project"
    provider = _glm_provider(project)
    provider.parent.mkdir(parents=True)
    provider.write_text(old, encoding="utf-8", newline="\n")

    GlmAdapter().uninstall(project=project)

    assert provider.read_text(encoding="utf-8") == old


def test_glm_second_uninstall_keeps_an_earlier_copy_the_operator_placed(
    tmp_path: Path,
) -> None:
    # The first uninstall keeps the operator's file and closes the record, so
    # a second one runs without a record and must keep it too.
    old = _glm_earlier_text()
    project = tmp_path / "project"
    provider = _glm_provider(project)
    provider.parent.mkdir(parents=True)
    provider.write_text(old, encoding="utf-8", newline="\n")
    adapter = GlmAdapter()

    adapter.install({}, project=project)
    adapter.uninstall(project=project)
    adapter.uninstall(project=project)

    assert provider.read_text(encoding="utf-8") == old


def test_glm_uninstall_keeps_an_edited_earlier_copy(tmp_path: Path) -> None:
    old = _glm_earlier_text()
    project = tmp_path / "project"
    project.mkdir()
    adapter = GlmAdapter()
    adapter.install({}, project=project)
    provider = _glm_provider(project)
    edited = old + 'operator_key = "kept"\n'
    provider.write_text(edited, encoding="utf-8", newline="\n")

    adapter.uninstall(project=project)

    assert provider.read_text(encoding="utf-8") == edited


# --- guard: a shipped template change records the previous digest ----------


def test_plain_file_templates_carry_no_path_token() -> None:
    # An install-specific rendering has no fixed digest, so the record cannot
    # cover it; a templated plain file needs a different mechanism first.
    for harness, entry in _plain_file_entries():
        text = install_driver.resolve_source(entry.source).read_text(encoding="utf-8")
        assert "${" not in text, f"{harness}: {entry.source} carries a path token"


def test_recorded_digests_are_not_the_current_template() -> None:
    for harness, entry in _plain_file_entries():
        assert _current_digest(entry) not in entry.earlier_digests, (
            f"{harness}: {entry.source} lists its current text as an earlier digest"
        )


def test_latest_release_template_is_current_or_recorded() -> None:
    """Fail when a template changed since the latest release without a digest."""
    entries = {
        (harness, entry.source): entry for harness, entry in _plain_file_entries()
    }
    for key, shipped in _LATEST_RELEASE_DIGESTS.items():
        assert key in entries, f"{key} is no longer a plain-file entry; update the pin"
        entry = entries[key]
        assert _current_digest(entry) == shipped or shipped in entry.earlier_digests, (
            f"{key[1]} changed since {_LATEST_RELEASE}; add {shipped} to "
            f"earlier_digests for the {key[0]} entry in propagation-manifest.yaml"
        )


def _version_key(tag: str) -> tuple[int, ...] | None:
    """Return the numeric key of a ``vMAJOR.MINOR.PATCH`` tag, else ``None``."""
    parts = tag.removeprefix("v").split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def test_latest_release_pin_is_the_newest_release_tag() -> None:
    """Fail once a release newer than the pin exists, so the pin is refreshed.

    The release-preflight CI job checks out every tag, so this runs there.
    A tag on the checked-out commit is the release being cut and is not yet
    expected in the pin.
    """
    tags = _require_release_tags()
    at_head = _git("tag", "--points-at", "HEAD")
    cut_now = set(at_head.stdout.decode("utf-8").split()) if at_head else set()
    pinned = _version_key(_LATEST_RELEASE)
    assert pinned is not None
    newer = sorted(
        tag
        for tag in tags
        if tag not in cut_now
        and (key := _version_key(tag)) is not None
        and key > pinned
    )
    assert not newer, (
        f"release tag(s) {', '.join(newer)} are newer than _LATEST_RELEASE "
        f"({_LATEST_RELEASE}); set _LATEST_RELEASE and _LATEST_RELEASE_DIGESTS "
        "to the newest release's templates"
    )


def test_latest_release_pin_matches_the_tag() -> None:
    tags = _require_release_tags()
    assert _LATEST_RELEASE in tags
    for (_, source), shipped in _LATEST_RELEASE_DIGESTS.items():
        text = _text_at_tag(_LATEST_RELEASE, source)
        assert text is not None
        assert propagation.text_digest(text) == shipped


def test_every_released_template_is_current_or_recorded() -> None:
    tags = _require_release_tags()
    for harness, entry in _plain_file_entries():
        allowed = {_current_digest(entry), *entry.earlier_digests}
        for tag in tags:
            text = _text_at_tag(tag, entry.source)
            if text is None:
                continue
            assert propagation.text_digest(text) in allowed, (
                f"{harness}: {entry.source} as {tag} shipped it is not recorded; "
                "add its SHA-256 digest to earlier_digests"
            )
