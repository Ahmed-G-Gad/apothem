# SPDX-License-Identifier: MIT

"""Hook interpreter starts load nothing from the opened folder or the environment.

A hook runs in whatever folder the harness opened, on every tool call. An empty
``PYTHONPATH`` entry (``":/x"`` or ``"/x:"``; ``";C:\\x"`` or ``"C:\\x;"`` on
Windows) stands for that folder and sits ahead of the standard library, and a
script start keeps only ``sys.path[0]`` pointed at its own folder. Every hook
command therefore starts Python with ``-E`` (read no ``PYTHON*`` variable) and
``-s`` (leave out the user's site-packages; ``site`` reads ``PYTHONUSERBASE``
even under ``-E``).

Each test runs a hook the way the harness runs it, from a folder holding a
``sitecustomize.py``, a ``usercustomize.py`` and a ``json.py`` that each write a
marker file when imported, with ``PYTHONPATH`` unset, then holding an empty entry
first, then an empty entry last. The hook must answer as usual every time and
no marker may appear. Covered: ``bootstrap.sh`` (the plugin's command), each
time with a cold interpreter cache so the locator's version probe runs from the
opened folder too, then a warm one; ``bootstrap.ps1`` on Windows under
PowerShell 7 and Windows PowerShell, the same way; and the commands the Claude
Code install writes into ``settings.json`` (the dispatcher and the conformity
gate). The unset run is the control: it shows the hook works when nothing is
planted in reach. A user site-packages folder inside the opened folder is
kept out of the Claude Code commands, ``bootstrap.sh`` and ``bootstrap.ps1``
alike, each stub with a cold cache.

``-E`` also turns off ``PYTHONUTF8`` and ``PYTHONIOENCODING``, so the dispatcher
and the gate set their streams to UTF-8 themselves. The non-ASCII tests hold
them to that where the locale's encoding is a legacy code page (Windows); on
Linux and macOS the locale is UTF-8 already. The byte-order-mark tests hold the
same stream setup on every platform.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from apothem.harnesses.claude_code import ClaudeCodeAdapter
from tests._shared.bash_resolver import SKIP_REASON, find_test_bash

_SRC = Path(__file__).resolve().parents[2] / "src" / "apothem"
_PLANTED = ("sitecustomize", "usercustomize", "json")
_ELSEWHERE = r"C:\nonexistent" if sys.platform == "win32" else "/nonexistent"
#: ``PYTHONPATH`` unset (the control), then an empty entry first, then last.
_PYTHONPATHS: tuple[str | None, ...] = (
    None,
    os.pathsep + _ELSEWHERE,
    _ELSEWHERE + os.pathsep,
)
_BASH = find_test_bash()
_POWERSHELLS = [
    shell
    for shell in (shutil.which("pwsh"), shutil.which("powershell"))
    if shell is not None and sys.platform == "win32"
]
#: A file name whose UTF-8 bytes no single-byte code page reads back as itself.
_NON_ASCII_NAME = "caf\u00e9-\u6f22\u5b57.py"
#: Inert payload text that the dynamic-eval guard reports; the report names the
#: target path. Nothing here deserializes anything.
_EVAL_CONTENT = "import pickle\nobj = pickle.loads(reply)\n"
_BOM = b"\xef\xbb\xbf"
#: Seconds one hook start may take on a loaded runner, and one interpreter probe.
_HOOK_TIMEOUT_SECONDS = 120
_PROBE_TIMEOUT_SECONDS = 60
#: Characters of a failing hook's stderr shown in an assertion message.
_STDERR_TAIL = 600


# --- helpers ----------------------------------------------------------------------


def _marker_module(marker: Path) -> str:
    """Return a module body that writes *marker* when it is imported."""
    return f"with open({str(marker)!r}, 'w') as _f:\n    _f.write('loaded')\n"


def _plant(tmp_path: Path) -> tuple[Path, Path]:
    """Return a project folder holding the three marker modules, and the marker folder."""
    project = tmp_path / "project"
    (project / ".git").mkdir(parents=True)
    markers = tmp_path / "markers"
    markers.mkdir()
    for name in _PLANTED:
        (project / f"{name}.py").write_text(
            _marker_module(markers / name), encoding="utf-8"
        )
    return project, markers


def _env(
    tmp_path: Path, pythonpath: str | None = None, *, state: str = "state", **extra: str
) -> dict[str, str]:
    """Return a hook environment: the host's, less what Apothem or Python reads."""
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("APOTHEM_", "CLAUDE_", "PYTHON"))
    }
    # The test's interpreter comes first, so the locators find a real one.
    env["PATH"] = os.pathsep.join(
        [str(Path(sys.executable).parent), env.get("PATH", os.defpath)]
    )
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    env["APOTHEM_HOOK_STATE_DIR"] = str(tmp_path / state)
    if pythonpath is not None:
        env["PYTHONPATH"] = pythonpath
    env.update(extra)
    return env


