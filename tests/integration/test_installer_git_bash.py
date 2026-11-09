# SPDX-License-Identifier: MIT

"""Under Git Bash, the sh installers keep the current folder off sys.path.

The sh scripts ask the Python they run which PYTHONPATH form it reads. A
Windows Python (the usual one under Git Bash) gets Windows paths joined with
";" and only the drive and network paths of the caller's PYTHONPATH. Getting
this wrong is not harmless: Git Bash (MSYS) rewrites a ":"-joined list of
/c/... paths into ";"-joined Windows paths when it starts a Windows program,
and splits a "C:\\x" entry into "C" and "\\x" on the way. The relative "C"
then names a folder in the current folder, ahead of the standard library,
so a planted C/sitecustomize.py ran.

These tests run under Git Bash with a Windows Python, from a folder holding
planted modules: the scripts' own engine-path code for each script, and the
real install.sh, the shim it writes, update.sh and uninstall.sh end to end
against this checkout, with HOME, APOTHEM_HOME and the bin folder under the
test's temporary folder. They check that nothing in the current folder
loads and that the engine paths and the caller's full-path entries arrive
intact.
"""

from __future__ import annotations

import ast
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests._shared.python_shim import write_python_shim

REPO = Path(__file__).resolve().parents[2]
INSTALLER = REPO / "scripts" / "installer"
SH_SCRIPTS = ("install.sh", "update.sh", "uninstall.sh")
#: An install, update or uninstall run of the real engine.
END_TO_END_TIMEOUT_SECONDS = 600


def _git_bash() -> Path | None:
    """Git for Windows' bash.exe, found from git on PATH (never WSL's bash)."""
    git = shutil.which("git")
    if git is None:
        return None
    # git.exe lives in <Git>\cmd or <Git>\mingw64\bin; bash.exe in <Git>\bin.
    for root in Path(git).resolve().parents[:3]:
        bash = root / "bin" / "bash.exe"
        if bash.is_file():
            return bash
    return None


GIT_BASH = _git_bash()
pytestmark = pytest.mark.skipif(
    sys.platform != "win32" or GIT_BASH is None,
    reason="needs Git for Windows' bash.exe and a Windows Python",
)

#: Prints the first sys.path entries, without importing anything the
#: planted folder could shadow.
PROBE = "import sys; print(repr(sys.path[:8]))"


def _block(script: str, pattern: str) -> str:
    match = re.search(pattern, script, re.MULTILINE | re.DOTALL)
    assert match, f"pattern not found: {pattern}"
    return match.group(0)


def _engine_setup(script: str) -> str:
    """The script's own PYTHONPATH handling and engine-path code, in order:
    the startup block, the helpers, the form probe, then the engine paths."""
    return "\n".join(
        (
            _block(script, r"^unset APOTHEM_CALLER_PYTHONPATH\n.*?^PY_PATHSEP=\"\"$"),
            _block(script, r"^keep_full_pythonpath\(\) \{\n.*?^\}$"),
            _block(script, r"^settle_python_form\(\) \{\n.*?^\}$"),
            _block(script, r"^native_path\(\) \{\n.*?^\}$"),
            _block(script, r"^engine_pythonpath\(\) \{\n.*?^\}$"),
            "settle_python_form",
            _block(script, r'^_ep_vendor=.*?^ENGINE_PYPATH="\$\{_ep_vendor\}.*?$'),
        )
    )


def _plant(cwd: Path, marks: Path) -> None:
    """Modules in CWD (and its C subfolder) that write a marker if imported."""
    for folder in (cwd, cwd / "C"):
        folder.mkdir(parents=True, exist_ok=True)
        for name in ("sitecustomize", "usercustomize", "click"):
            mark = marks / f"{folder.name}-{name}"
            (folder / f"{name}.py").write_text(
                f"open({str(mark)!r}, 'w').write('x')\n", encoding="utf-8"
            )


def _posix(path: Path) -> str:
    """PATH as Git Bash spells it (/c/...)."""
    drive, rest = path.drive, path.as_posix()[len(path.drive) :]
    return f"/{drive[0].lower()}{rest}"


