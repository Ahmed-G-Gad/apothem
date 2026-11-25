# SPDX-License-Identifier: MIT

"""The POSIX installers hold one lock per APOTHEM_HOME for their whole run.

install.sh, update.sh and uninstall.sh each make the folder
``<APOTHEM_HOME>.lock`` with mkdir, which fails when the folder is already
there, write their process ID into it, and remove it on every way out of the
run: success, failure, or a signal. A second run on the same APOTHEM_HOME
stops at once instead of changing it at the same time. A lock whose process
is gone (a forced kill leaves one) is reported with how to remove it, never
taken over.

The scripts run against a stand-in checkout (``APOTHEM_SOURCE``) whose engine
records the process ID in the lock while it runs and, on request, waits for
the test, fails, or sends SIGTERM to the script that started it.

The last tests cover the folder an earlier tree is set aside in
(``<APOTHEM_HOME>.before-apothem-<time>``): it is made with mkdir before the
tree moves into it, so a folder of that name that someone else made, just
before the move or between the early check and the swap, is never used.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from tests.integration.test_installer_cwd_isolation import _env, _write
from tests.integration.test_installer_release_mode import (
    STAMP,
    _release,
    _run,
    _snapshot,
    _stub_cosign,
    _stub_date,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "installer" / "install.sh"
UPDATER = REPO_ROOT / "scripts" / "installer" / "update.sh"
UNINSTALLER = REPO_ROOT / "scripts" / "installer" / "uninstall.sh"
RUN_TIMEOUT_SECONDS = 120
EXECUTABLE_MODE = 0o755

SCRIPT_ARGS = {
    "install.sh": ["sh", str(INSTALLER)],
    "update.sh": ["sh", str(UPDATER)],
    "uninstall.sh": ["sh", str(UNINSTALLER), "--yes"],
}
SCRIPTS = sorted(SCRIPT_ARGS)
# The engine command each script runs.
ENGINE_COMMAND = {
    "install.sh": "install",
    "update.sh": "update",
    "uninstall.sh": "uninstall",
}

pytestmark = pytest.mark.skipif(
    shutil.which("sh") is None
    or shutil.which("curl") is None
    or sys.platform == "win32",
    reason="exercises the POSIX installers; the ps1 twins cover Windows",
)

# The stand-in engine: records its command and the process ID the lock
# holds while it runs, then does what FAKE_ENGINE_MODE asks.
_ENGINE = """\
# SPDX-License-Identifier: MIT
import os
import signal
import sys
import time
from pathlib import Path

lock = Path(os.environ["APOTHEM_HOME"] + ".lock")
held = (lock / "pid").read_text(encoding="utf-8").strip() if lock.is_dir() else "-"
with open(os.environ["FAKE_ENGINE_RECORD"], "a", encoding="utf-8") as record:
    record.write(sys.argv[1] + " " + held + "\\n")
if os.environ.get("FAKE_ENGINE_ENV_RECORD") and (lock / "env").is_file():
    Path(os.environ["FAKE_ENGINE_ENV_RECORD"]).write_bytes((lock / "env").read_bytes())
mode = os.environ.get("FAKE_ENGINE_MODE", "")
if mode == "wait":
    Path(os.environ["FAKE_ENGINE_STARTED"]).write_text("started", encoding="utf-8")
    go = Path(os.environ["FAKE_ENGINE_GO"])
    deadline = time.monotonic() + 60
    while not go.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
elif mode == "fail":
    sys.exit(3)
elif mode == "term":
    os.kill(os.getppid(), signal.SIGTERM)