def _payload(project: Path, event: str, **fields: object) -> bytes:
    """Return a hook payload as the harness writes it: UTF-8 JSON, not escaped."""
    base: dict[str, object] = {
        "session_id": "isolation",
        "hook_event_name": event,
        "cwd": str(project),
        "transcript_path": str(project / "transcript.jsonl"),
    }
    if event == "SessionStart":
        base["source"] = "startup"
    base.update(fields)
    return json.dumps(base, ensure_ascii=False).encode("utf-8")


def _write_payload(project: Path, name: str = "app.py") -> bytes:
    return _payload(
        project,
        "PreToolUse",
        tool_name="Write",
        tool_input={"file_path": str(project / name), "content": _EVAL_CONTENT},
    )


def _run(
    argv: list[str], payload: bytes, env: dict[str, str], cwd: Path
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        argv,
        input=payload,
        capture_output=True,
        env=env,
        cwd=str(cwd),
        timeout=_HOOK_TIMEOUT_SECONDS,
        check=False,
    )


def _answer(
    done: subprocess.CompletedProcess[bytes], markers: Path, label: str = ""
) -> dict[str, object]:
    """Assert the hook ran clean and loaded no planted module; return its answer."""
    loaded = sorted(path.name for path in markers.iterdir())
    stderr = done.stderr.decode("utf-8", "replace")[-_STDERR_TAIL:]
    assert loaded == [], f"{label}: planted modules loaded: {loaded}; stderr: {stderr}"
    assert done.returncode == 0, f"{label}: {stderr}"
    text = done.stdout.decode("utf-8").strip()
    answer = json.loads(text) if text else {}
    assert isinstance(answer, dict), text
    return answer


def _context(answer: dict[str, object]) -> str:
    specific = answer.get("hookSpecificOutput")
    assert isinstance(specific, dict), answer
    return str(specific.get("additionalContext", ""))


def _event(answer: dict[str, object]) -> str:
    specific = answer.get("hookSpecificOutput")
    assert isinstance(specific, dict), answer
    return str(specific.get("hookEventName", ""))


def _install_claude_code() -> dict[str, object]:
    """Install Claude Code into the test's own home; return its settings."""
    adapter = ClaudeCodeAdapter()
    adapter.install({})
    settings = json.loads(adapter.output_path.read_text(encoding="utf-8"))
    assert isinstance(settings, dict)
    return settings


def _handler_argv(
    settings: dict[str, object], event: str, matcher: str, script: str
) -> list[str]:
    """Return the argv of the *script* handler registered for *event* and *matcher*."""
    hooks = settings["hooks"]
    assert isinstance(hooks, dict)
    for group in hooks[event]:
        if group.get("matcher") != matcher:
            continue
        for handler in group["hooks"]:
            args = [str(arg) for arg in handler.get("args", [])]
            if any(arg.endswith(script) for arg in args):
                return [str(handler["command"]), *args]
    raise AssertionError(f"no {script} handler for {event} {matcher}")


def _hook_tree(tmp_path: Path) -> Path:
    """Copy the hook tree to a scratch root, laid out as an install lays it out.

    The stubs find their dispatcher two levels above themselves, so the copy
    keeps the source checkout free of the bytecode the hooks write.
    """
    root = tmp_path / "tree"
    shutil.copytree(
        _SRC / "hooks", root / "hooks", ignore=shutil.ignore_patterns("__pycache__")
    )
    return root


def _run_stub(argv: list[str], tmp_path: Path, cache_name: str) -> None:
    """Run a bootstrap stub with each ``PYTHONPATH`` value, a cold cache each time.

    The first call of each round locates the interpreter from the opened folder
    (the locator's version probe runs there) and caches it; the second starts
    the dispatcher from the cache.
    """
    stub = Path(argv[-1])
    message = str(stub.parents[1] / "messages" / "pretooluse-eval-guard.md")
    for index, pythonpath in enumerate(_PYTHONPATHS):
        project, markers = _plant(tmp_path / f"round-{index}")
        env = _env(tmp_path, pythonpath, state=f"state-{index}")
        label = f"PYTHONPATH={pythonpath!r}"
        cold = _run(
            [*argv, "SessionStart"], _payload(project, "SessionStart"), env, project
        )
        assert _event(_answer(cold, markers, f"{label}, cold")) == "SessionStart"
        cache = tmp_path / f"state-{index}" / cache_name
        assert cache.is_file(), f"{label}: the cold run cached the interpreter it found"
        warm = _run(
            [*argv, "PreToolUse", message], _write_payload(project), env, project
        )
        assert "pickle.loads" in _context(_answer(warm, markers, f"{label}, warm"))