def _bash(
    program: str, cwd: Path, pythonpath: str | None, timeout: int = 60
) -> subprocess.CompletedProcess[str]:
    """Run PROGRAM under Git Bash in CWD with PYTHONPATH (None: unset)."""
    # A file, not `bash -c`: the Windows command line that carries a -c
    # argument to bash.exe would have its own quoting rules applied to the
    # backslashes in the program.
    program_file = cwd.parent / "program.sh"
    program_file.write_text(program, encoding="utf-8", newline="\n")
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("PYTHONPATH", "PYTHONSAFEPATH", "PYTHONHOME")
        and not key.startswith("APOTHEM_")
    }
    if pythonpath is not None:
        env["PYTHONPATH"] = pythonpath
    env["PY"] = _posix(Path(sys.executable))
    env["NO_COLOR"] = "1"
    assert GIT_BASH is not None
    return subprocess.run(
        [str(GIT_BASH), _posix(program_file)],
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _sys_path(program: str, cwd: Path, pythonpath: str | None) -> list[str]:
    result = _bash(program, cwd, pythonpath)
    assert result.returncode == 0, result.stderr
    return [str(entry) for entry in ast.literal_eval(result.stdout.strip())]


def _cases(userlib: Path) -> list[tuple[str | None, list[str]]]:
    """(caller PYTHONPATH, the full-path entries the engine must get)."""
    lib = str(userlib)
    return [
        (None, []),
        (lib, [lib]),
        # Python spells a "C:/x" entry "C:\x" on sys.path.
        (lib.replace("\\", "/"), [lib]),
        (f"{lib};", [lib]),
        (f";C:rel;{lib}", [lib]),
        ("/c/nonexistent", []),
        ("/c/nonexistent;", []),
        (".", []),
        ("\\rooted", []),
    ]


@pytest.mark.parametrize("script_name", SH_SCRIPTS)
def test_engine_runs_keep_the_current_folder_off_sys_path(
    tmp_path: Path, script_name: str
) -> None:
    """An engine run built from the script's own code loads nothing from the
    current folder, and gets the engine paths then the caller's full-path
    entries, in Windows form."""
    script = (INSTALLER / script_name).read_text(encoding="utf-8")
    src = tmp_path / "home" / "src"
    (src / "apothem" / "_vendor").mkdir(parents=True)
    userlib = tmp_path / "userlib"
    userlib.mkdir()
    cwd, marks = tmp_path / "work", tmp_path / "marks"
    marks.mkdir()
    _plant(cwd, marks)
    # The probe starts with the script's own DROP_CWD_FROM_PATH, as the
    # engine program does: on Python 3.10, which has no PYTHONSAFEPATH, `-c`
    # puts '' first on sys.path and only that statement removes it.
    program = (
        'die() { printf "%s\\n" "$*" >&2; exit 1; }\n'
        f"SRC_PATH='{_posix(src)}'\n"
        + _engine_setup(script)
        + "\n"
        + _block(script, r"^DROP_CWD_FROM_PATH=[^\n]*$")
        + '\nPYTHONSAFEPATH=1 PYTHONPATH="$(engine_pythonpath)" '
        + f'"$PY" -c "$DROP_CWD_FROM_PATH; {PROBE}"\n'
    )
    engine = [str(src / "apothem" / "_vendor"), str(src)]

    for pythonpath, wanted in _cases(userlib):
        path = _sys_path(program, cwd, pythonpath)

        assert sorted(p.name for p in marks.iterdir()) == [], (pythonpath, path)
        assert path[:2] == engine, (pythonpath, path)
        assert path[2 : 2 + len(wanted)] == wanted, (pythonpath, path)
        assert not {str(cwd), str(cwd / "C"), ""} & set(path), (pythonpath, path)


# --- the real scripts, end to end ------------------------------------------


@dataclass(frozen=True)
class Installed:
    """An install.sh run of this checkout, with its folders."""

    root: Path
    cwd: Path
    marks: Path
    userlib: Path
    shim: Path
    install: subprocess.CompletedProcess[str]


def _sq(text: str) -> str:
    return shlex.quote(text)


def _driver(root: Path, command: str) -> str:
    """A Git Bash program that isolates HOME, APOTHEM_HOME, the bin folder
    and the profile under ROOT, puts the test's Python first on PATH, and
    runs COMMAND."""
    home = root / "home"
    (home / ".config" / "apothem").mkdir(parents=True, exist_ok=True)
    python_dir = root / "python-shim"
    python_dir.mkdir(exist_ok=True)
    write_python_shim(python_dir / "python3")
    exports = {
        "HOME": _posix(home),
        "USERPROFILE": str(home),
        "APOTHEM_HOME": _posix(home / ".apothem"),
        "APOTHEM_BIN_DIR": _posix(root / "bin"),
        "APOTHEM_SOURCE": _posix(REPO),
        "APOTHEM_PROFILE": _posix(home / ".config" / "apothem" / "profile.yaml"),
    }
    lines = [f"export {name}={_sq(value)}" for name, value in exports.items()]
    lines.append(f'export PATH={_sq(_posix(python_dir))}:"$PATH"')
    lines.append(command)
    return "\n".join(lines) + "\n"


def _plant_userlib(userlib: Path, marks: Path) -> None:
    """A user library whose sitecustomize proves it reached sys.path."""
    userlib.mkdir(parents=True, exist_ok=True)
    (userlib / "sitecustomize.py").write_text(
        f"open({str(marks / 'userlib-sitecustomize')!r}, 'w').write('x')\n",
        encoding="utf-8",
    )


def _install(root: Path) -> Installed:
    cwd, marks, userlib = root / "work", root / "marks", root / "userlib"
    marks.mkdir(parents=True)
    _plant(cwd, marks)
    _plant_userlib(userlib, marks)
    script = _posix(INSTALLER / "install.sh")
    install = _bash(
        _driver(root, f"sh {_sq(script)} --yes"),
        cwd,
        f"{userlib};/c/nonexistent;C:rel;.",
        END_TO_END_TIMEOUT_SECONDS,
    )
    return Installed(root, cwd, marks, userlib, root / "bin" / "apothem", install)


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory) -> Installed:
    return _install(tmp_path_factory.mktemp("git-bash-install"))