"""


@pytest.fixture(autouse=True)
def _require_click_and_rich() -> None:
    probe = subprocess.run(
        [sys.executable, "-c", "import click, rich"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        pytest.skip(f"{sys.executable} cannot import click and rich")


def _checkout(root: Path) -> Path:
    """A stand-in Apothem checkout whose engine is _ENGINE."""
    _write(root / "pyproject.toml", '[project]\nname = "lock-fixture"\n')
    _write(root / "src" / "apothem" / "__init__.py", "")
    _write(root / "src" / "apothem" / "__main__.py", _ENGINE)
    _write(root / "src" / "apothem" / "schemas" / "profile.example.yaml", "{}\n")
    return root


def _lock_env(tmp_path: Path, **extra: str) -> dict[str, str]:
    """The isolated environment of test_installer_cwd_isolation, running the
    stand-in checkout, with a profile and no post-install verify."""
    profile = tmp_path / "profile.yaml"
    profile.write_text("identity: {}\n", encoding="utf-8")
    env = _env(
        tmp_path,
        APOTHEM_SOURCE=str(_checkout(tmp_path / "checkout")),
        APOTHEM_PROFILE=str(profile),
        APOTHEM_SKIP_VERIFY="1",
        FAKE_ENGINE_RECORD=str(tmp_path / "engine-calls.txt"),
    )
    env.update(extra)
    return env


def _engine_calls(tmp_path: Path) -> list[str]:
    record = tmp_path / "engine-calls.txt"
    return record.read_text(encoding="utf-8").splitlines() if record.exists() else []


def _run_script(
    name: str, env: dict[str, str], cwd: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        SCRIPT_ARGS[name],
        cwd=str(cwd),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=RUN_TIMEOUT_SECONDS,
        check=False,
    )


def _wait_for(path: Path, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + RUN_TIMEOUT_SECONDS
    while not path.exists():
        assert process.poll() is None, process.communicate()
        assert time.monotonic() < deadline, f"{path} never appeared"
        time.sleep(0.05)


def _held_message(home: Path) -> str:
    return (
        f"Another Apothem install, update or uninstall is running on {home}. "
        f"Wait for it to finish, then re-run. If none is running, remove "
        f"{home}.lock, then re-run."
    )


@pytest.mark.parametrize("name", SCRIPTS)
def test_a_second_run_stops_while_the_first_holds_the_lock(
    tmp_path: Path, name: str
) -> None:
    """While one run is under way (its engine waits here), a second run on
    the same APOTHEM_HOME stops at once, says why, and changes nothing; the
    first run then finishes and removes the lock."""
    home = tmp_path / "apothem-home"
    lock = tmp_path / "apothem-home.lock"
    started, go = tmp_path / "started", tmp_path / "go"
    env = _lock_env(tmp_path)
    first_env = {
        **env,
        "FAKE_ENGINE_MODE": "wait",
        "FAKE_ENGINE_STARTED": str(started),
        "FAKE_ENGINE_GO": str(go),
    }
    first = subprocess.Popen(
        SCRIPT_ARGS[name],
        cwd=str(tmp_path),
        env=first_env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for(started, first)
        assert (lock / "pid").read_text(encoding="utf-8").strip() == str(first.pid)

        second = _run_script(name, env, tmp_path)

        combined = second.stdout + second.stderr
        assert second.returncode != 0, combined
        assert _held_message(home) in combined, combined
        assert (lock / "pid").read_text(encoding="utf-8").strip() == str(first.pid)
        assert _engine_calls(tmp_path) == [f"{ENGINE_COMMAND[name]} {first.pid}"]
    finally:
        go.touch()
        out, err = first.communicate(timeout=RUN_TIMEOUT_SECONDS)
    assert first.returncode == 0, out + err
    assert not lock.exists(), out + err


@pytest.mark.parametrize("name", SCRIPTS)
def test_a_lock_left_by_a_run_that_is_gone_is_reported_not_taken(
    tmp_path: Path, name: str
) -> None:
    """A lock whose process no longer runs (a forced kill leaves one) is
    reported with how to remove it; the run does not take it over and
    changes nothing."""
    gone = subprocess.Popen(["sh", "-c", "exit 0"])
    gone.wait(timeout=RUN_TIMEOUT_SECONDS)
    lock = tmp_path / "apothem-home.lock"
    lock.mkdir()
    (lock / "pid").write_text(f"{gone.pid}\n", encoding="utf-8")

    result = _run_script(name, _lock_env(tmp_path), tmp_path)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert (
        f"{lock} was left by an Apothem run that did not finish (process "
        f"{gone.pid} is no longer running). Check that no Apothem install, "
        f"update or uninstall is running, remove {lock}, then re-run."
    ) in combined, combined
    assert (lock / "pid").read_text(encoding="utf-8") == f"{gone.pid}\n"
    assert _engine_calls(tmp_path) == [], combined


@pytest.mark.parametrize("name", SCRIPTS)
def test_a_lock_that_names_no_process_is_reported(tmp_path: Path, name: str) -> None:
    """A lock folder with no process ID in it is reported, not taken."""
    lock = tmp_path / "apothem-home.lock"
    lock.mkdir()

    result = _run_script(name, _lock_env(tmp_path), tmp_path)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert (
        f"{lock} exists but names no running process; an Apothem run may have "
        "left it when it was stopped. Check that no Apothem install, update or "
        f"uninstall is running, remove {lock}, then re-run."
    ) in combined, combined
    assert lock.is_dir(), combined
    assert list(lock.iterdir()) == [], combined
    assert _engine_calls(tmp_path) == [], combined


@pytest.mark.parametrize("name", SCRIPTS)
def test_a_lock_whose_process_id_comes_a_moment_later_reads_as_held(
    tmp_path: Path, name: str
) -> None:
    """A run that has just made the lock folder writes its process ID a
    moment later. A second run that finds the folder in between looks again
    and reports the lock as held, not as one a stopped run left."""
    lock = tmp_path / "apothem-home.lock"
    lock.mkdir()
    holder = subprocess.Popen(["sleep", "60"])
    writer = threading.Timer(0.3, (lock / "pid").write_text, args=(f"{holder.pid}\n",))
    try:
        writer.start()

        result = _run_script(name, _lock_env(tmp_path), tmp_path)

    finally:
        writer.join()
        holder.kill()
        holder.wait(timeout=RUN_TIMEOUT_SECONDS)
    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert _held_message(tmp_path / "apothem-home") in combined, combined
    assert "names no running process" not in combined, combined
    assert _engine_calls(tmp_path) == [], combined


@pytest.mark.parametrize("name", SCRIPTS)
@pytest.mark.parametrize(
    ("mode", "exit_code"),
    [
        pytest.param("", 0, id="success"),
        pytest.param("fail", 3, id="failure"),
        pytest.param("term", 143, id="sigterm"),
    ],
)
def test_the_run_holds_the_lock_and_removes_it_on_every_way_out(
    tmp_path: Path, name: str, mode: str, exit_code: int
) -> None:
    """The engine runs while the script holds the lock (its process ID is in
    it), and the lock is gone once the run ends: after a success, after the
    engine fails, and after a SIGTERM that stops the script."""
    result = _run_script(name, _lock_env(tmp_path, FAKE_ENGINE_MODE=mode), tmp_path)

    combined = result.stdout + result.stderr
    assert result.returncode == exit_code, combined
    calls = _engine_calls(tmp_path)
    assert len(calls) == 1, calls
    command, held = calls[0].split(" ")
    assert command == ENGINE_COMMAND[name], calls
    assert held.isdigit(), calls
    assert not (tmp_path / "apothem-home.lock").exists(), combined


@pytest.mark.parametrize("name", SCRIPTS)
@pytest.mark.parametrize("suffix", ["/", "/."])
def test_the_lock_stays_beside_a_home_given_with_a_trailing_slash(
    tmp_path: Path, name: str, suffix: str
) -> None:
    """APOTHEM_HOME given as <home>/ (or <home>/.) still names the lock
    <home>.lock, beside it, so a run holding that lock stops this one."""
    home = tmp_path / "apothem-home"
    home.mkdir()
    lock = tmp_path / "apothem-home.lock"
    holder = subprocess.Popen(["sleep", "60"])
    try:
        lock.mkdir()
        (lock / "pid").write_text(f"{holder.pid}\n", encoding="utf-8")

        result = _run_script(
            name, _lock_env(tmp_path, APOTHEM_HOME=f"{home}{suffix}"), tmp_path
        )
    finally:
        holder.kill()
        holder.wait(timeout=RUN_TIMEOUT_SECONDS)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert _held_message(home) in combined, combined
    assert not (home / ".lock").exists(), combined
    assert _engine_calls(tmp_path) == [], combined


def test_a_dry_run_with_no_folder_for_apothem_home_creates_none(
    tmp_path: Path,
) -> None:
    """A dry run writes nothing: when the folder that would hold APOTHEM_HOME
    is not there, it runs without the lock rather than make that folder."""
    parent = tmp_path / "not-yet"
    env = _lock_env(tmp_path, APOTHEM_HOME=str(parent / "apothem-home"))

    result = subprocess.run(
        ["sh", str(INSTALLER), "--dry-run"],
        cwd=str(tmp_path),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=RUN_TIMEOUT_SECONDS,
        check=False,
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    assert not parent.exists(), combined
    assert _engine_calls(tmp_path) == ["install -"], combined


def test_a_real_install_makes_the_folder_for_the_lock(tmp_path: Path) -> None:
    """A real install into a folder that does not exist yet makes the folder
    that holds APOTHEM_HOME first and takes the lock there."""
    parent = tmp_path / "not-yet"
    env = _lock_env(tmp_path, APOTHEM_HOME=str(parent / "apothem-home"))

    result = _run_script("install.sh", env, tmp_path)

    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    calls = _engine_calls(tmp_path)
    assert len(calls) == 1, calls
    assert calls[0].split(" ")[1].isdigit(), calls
    assert parent.is_dir(), combined
    assert not (parent / "apothem-home.lock").exists(), combined


# --- the folder an earlier tree is set aside in -----------------------------


def _racing_mv(tmp_path: Path, home: Path, racer: Path) -> Path:
    """A stub mv that, right before HOME moves, makes RACER holding someone
    else's file when RACER is not there yet, as a process racing the
    installer could; return the stub's folder."""
    real = shutil.which("mv")
    assert real is not None
    stub_dir = tmp_path / "racing-mv"
    stub_dir.mkdir()
    q_home, q_racer = shlex.quote(str(home)), shlex.quote(str(racer))
    q_theirs = shlex.quote(str(racer / "theirs.txt"))
    stub = stub_dir / "mv"
    stub.write_text(
        "#!/bin/sh\n"
        f'if [ "$1" = {q_home} ] && [ ! -e {q_racer} ]; then\n'
        f"    mkdir {q_racer} && echo theirs > {q_theirs}\n"
        "fi\n"
        f'exec {shlex.quote(real)} "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    stub.chmod(EXECUTABLE_MODE)
    return stub_dir


def _racing_cosign(tmp_path: Path, racer: Path) -> Path:
    """A stub cosign that passes and makes RACER holding someone else's
    file: cosign runs after the early check of the set-aside name and before
    the swap. Return the stub's folder."""
    stub_dir = tmp_path / "racing-cosign"
    stub_dir.mkdir()
    q_racer = shlex.quote(str(racer))
    q_theirs = shlex.quote(str(racer / "theirs.txt"))
    stub = stub_dir / "cosign"
    stub.write_text(
        f"#!/bin/sh\nmkdir {q_racer} && echo theirs > {q_theirs}\nexit 0\n",
        encoding="utf-8",
        newline="\n",
    )
    stub.chmod(EXECUTABLE_MODE)
    return stub_dir


@pytest.mark.parametrize("when", ["just-before-the-move", "after-the-early-check"])
def test_an_earlier_folder_never_moves_into_a_folder_someone_else_made(
    tmp_path: Path, when: str
) -> None:
    """The set-aside folder is made with mkdir, which fails when the name is
    taken, and the earlier folder then moves inside it. A folder of the same
    name made by someone else, right before the move or after the early
    check, keeps only its own file; the earlier folder ends up, unchanged,
    in a folder this run made, and the installer names it."""
    home = tmp_path / "apothem-home"
    home.mkdir()
    (home / "keep.txt").write_text("mine\n", encoding="utf-8")
    before = _snapshot(home)
    base = _release(tmp_path)
    racer = tmp_path / f"apothem-home.before-apothem-{STAMP}"
    if when == "just-before-the-move":
        path_first = [_stub_date(tmp_path), _racing_mv(tmp_path, home, racer)]
        cosign_dir = _stub_cosign(tmp_path)
    else:
        path_first = [_stub_date(tmp_path)]
        cosign_dir = _racing_cosign(tmp_path, racer)

    result = _run(
        tmp_path, base, cosign_dir=cosign_dir, yes=True, path_first=path_first
    )

    combined = result.stdout + result.stderr
    for folder in tmp_path.glob("apothem-home.before-apothem-*"):
        if (folder / "theirs.txt").exists():
            assert [p.name for p in folder.iterdir()] == ["theirs.txt"], combined
    moved = [
        folder / "apothem-home"
        for folder in tmp_path.glob("apothem-home.before-apothem-*")
        if (folder / "apothem-home").exists()
    ]
    assert len(moved) == 1, combined
    assert _snapshot(moved[0]) == before, combined
    assert f"were moved, unchanged, to {moved[0]}\n" in combined, combined
    assert (home / "src" / "apothem" / "__init__.py").is_file(), combined


# --- what the lock message says, and which lock a run takes -----------------


def _stub_uname(tmp_path: Path, system: str, release: str) -> Path:
    """A stub uname that answers -s with SYSTEM and -r with RELEASE, and
    passes anything else to the real uname; return its folder."""
    real = shutil.which("uname")
    assert real is not None
    stub_dir = tmp_path / "stub-uname"
    stub_dir.mkdir()
    stub = stub_dir / "uname"
    stub.write_text(
        "#!/bin/sh\n"
        f'case "$1" in -s) echo {shlex.quote(system)} ;; '
        f"-r) echo {shlex.quote(release)} ;; "
        f'*) exec {shlex.quote(real)} "$@" ;; esac\n',
        encoding="utf-8",
        newline="\n",
    )
    stub.chmod(EXECUTABLE_MODE)
    return stub_dir


@pytest.mark.parametrize("name", SCRIPTS)
@pytest.mark.parametrize(
    ("system", "release", "powershell"),
    [
        pytest.param("Linux", "5.15.153.1-microsoft-standard-WSL2", True, id="wsl"),
        pytest.param("Linux", "6.8.0-45-generic", False, id="linux"),
        pytest.param("Darwin", "24.1.0", False, id="macos"),
    ],
)
def test_a_lock_file_is_reported_as_a_powershell_runs_lock(
    tmp_path: Path, name: str, system: str, release: str, powershell: bool
) -> None:
    """install.ps1, update.ps1 and uninstall.ps1 hold a file at
    <APOTHEM_HOME>.lock, which Windows removes when that run ends and will
    not let anyone remove while it runs. Where such a run can hold it (in
    WSL, a Windows run on a Windows drive) the sh scripts say so; on other
    Linux and on macOS they say only that a file is where the lock folder
    belongs. Neither calls it a lock that names no running process."""
    home = tmp_path / "apothem-home"
    lock = tmp_path / "apothem-home.lock"
    lock.write_bytes(b"")
    env = _lock_env(tmp_path)
    env["PATH"] = f"{_stub_uname(tmp_path, system, release)}{os.pathsep}{env['PATH']}"

    result = _run_script(name, env, tmp_path)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    if powershell:
        expected = (
            f"{lock} is the lock file of an Apothem PowerShell run (install.ps1, "
            f"update.ps1 or uninstall.ps1) on {home}, and Windows removes it when "
            "that run ends; while the run is active, Windows will not let anyone "
            "remove it. Wait for that run to finish, then re-run. If no Apothem "
            f"install, update or uninstall is running, remove {lock}, then re-run."
        )
    else:
        expected = (
            f"{lock} is a file where the Apothem lock folder belongs. If no "
            "Apothem install, update or uninstall is running, remove "
            f"{lock}, then re-run."
        )
    assert expected in combined, combined
    assert "names no running process" not in combined, combined
    assert powershell == ("PowerShell" in combined), combined
    assert lock.is_file(), combined
    assert _engine_calls(tmp_path) == [], combined


@pytest.mark.parametrize("name", SCRIPTS)
def test_a_lock_from_another_environment_is_not_called_gone(
    tmp_path: Path, name: str
) -> None:
    """A lock folder made by a run in another environment (WSL and Git Bash
    on one machine, another container) names a process this run cannot
    see, so kill -0 says nothing about it. The run says the process cannot
    be checked from here and to remove the lock only if no run is active
    anywhere, never that the process is gone."""
    gone = subprocess.Popen(["sh", "-c", "exit 0"])
    gone.wait(timeout=RUN_TIMEOUT_SECONDS)
    lock = tmp_path / "apothem-home.lock"
    lock.mkdir()
    (lock / "env").write_text("MINGW64_NT-10.0-26100 elsewhere \n", encoding="utf-8")
    (lock / "pid").write_text(f"{gone.pid}\n", encoding="utf-8")

    result = _run_script(name, _lock_env(tmp_path), tmp_path)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert (
        f"{lock} was made by an Apothem run in another environment (such as WSL, "
        f"Git Bash or a container), so whether its process {gone.pid} still runs "
        "cannot be checked from here. Wait for that run to finish, then re-run. "
        "If no Apothem install, update or uninstall is running anywhere, remove "
        f"{lock}, then re-run."
    ) in combined, combined
    assert "is no longer running" not in combined, combined
    assert (lock / "pid").is_file(), combined
    assert _engine_calls(tmp_path) == [], combined


@pytest.mark.parametrize("name", SCRIPTS)
def test_the_lock_records_the_environment_of_its_run(tmp_path: Path, name: str) -> None:
    """While a run holds the lock, the folder names the system and host the
    run's process ID belongs to, next to that process ID."""
    record = tmp_path / "lock-env"
    env = _lock_env(tmp_path, FAKE_ENGINE_ENV_RECORD=str(record))

    result = _run_script(name, env, tmp_path)

    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    fields = record.read_text(encoding="utf-8").split(" ")
    system = subprocess.run(
        ["uname", "-o"], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert fields[:2] == [system, os.uname().nodename], fields


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="needs a process of another user that kill -0 may not signal",
)
@pytest.mark.parametrize("name", SCRIPTS)
def test_a_lock_held_by_another_users_run_is_reported_as_running(
    tmp_path: Path, name: str
) -> None:
    """kill -0 fails for a running process of another user (a run under
    sudo) as it does for one that is gone; only the first says "not
    permitted", and then the lock's run is reported as running, not as
    gone. Process 1 belongs to root and always runs."""
    home = tmp_path / "apothem-home"
    lock = tmp_path / "apothem-home.lock"
    lock.mkdir()
    (lock / "pid").write_text("1\n", encoding="utf-8")

    result = _run_script(name, _lock_env(tmp_path), tmp_path)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert _held_message(home) in combined, combined
    assert "is no longer running" not in combined, combined


@pytest.mark.parametrize("name", SCRIPTS)
def test_a_signal_while_the_lock_is_made_leaves_no_lock_behind(
    tmp_path: Path, name: str
) -> None:
    """A TERM that arrives just after mkdir made the lock, before the run
    has recorded it as its own, would leave a lock with no process ID that
    stops every later run. The run ignores signals for that moment, so it
    goes on, and the lock is gone when it ends."""
    real = shutil.which("mkdir")
    assert real is not None
    stub_dir = tmp_path / "stub-mkdir"
    stub_dir.mkdir()
    stub = stub_dir / "mkdir"
    stub.write_text(
        "#!/bin/sh\n"
        f'{shlex.quote(real)} "$@" || exit\n'
        'case "$*" in *.lock) kill -TERM "$PPID" ;; esac\n',
        encoding="utf-8",
        newline="\n",
    )
    stub.chmod(EXECUTABLE_MODE)
    env = _lock_env(tmp_path)
    env["PATH"] = f"{stub_dir}{os.pathsep}{env['PATH']}"

    result = _run_script(name, env, tmp_path)

    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    assert not (tmp_path / "apothem-home.lock").exists(), combined
    assert len(_engine_calls(tmp_path)) == 1, combined


@pytest.mark.parametrize("name", SCRIPTS)
def test_a_run_through_a_link_takes_the_lock_of_the_folder_it_leads_to(
    tmp_path: Path, name: str
) -> None:
    """APOTHEM_HOME given as a symbolic link takes the lock beside the
    folder the link leads to, so it stops while a run through that folder's
    own path holds the lock."""
    real_home = tmp_path / "apothem-home"
    real_home.mkdir()
    link = tmp_path / "home-link"
    link.symlink_to(real_home)
    lock = tmp_path / "apothem-home.lock"
    holder = subprocess.Popen(["sleep", "60"])
    try:
        lock.mkdir()
        (lock / "pid").write_text(f"{holder.pid}\n", encoding="utf-8")

        result = _run_script(
            name, _lock_env(tmp_path, APOTHEM_HOME=str(link)), tmp_path
        )
    finally:
        holder.kill()
        holder.wait(timeout=RUN_TIMEOUT_SECONDS)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert (
        f"Another Apothem install, update or uninstall is running on {link}. "
        f"Wait for it to finish, then re-run. If none is running, remove "
        f"{lock}, then re-run."
    ) in combined, combined
    assert not (tmp_path / "home-link.lock").exists(), combined
    assert _engine_calls(tmp_path) == [], combined
