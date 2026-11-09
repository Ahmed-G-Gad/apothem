# SPDX-License-Identifier: MIT

"""Under Git Bash, the sh installers keep the current folder off sys.path.

Git Bash (MSYS) rewrites a ":"-joined list of /c/... paths into ";"-joined
Windows paths when it starts a Windows program, and splits a "C:\\x" entry
into "C" and "\\x" on the way. The relative "C" then names a folder in the
current folder, ahead of the standard library, so a planted
C/sitecustomize.py ran. These tests run the scripts' own helper code (the
PYTHONPATH filter, the engine-path builder and the POSIX shim body) under
Git Bash with a Windows Python, from a folder holding planted modules, and
check that nothing there loads and that the engine paths and the caller's
full-path entries arrive intact.
"""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
INSTALLER = REPO / "scripts" / "installer"
SH_SCRIPTS = ("install.sh", "update.sh", "uninstall.sh")


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
    """The script's own PYTHONPATH filter and engine-path code, in order."""
    return "\n".join(
        (
            _block(script, r"^keep_full_pythonpath\(\) \{\n.*?^\}$"),
            _block(
                script,
                r'^case "\$\(uname -s 2>/dev/null \|\| true\)" in\n'
                r"    MINGW\* \| MSYS\* \| CYGWIN\*\) PY_PATHSEP.*?^esac$",
            ),
            _block(script, r"^native_path\(\) \{\n.*?^\}$"),
            _block(script, r"^engine_pythonpath\(\) \{\n.*?^\}$"),
            _block(script, r'^_pp_keep="\$\(keep_full_pythonpath.*?^fi$'),
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


def _run(program: str, cwd: Path, pythonpath: str | None) -> list[str]:
    # A file, not `bash -c`: the Windows command line that carries a -c
    # argument to bash.exe would have its own quoting rules applied to the
    # backslashes in the program.
    program_file = cwd.parent / "program.sh"
    program_file.write_text(program, encoding="utf-8", newline="\n")
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("PYTHONPATH", "PYTHONSAFEPATH", "PYTHONHOME")
    }
    if pythonpath is not None:
        env["PYTHONPATH"] = pythonpath
    env["PY"] = _posix(Path(sys.executable))
    assert GIT_BASH is not None
    result = subprocess.run(
        [str(GIT_BASH), _posix(program_file)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return [str(entry) for entry in ast.literal_eval(result.stdout.strip())]


def _cases(userlib: Path) -> list[tuple[str | None, list[str]]]:
    """(caller PYTHONPATH, the full-path entries the engine must get)."""
    lib = str(userlib)
    return [
        (None, []),
        (lib, [lib]),
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
    program = (
        'die() { printf "%s\\n" "$*" >&2; exit 1; }\n'
        f"SRC_PATH='{_posix(src)}'\n"
        + _engine_setup(script)
        + f'\nPYTHONSAFEPATH=1 PYTHONPATH="$(engine_pythonpath)" "$PY" -c "{PROBE}"\n'
    )
    engine = [str(src / "apothem" / "_vendor"), str(src)]

    for pythonpath, wanted in _cases(userlib):
        path = _run(program, cwd, pythonpath)

        assert sorted(p.name for p in marks.iterdir()) == [], (pythonpath, path)
        assert path[:2] == engine, (pythonpath, path)
        assert path[2 : 2 + len(wanted)] == wanted, (pythonpath, path)
        assert not {str(cwd), str(cwd / "C"), ""} & set(path), (pythonpath, path)


def test_the_shim_keeps_the_current_folder_off_sys_path(tmp_path: Path) -> None:
    """The POSIX shim body install.sh writes, run with the separator it bakes
    in under Git Bash, keeps only drive and network paths of PYTHONPATH and
    loads nothing from the current folder."""
    script = (INSTALLER / "install.sh").read_text(encoding="utf-8")
    body = _block(script, r"(?<=cat <<'SHIM_BODY'\n).*?(?=^SHIM_BODY$)")
    engine = tmp_path / "engine"
    engine.mkdir()
    userlib = tmp_path / "userlib"
    userlib.mkdir()
    cwd, marks = tmp_path / "work", tmp_path / "marks"
    marks.mkdir()
    _plant(cwd, marks)
    program = (
        f"apothem_pp='{engine}'\napothem_sep=';'\n"
        + body
        + f'PYTHONSAFEPATH=1 PYTHONPATH="$apothem_pp" "$PY" -c "{PROBE}"\n'
    )

    for pythonpath, wanted in _cases(userlib):
        path = _run(program, cwd, pythonpath)

        assert sorted(p.name for p in marks.iterdir()) == [], (pythonpath, path)
        assert path[: 1 + len(wanted)] == [str(engine), *wanted], (pythonpath, path)
        assert not {str(cwd), str(cwd / "C"), ""} & set(path), (pythonpath, path)
