# SPDX-License-Identifier: MIT

"""Unit tests for the per-folder README file-coverage gate.

``scripts/dev/check_readme_file_coverage.py`` reports every file a folder ships
that the folder's own README never names. CI runs it with ``--strict``, so a
false positive is not merely noise — it fails the build. The exclusions are
therefore the part worth pinning: the tracked-set restriction (an earlier draft
walked the working tree and reported a gitignored build artifact), the
front-page READMEs that index nothing by design, and the fixture corpora whose
READMEs describe what the corpus proves rather than listing its files.

Every fixture tree is built under ``tmp_path``, and ``tracked_files`` is
replaced rather than exercised: the check's subject is which files it judges,
not whether ``git ls-files`` works.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DEV = _REPO_ROOT / "scripts" / "dev"
if str(_SCRIPTS_DEV) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DEV))

import check_readme_file_coverage as cov  # noqa: E402


def _tree(root: Path, files: dict[str, str]) -> None:
    """Write {relative path: text} under ``root``, creating parents."""
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _all_tracked(root: Path) -> set[Path]:
    """Every file under ``root``, as if git tracked all of them."""
    return {p.relative_to(root) for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def track_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the check treat every file on disk as git-tracked.

    The default for a test that is not about the tracked-set restriction.
    """
    monkeypatch.setattr(cov, "tracked_files", _all_tracked)


class TestNamedIn:
    """Deciding whether a README names a file.

    Presence is the whole question — a reader who cannot find a module in the
    README concludes it does not exist. Whether the row's *description* is
    accurate is deliberately out of scope.
    """

    def test_bare_filename_anywhere_counts(self) -> None:
        assert cov.named_in("The `worker.py` module drives it.", "worker.py")

    def test_prose_mention_counts_not_only_a_table_row(self) -> None:
        readme = "Configuration is read from settings.toml at startup."
        assert cov.named_in(readme, "settings.toml")

    def test_backticked_stem_counts(self) -> None:
        # A folder shipping install.sh + install.ps1 may document one `install`
        # recipe rather than one row per extension.
        assert cov.named_in("Run the `install` recipe.", "install.sh")

    def test_unmentioned_file_is_not_named(self) -> None:
        assert not cov.named_in("# Widgets\n\nSee `other.py`.", "worker.py")

    def test_bare_stem_without_backticks_does_not_count(self) -> None:
        # "install" appears as an ordinary English word constantly; matching it
        # unquoted would silently pass almost any folder.
        assert not cov.named_in("You can install this from source.", "install.sh")


class TestIsExcluded:
    """Trees the per-folder contract does not govern."""

    @pytest.mark.parametrize(
        "path",
        [
            "site/node_modules/pkg/README.md",
            "src/apothem/_vendor/jsonschema/README.md",
            "site/dist/README.md",
            ".audit/README.md",
        ],
    )
    def test_generated_and_vendored_trees_are_excluded(self, path: str) -> None:
        assert cov.is_excluded(Path(path))

    def test_conformity_fixture_corpora_are_excluded(self) -> None:
        # These READMEs state what the corpus proves; enumerating each fixture
        # would restate the corpus in prose and drift on the next fixture.
        assert cov.is_excluded(Path("tests/conformity/plain_language/pass/README.md"))
        assert cov.is_excluded(Path("tests/conformity/plain_language/fail/README.md"))

    def test_an_ordinary_source_folder_is_governed(self) -> None:
        assert not cov.is_excluded(Path("src/apothem/audit/README.md"))


class TestShippedFiles:
    """Which files a README is expected to name."""

    def test_untracked_files_are_ignored(self, tmp_path: Path) -> None:
        # The regression this pins: walking the working tree reported a
        # gitignored build artifact as an undocumented file. The tracked set is
        # the honest definition of what the repo ships.
        _tree(tmp_path, {"pkg/real.py": "", "pkg/tsconfig.tsbuildinfo": ""})
        tracked = {Path("pkg/real.py")}
        found = cov.shipped_files(tmp_path / "pkg", tmp_path, tracked)
        assert [p.name for p in found] == ["real.py"]

    def test_package_markers_and_tool_configs_are_ignored(self, tmp_path: Path) -> None:
        _tree(
            tmp_path,
            {
                "pkg/__init__.py": "",
                "pkg/py.typed": "",
                "pkg/tsconfig.json": "",
                "pkg/README.md": "",
                "pkg/.hidden": "",
                "pkg/worker.py": "",
            },
        )
        found = cov.shipped_files(tmp_path / "pkg", tmp_path, _all_tracked(tmp_path))
        assert [p.name for p in found] == ["worker.py"]


@pytest.mark.usefixtures("track_everything")
class TestMain:
    """The end-to-end walk and its exit contract."""

    def test_documented_folder_reports_ok(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _tree(
            tmp_path,
            {
                "pkg/README.md": "| `worker.py` | Does the work. |",
                "pkg/worker.py": "",
            },
        )
        assert cov.main([str(tmp_path), "--strict"]) == 0
        assert "OK" in capsys.readouterr().out

    def test_unnamed_file_is_reported(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _tree(
            tmp_path,
            {
                "pkg/README.md": "# pkg\n\nA package.\n",
                "pkg/worker.py": "",
            },
        )
        cov.main([str(tmp_path)])
        out = capsys.readouterr().out
        assert "worker.py" in out
        assert "1 unnamed file(s)" in out

    def test_advisory_by_default_and_blocking_under_strict(
        self, tmp_path: Path
    ) -> None:
        _tree(tmp_path, {"pkg/README.md": "# pkg\n", "pkg/worker.py": ""})
        assert cov.main([str(tmp_path)]) == 0
        assert cov.main([str(tmp_path), "--strict"]) == 1

    def test_front_page_readmes_are_not_held_to_the_contract(
        self, tmp_path: Path
    ) -> None:
        # The repo root introduces the project; the extension's README is its
        # marketplace listing. Neither is a file index, and demanding one would
        # make both worse for their actual readers.
        _tree(
            tmp_path,
            {
                "README.md": "# Apothem\n",
                "CITATION.cff": "",
                "noticeable.py": "",
                "vscode-extension/README.md": "# Apothem for VS Code\n",
                "vscode-extension/extension.js": "",
            },
        )
        assert cov.main([str(tmp_path), "--strict"]) == 0

    def test_a_folder_with_a_readme_but_no_shipped_files_is_not_counted(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A README over a folder of subdirectories has nothing to index; it
        # should not inflate the "folders checked" total.
        _tree(
            tmp_path,
            {
                "docs/README.md": "# docs\n",
                "docs/guide/README.md": "| `intro.md` | Start here. |",
                "docs/guide/intro.md": "",
            },
        )
        assert cov.main([str(tmp_path), "--strict"]) == 0
        assert "1 folders checked" in capsys.readouterr().out