# --- the commands the Claude Code install writes --------------------------------------


def test_every_claude_code_hook_handler_starts_python_with_e_and_s() -> None:
    settings = _install_claude_code()
    hooks = settings["hooks"]
    assert isinstance(hooks, dict)
    handlers = [
        handler
        for groups in hooks.values()
        for group in groups
        for handler in group["hooks"]
    ]
    assert handlers
    for handler in handlers:
        assert handler["args"][:2] == ["-E", "-s"], handler


def test_the_claude_code_hook_commands_load_nothing_from_the_opened_folder(
    tmp_path: Path,
) -> None:
    settings = _install_claude_code()
    session = _handler_argv(settings, "SessionStart", "*", "dispatch.py")
    write = _handler_argv(settings, "PreToolUse", "Write", "dispatch.py")
    gate = _handler_argv(settings, "PreToolUse", "Write", "gate.py")

    for index, pythonpath in enumerate(_PYTHONPATHS):
        project, markers = _plant(tmp_path / f"round-{index}")
        env = _env(tmp_path, pythonpath)
        label = f"PYTHONPATH={pythonpath!r}"

        answer = _answer(
            _run(session, _payload(project, "SessionStart"), env, project),
            markers,
            f"{label}, SessionStart",
        )
        assert _event(answer) == "SessionStart"
        answer = _answer(
            _run(write, _write_payload(project), env, project),
            markers,
            f"{label}, Write",
        )
        assert "pickle.loads" in _context(answer)
        report = _answer(
            _run(gate, _write_payload(project), env, project), markers, f"{label}, gate"
        )
        assert report["orchestrator"] == "conformity-gate"
        assert report["path"] == str(project / "app.py")


# --- the bootstrap stubs ----------------------------------------------------------------


@pytest.mark.skipif(_BASH is None, reason=SKIP_REASON)
def test_bootstrap_sh_loads_nothing_from_the_opened_folder(tmp_path: Path) -> None:
    assert _BASH is not None
    stub = _hook_tree(tmp_path) / "hooks" / "lib" / "bootstrap.sh"
    _run_stub([_BASH, str(stub)], tmp_path, "interpreter-path")


@pytest.mark.skipif(not _POWERSHELLS, reason="bootstrap.ps1 is the Windows stub")
@pytest.mark.parametrize("shell", _POWERSHELLS or [""], ids=lambda s: Path(s).stem)
def test_bootstrap_ps1_loads_nothing_from_the_opened_folder(
    tmp_path: Path, shell: str
) -> None:
    stub = _hook_tree(tmp_path) / "hooks" / "lib" / "bootstrap.ps1"
    argv = [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(stub)]
    _run_stub(argv, tmp_path, "interpreter-path-ps1")


# --- the user's site-packages -------------------------------------------------------------