def _marks(installed: Installed) -> list[str]:
    """The markers written so far, then clear them."""
    names = sorted(p.name for p in installed.marks.iterdir())
    for mark in installed.marks.iterdir():
        mark.unlink()
    return names


def test_install_runs_the_engine_with_windows_paths(installed: Installed) -> None:
    """install.sh, run from the planted folder, installs from this checkout:
    nothing there loads, the caller's drive-path entry reaches the engine's
    Python, and the shim bakes the ";" a Windows Python reads."""
    result = installed.install

    assert result.returncode == 0, result.stdout + result.stderr
    assert _marks(installed) == ["userlib-sitecustomize"], result.stdout
    shim = installed.shim.read_text(encoding="utf-8")
    assert "\napothem_sep=';'\n" in shim, shim


def test_the_shim_runs_the_engine_from_the_planted_folder(
    installed: Installed,
) -> None:
    """The shim install.sh wrote runs the engine from the planted folder,
    whatever the caller's PYTHONPATH, and loads nothing from there."""
    assert installed.install.returncode == 0, installed.install.stderr
    shim = _posix(installed.shim)

    for pythonpath, _wanted in _cases(installed.userlib):
        _marks(installed)

        result = _bash(f"{_sq(shim)} --version\n", installed.cwd, pythonpath)

        assert result.returncode == 0, (pythonpath, result.stderr)
        assert "version" in result.stdout.lower(), (pythonpath, result.stdout)
        planted = [m for m in _marks(installed) if not m.startswith("userlib")]
        assert planted == [], (pythonpath, planted)


def test_the_shim_hands_the_engine_its_paths_then_the_callers(
    installed: Installed,
) -> None:
    """The shim's own PYTHONPATH handling, run up to the engine start, gives
    Python the engine paths then only the caller's drive and network paths."""
    assert installed.install.returncode == 0, installed.install.stderr
    probe = installed.root / "probe-shim"
    probe.write_text(
        installed.shim.read_text(encoding="utf-8").replace(
            "import runpy;", "print(repr(sys.path[:8])); raise SystemExit(0);"
        ),
        encoding="utf-8",
        newline="\n",
    )
    engine = [str(REPO / "src" / "apothem" / "_vendor"), str(REPO / "src")]

    for pythonpath, wanted in _cases(installed.userlib):
        _marks(installed)

        path = _sys_path(f"sh {_sq(_posix(probe))}\n", installed.cwd, pythonpath)

        planted = [m for m in _marks(installed) if not m.startswith("userlib")]
        assert planted == [], (pythonpath, planted)
        assert path[:2] == engine, (pythonpath, path)
        assert path[2 : 2 + len(wanted)] == wanted, (pythonpath, path)
        assert not {str(installed.cwd), str(installed.cwd / "C"), ""} & set(path)