def _plant_user_site(project: Path, env: dict[str, str], markers: Path) -> None:
    """Plant a ``usercustomize.py`` and a ``.pth`` file in the user site *env* names.

    ``PYTHONUSERBASE=.`` puts the user site-packages inside the opened folder,
    and ``site`` reads that variable even when ``-E`` is given. Skips the test
    when this interpreter adds no user site at all (a virtual environment),
    because then there is nothing for ``-s`` to leave out.
    """
    probe = subprocess.run(
        [sys.executable, "-E", "-c", "import site; print(site.getusersitepackages())"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(project),
        timeout=_PROBE_TIMEOUT_SECONDS,
        check=True,
    )
    site_dir = project / probe.stdout.strip()
    site_dir.mkdir(parents=True)
    (site_dir / "usercustomize.py").write_text(
        _marker_module(markers / "user-site-usercustomize"), encoding="utf-8"
    )
    marker = str(markers / "user-site-pth")
    (site_dir / "apothem-isolation-probe.pth").write_text(
        f"import os; open({marker!r}, 'w').close()\n", encoding="utf-8"
    )
    # The control: a start without -s reads that site.
    subprocess.run(
        [sys.executable, "-E", "-c", "pass"],
        env=env,
        cwd=str(project),
        timeout=_PROBE_TIMEOUT_SECONDS,
        check=True,
    )
    if not any(markers.iterdir()):
        pytest.skip(
            "this interpreter adds no user site-packages (a virtual environment)"
        )
    for leftover in markers.iterdir():
        leftover.unlink()


def test_a_user_site_inside_the_opened_folder_stays_out_of_the_hooks(
    tmp_path: Path,
) -> None:
    settings = _install_claude_code()
    project = tmp_path / "project"
    (project / ".git").mkdir(parents=True)
    markers = tmp_path / "markers"
    markers.mkdir()
    env = _env(tmp_path, PYTHONUSERBASE=".")
    _plant_user_site(project, env, markers)

    session = _handler_argv(settings, "SessionStart", "*", "dispatch.py")
    answer = _answer(
        _run(session, _payload(project, "SessionStart"), env, project), markers
    )
    assert _event(answer) == "SessionStart"
    gate = _handler_argv(settings, "PreToolUse", "Write", "gate.py")
    _answer(_run(gate, _write_payload(project), env, project), markers)

    if _BASH is not None:
        stub = str(_hook_tree(tmp_path) / "hooks" / "lib" / "bootstrap.sh")
        # A cold cache, so the locator's version probe runs from the folder too.
        done = _run(
            [_BASH, stub, "SessionStart"],
            _payload(project, "SessionStart"),
            env,
            project,
        )
        assert _event(_answer(done, markers)) == "SessionStart"

    for index, shell in enumerate(_POWERSHELLS):
        tree = _hook_tree(tmp_path / f"ps-{index}")
        stub = str(tree / "hooks" / "lib" / "bootstrap.ps1")
        # A state folder of its own: a cold cache, so the locator runs here too.
        shell_env = _env(tmp_path, state=f"state-ps-{index}", PYTHONUSERBASE=".")
        argv = [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", stub]
        done = _run(
            [*argv, "SessionStart"],
            _payload(project, "SessionStart"),
            shell_env,
            project,
        )
        assert _event(_answer(done, markers, Path(shell).stem)) == "SessionStart"
        assert (tmp_path / f"state-ps-{index}" / "interpreter-path-ps1").is_file()


# --- a payload that is not ASCII --------------------------------------------------------

#: The environment a caller may run the hook in: clean, or one asking Python for
#: another stream encoding. Python reads neither variable under -E, so the hook
#: reads its payload as UTF-8 itself either way.
_ENCODING_ENVS = pytest.mark.parametrize(
    "encoding_env",
    [{}, {"PYTHONIOENCODING": "latin-1", "PYTHONUTF8": "0"}],
    ids=["clean-environment", "another-encoding-requested"],
)


@_ENCODING_ENVS
def test_the_dispatcher_reads_a_non_ascii_payload_as_utf8(
    tmp_path: Path, encoding_env: dict[str, str]
) -> None:
    settings = _install_claude_code()
    project, markers = _plant(tmp_path)
    write = _handler_argv(settings, "PreToolUse", "Write", "dispatch.py")
    env = _env(tmp_path, **encoding_env)

    done = _run(write, _write_payload(project, _NON_ASCII_NAME), env, project)

    assert str(project / _NON_ASCII_NAME) in _context(_answer(done, markers))


@_ENCODING_ENVS
def test_the_gate_reads_a_non_ascii_payload_as_utf8(
    tmp_path: Path, encoding_env: dict[str, str]
) -> None:
    settings = _install_claude_code()
    project, markers = _plant(tmp_path)
    gate = _handler_argv(settings, "PreToolUse", "Write", "gate.py")
    env = _env(tmp_path, **encoding_env)

    done = _run(gate, _write_payload(project, _NON_ASCII_NAME), env, project)

    # The write is outside the gate's scope, so the report names the path only.
    assert _answer(done, markers)["path"] == str(project / _NON_ASCII_NAME)


def test_the_dispatcher_drops_a_byte_order_mark_before_the_payload(
    tmp_path: Path,
) -> None:
    settings = _install_claude_code()
    project, markers = _plant(tmp_path)
    write = _handler_argv(settings, "PreToolUse", "Write", "dispatch.py")

    done = _run(write, _BOM + _write_payload(project), _env(tmp_path), project)

    assert "pickle.loads" in _context(_answer(done, markers))


def test_the_gate_drops_a_byte_order_mark_before_the_payload(tmp_path: Path) -> None:
    settings = _install_claude_code()
    project, markers = _plant(tmp_path)
    gate = _handler_argv(settings, "PreToolUse", "Write", "gate.py")

    done = _run(gate, _BOM + _write_payload(project), _env(tmp_path), project)

    assert _answer(done, markers)["path"] == str(project / "app.py")