def test_update_runs_the_engine_from_the_planted_folder(
    installed: Installed,
) -> None:
    """update.sh re-materializes from this checkout with nothing from the
    planted folder loading, and the caller's drive path reaching Python."""
    assert installed.install.returncode == 0, installed.install.stderr
    _marks(installed)
    script = _posix(INSTALLER / "update.sh")

    result = _bash(
        _driver(installed.root, f"sh {_sq(script)} --yes"),
        installed.cwd,
        f"{installed.userlib};/c/nonexistent;C:rel;.",
        END_TO_END_TIMEOUT_SECONDS,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert _marks(installed) == ["userlib-sitecustomize"], result.stdout


def test_uninstall_runs_the_engine_from_the_planted_folder(tmp_path: Path) -> None:
    """uninstall.sh, after its own install, removes the harness and the
    shim with nothing from the planted folder loading."""
    installed = _install(tmp_path)
    assert installed.install.returncode == 0, installed.install.stderr
    _marks(installed)
    script = _posix(INSTALLER / "uninstall.sh")

    result = _bash(
        _driver(installed.root, f"sh {_sq(script)} --yes"),
        installed.cwd,
        f"{installed.userlib};/c/nonexistent;C:rel;.",
        END_TO_END_TIMEOUT_SECONDS,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert _marks(installed) == ["userlib-sitecustomize"], result.stdout
    assert not installed.shim.exists()


# --- the in-place clone's work-tree check ----------------------------------

#: Stubs for the checks check_clone_setup runs before and after its own
#: work-tree check, which the tests below exercise alone.
_CLONE_CHECK_STUBS = """\
clone_git_ok() { :; }
check_clone_config() { :; }
check_clone_modules() { :; }
check_clone_gitlinks() { :; }
die() { printf 'DIE %s\\n' "$*"; exit 1; }
HOOKS_OFF=
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
"""


def _make_clone(root: Path) -> Path:
    """A git clone with one commit, at ROOT/Clone (capitals on disk)."""
    clone = root / "Clone"
    clone.mkdir(parents=True)
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    for args in (
        ["init", "--quiet"],
        [
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.invalid",
            "commit",
            "--quiet",
            "--allow-empty",
            "-m",
            "one",
        ],
    ):
        subprocess.run(["git", *args], cwd=clone, env=env, check=True)
    return clone


def _check_clone_setup(script_name: str, spelling: str, cwd: Path) -> str:
    """Run SCRIPT_NAME's check_clone_setup on the clone spelled SPELLING."""
    script = (INSTALLER / script_name).read_text(encoding="utf-8")
    program = "\n".join(
        (
            _CLONE_CHECK_STUBS,
            _block(script, r"^cgit\(\) \{\n.*?^\}$"),
            _block(script, r"^check_clone_setup\(\) \{\n.*?^\}$"),
            f"check_clone_setup {_sq(spelling)}",
            "echo PASSED",
        )
    )
    result = _bash(program, cwd, None)
    return result.stdout + result.stderr


def _other_capitals(path: Path) -> str:
    """PATH as Git Bash spells it, every letter after the drive in the
    other case (NTFS folders match either way)."""
    posix = _posix(path)
    return posix[:2] + posix[2:].swapcase()


@pytest.mark.parametrize("script_name", ["install.sh", "update.sh"])
@pytest.mark.parametrize("spelling", ["as on disk", "other capitals"])
def test_an_in_place_clone_is_accepted_however_its_path_is_spelled(
    tmp_path: Path, script_name: str, spelling: str
) -> None:
    """git spells the clone's top folder C:/... with its on-disk capitals,
    and maps the Windows temp folder onto /tmp, while pwd -P keeps the
    spelling a folder was reached by. The check asks git whether the folder
    is the top of the work tree, so a clone reached by /c/... (under the
    temp folder) or with other capitals passes."""
    clone = _make_clone(tmp_path)
    path = _posix(clone) if spelling == "as on disk" else _other_capitals(clone)

    output = _check_clone_setup(script_name, path, tmp_path)

    assert output.strip().endswith("PASSED"), output


@pytest.mark.parametrize("script_name", ["install.sh", "update.sh"])
@pytest.mark.parametrize("setup", ["core.bare", "subfolder"])
def test_an_in_place_clone_without_its_work_tree_at_the_top_is_refused(
    tmp_path: Path, script_name: str, setup: str
) -> None:
    """A clone git finds no work tree in (core.bare=true), and a folder
    inside a clone rather than at its top, are still refused."""
    clone = _make_clone(tmp_path)
    target = clone
    if setup == "core.bare":
        subprocess.run(["git", "config", "core.bare", "true"], cwd=clone, check=True)
    else:
        target = clone / "inner"
        target.mkdir()

    output = _check_clone_setup(script_name, _posix(target), tmp_path)

    assert "PASSED" not in output, output
    assert "is not the work tree of its git clone" in output, output
