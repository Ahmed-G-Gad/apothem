# SPDX-License-Identifier: MIT

"""The sh installers' warning when other users can write to APOTHEM_HOME.

``install.sh`` and ``update.sh`` call ``warn_home_access`` once, before the
engine first runs from APOTHEM_HOME. It warns, and never stops the run, when
the permission bits or an access list (``getfacl``, where installed) let
users other than you write to APOTHEM_HOME (or, for a home not made yet, when
the umask would), or rename what the folder holding it holds, and when either
folder belongs to a user other than you or root. A group named after you is
your user-private group (umask 002 setups on Debian, Ubuntu, Fedora and RHEL),
so its write bit is no warning. Git Bash, MSYS2 and Cygwin make the bits up
from Windows permissions, so the check is skipped there; on Windows the ps1
scripts give the warning.

These tests run the two functions, as install.sh carries them, under sh with
a ``warn`` that prints its text, and stub ``id``, ``uname``, ``stat`` and
``getfacl`` on PATH where a test needs another answer.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
INSTALLER: Path = REPO_ROOT / "scripts" / "installer"
SH_SCRIPT: str = (INSTALLER / "install.sh").read_text(encoding="utf-8")

#: Owner-only folder (rwx------), the shape of a private parent.
PRIVATE_DIR = 0o700
#: The folder a umask of 022 makes (rwxr-xr-x).
DEFAULT_DIR = 0o755
#: A folder anyone can write to (rwxrwxrwx).
OPEN_DIR = 0o777
#: A folder anyone can write to, with the sticky bit (rwxrwxrwt), as /tmp.
STICKY_OPEN_DIR = 0o1777
#: Permission bits of the stub programs (rwxr-xr-x).
EXECUTABLE_MODE = 0o755

TEST_USER = "apothem-test-user"
H_OPENING = "Other users can change the code Apothem runs as you:"
P_OPENING = "Other users can replace "
OWNER_FIX = "To fix it, move APOTHEM_HOME into a folder you own."

posix_only = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("sh") is None,
    reason="reads POSIX permission bits; install.ps1 checks Windows permissions",
)


def _sh_function(script: str, name: str) -> str:
    """The definition of shell function NAME, from ``NAME() {`` to the
    closing ``}`` at column 0."""
    match = re.search(rf"^{name}\(\) \{{\n.*?^\}}$", script, re.MULTILINE | re.DOTALL)
    assert match, f"no {name}() definition found"
    return match.group(0)


def _posix_sh() -> str | None:
    """Git for Windows' sh on Windows (found from git on PATH), else sh."""
    if sys.platform != "win32":
        return shutil.which("sh")
    git = shutil.which("git")
    if git is None:
        return None
    for root in Path(git).resolve().parents[:3]:
        for candidate in (root / "usr" / "bin" / "sh.exe", root / "bin" / "sh.exe"):
            if candidate.is_file():
                return str(candidate)
    return None


_SH = _posix_sh()

PROGRAM = (
    "set -eu\n"
    "warn() { printf 'WARN %s\\n' \"$*\"; }\n"
    + _sh_function(SH_SCRIPT, "warn_writable")
    + "\n"
    + _sh_function(SH_SCRIPT, "warn_home_access")
    + "\nwarn_home_access\nprintf 'DONE\\n'\n"
)


def _stub_bin(
    tmp_path: Path,
    *,
    user: str | None,
    group: str | None,
    uname: str | None,
    stat_group: str | None = None,
    uid: str | None = None,
    acl: dict[str, str] | None = None,
    owner_number: tuple[str, str] | None = None,
) -> Path:
    """A folder of stub programs: ``id -un`` prints USER, ``id -gn`` prints
    GROUP and ``id -u`` prints UID (other ``id`` calls run the real one);
    ``uname`` prints UNAME; ``stat`` prints STAT_GROUP; ``getfacl`` prints
    ACL's text for each folder ACL names and nothing for any other;
    ``ls -ldnL`` gives OWNER_NUMBER's folder the owner number it names, or
    fails when that number is ``fail`` (other ``ls`` calls run the real
    one). A None leaves that answer to the real program."""
    stubs = tmp_path / "stub-bin"
    stubs.mkdir(exist_ok=True)
    real_id = shutil.which("id") or "/usr/bin/id"
    lines = ["#!/bin/sh"]
    if user is not None:
        lines.append(f"[ \"$1\" = -un ] && {{ printf '%s\\n' '{user}'; exit 0; }}")
    if group is not None:
        lines.append(f"[ \"$1\" = -gn ] && {{ printf '%s\\n' '{group}'; exit 0; }}")
    if uid is not None:
        lines.append(f"[ \"$1\" = -u ] && {{ printf '%s\\n' '{uid}'; exit 0; }}")
    lines.append(f"exec '{real_id}' \"$@\"")
    (stubs / "id").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (stubs / "id").chmod(EXECUTABLE_MODE)
    if uname is not None:
        (stubs / "uname").write_text(
            f"#!/bin/sh\nprintf '%s\\n' '{uname}'\n", encoding="utf-8"
        )
        (stubs / "uname").chmod(EXECUTABLE_MODE)
    if stat_group is not None:
        (stubs / "stat").write_text(
            f"#!/bin/sh\nprintf '%s\\n' '{stat_group}'\n", encoding="utf-8"
        )
        (stubs / "stat").chmod(EXECUTABLE_MODE)
    if acl is not None:
        cases = []
        for index, (folder, text) in enumerate(acl.items()):
            listing = stubs / f"acl-{index}.txt"
            listing.write_text(text + "\n", encoding="utf-8")
            cases.append(f"    '{folder}') cat '{listing}' ;;\n")
        (stubs / "getfacl").write_text(
            '#!/bin/sh\ncase "$2" in\n' + "".join(cases) + "esac\nexit 0\n",
            encoding="utf-8",
        )
        (stubs / "getfacl").chmod(EXECUTABLE_MODE)
    if owner_number is not None:
        folder, number = owner_number
        real_ls = shutil.which("ls") or "/bin/ls"
        answer = (
            "exit 2"
            if number == "fail"
            else f"'{real_ls}' \"$@\" | awk '{{ $3 = \"{number}\"; print }}'; exit 0"
        )
        (stubs / "ls").write_text(
            "#!/bin/sh\n"
            f'if [ "$1" = -ldnL ] && [ "$3" = \'{folder}\' ]; then {answer}; fi\n'
            f"exec '{real_ls}' \"$@\"\n",
            encoding="utf-8",
        )
        (stubs / "ls").chmod(EXECUTABLE_MODE)
    return stubs


def _warnings(
    tmp_path: Path,
    home: Path,
    *,
    umask: str = "022",
    user: str | None = None,
    group: str | None = None,
    uname: str | None = None,
    stat_group: str | None = None,
    uid: str | None = None,
    acl: dict[str, str] | None = None,
    owner_number: tuple[str, str] | None = None,
    shell: str | None = None,
) -> list[str]:
    """Run warn_home_access for APOTHEM_HOME=HOME and return its warnings."""
    assert _SH is not None
    stubs = _stub_bin(
        tmp_path,
        user=user,
        group=group,
        uname=uname,
        stat_group=stat_group,
        uid=uid,
        acl=acl,
        owner_number=owner_number,
    )
    env = dict(os.environ)
    env["PATH"] = f"{stubs}{os.pathsep}{env.get('PATH', os.defpath)}"
    env["APOTHEM_HOME"] = str(home)
    result = subprocess.run(
        [shell or _SH, "-c", f"umask {umask}\n{PROGRAM}"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.endswith("DONE\n"), result.stdout + result.stderr
    assert result.stderr == "", result.stderr
    return [
        line[len("WARN ") :]
        for line in result.stdout.splitlines()
        if line.startswith("WARN ")
    ]


def _folder(path: Path, mode: int) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(mode)
    return path


def _group_name(path: Path) -> str:
    import grp  # POSIX only; the tests that call this skip on Windows.

    return grp.getgrgid(path.stat().st_gid).gr_name


def _shells() -> list[str]:
    """sh, plus dash and bash where the host has them."""
    found = [_SH] if _SH else []
    for name in ("dash", "bash"):
        program = shutil.which(name)
        if program and program not in found:
            found.append(program)
    return found


@posix_only
@pytest.mark.parametrize("shell", _shells())
def test_a_private_home_in_a_private_folder_gives_no_warning(
    tmp_path: Path, shell: str
) -> None:
    parent = _folder(tmp_path / "parent", PRIVATE_DIR)
    home = _folder(parent / "home", DEFAULT_DIR)

    lines = _warnings(tmp_path, home, shell=shell)

    assert lines == []


@posix_only
@pytest.mark.parametrize("shell", _shells())
def test_a_group_writable_home_names_the_group(tmp_path: Path, shell: str) -> None:
    parent = _folder(tmp_path / "parent", PRIVATE_DIR)
    home = _folder(parent / "home", DEFAULT_DIR | stat.S_IWGRP)
    real = os.path.realpath(home)

    lines = _warnings(tmp_path, home, user=TEST_USER, shell=shell)

    assert lines == [
        f"{H_OPENING} the group {_group_name(home)} can write to {real}. "
        f'To fix it, run chmod go-w "{real}", or move APOTHEM_HOME.'
    ]


@posix_only
def test_a_group_name_with_a_space_is_named_whole(tmp_path: Path) -> None:
    """ls splits a group name such as ``domain users`` (sssd, AD-joined
    hosts) at the space; the name comes whole from stat."""
    parent = _folder(tmp_path / "parent", PRIVATE_DIR)
    home = _folder(parent / "home", DEFAULT_DIR | stat.S_IWGRP)
    real = os.path.realpath(home)

    lines = _warnings(tmp_path, home, user=TEST_USER, stat_group="domain users")

    assert lines == [
        f"{H_OPENING} the group domain users can write to {real}. "
        f'To fix it, run chmod go-w "{real}", or move APOTHEM_HOME.'
    ]


@posix_only
@pytest.mark.parametrize("shell", _shells())
def test_a_world_writable_home_names_all_users(tmp_path: Path, shell: str) -> None:
    parent = _folder(tmp_path / "parent", PRIVATE_DIR)
    home = _folder(parent / "home", DEFAULT_DIR | stat.S_IWOTH)
    real = os.path.realpath(home)

    lines = _warnings(tmp_path, home, user=TEST_USER, shell=shell)

    assert lines == [
        f'{H_OPENING} all users can write to {real}. To fix it, run chmod go-w "{real}", '
        "or move APOTHEM_HOME."
    ]


@posix_only
@pytest.mark.parametrize("made", [True, False], ids=["home-made", "home-missing"])
def test_a_user_private_group_with_umask_002_gives_no_warning(
    tmp_path: Path, made: bool
) -> None:
    """With umask 002 the home is group-writable, but the group is the one
    named after you, which holds only you."""
    parent = _folder(tmp_path / "parent", PRIVATE_DIR)
    home = parent / "home"
    if made:
        home.mkdir()
        home.chmod(0o775)
    own_group = _group_name(home if made else parent)

    lines = _warnings(tmp_path, home, umask="002", user=own_group, group=own_group)

    assert lines == []


@posix_only
@pytest.mark.parametrize("shell", _shells())
def test_a_world_writable_parent_warns_without_the_sticky_bit(
    tmp_path: Path, shell: str
) -> None:
    parent = _folder(tmp_path / "parent", OPEN_DIR)
    home = _folder(parent / "home", DEFAULT_DIR)
    real_parent = os.path.realpath(parent)
    real = os.path.realpath(home)

    lines = _warnings(tmp_path, home, shell=shell)

    assert lines == [
        f"{P_OPENING}{real}: all users can write to {real_parent}, the folder that "
        f'holds it. To fix it, run chmod go-w "{real_parent}", or move APOTHEM_HOME.'
    ]


@posix_only
def test_a_world_writable_parent_with_the_sticky_bit_gives_no_warning(
    tmp_path: Path,
) -> None:
    parent = _folder(tmp_path / "parent", STICKY_OPEN_DIR)
    home = _folder(parent / "home", DEFAULT_DIR)

    lines = _warnings(tmp_path, home)

    assert lines == []


@posix_only
@pytest.mark.parametrize("shell", _shells())
def test_a_missing_home_is_judged_by_the_umask(tmp_path: Path, shell: str) -> None:
    parent = _folder(tmp_path / "parent", PRIVATE_DIR)
    home = parent / "home"

    lines = _warnings(tmp_path, home, umask="000", shell=shell)

    assert lines == [
        f"A new {home} would let all users change the code Apothem runs as you "
        "(umask 0000). To fix it, run umask 022, then run the installer again."
    ]
    assert not home.exists()


@posix_only
@pytest.mark.parametrize("why", ["setgid", "macos"])
def test_a_missing_home_takes_the_group_a_new_folder_would_get(
    tmp_path: Path, why: str
) -> None:
    """A new folder takes the group of a setgid folder holding it, and on
    macOS and the BSDs always takes the group of the folder holding it. With
    your own group private, a dry run then names that other group, as the
    real run does once the folder is made."""
    parent = _folder(tmp_path / "parent", DEFAULT_DIR)
    if why == "setgid":
        parent.chmod(DEFAULT_DIR | stat.S_ISGID)
        if not parent.stat().st_mode & stat.S_ISGID:
            pytest.skip("this file system does not keep the setgid bit")
    home = parent / "home"

    lines = _warnings(
        tmp_path,
        home,
        umask="002",
        user=TEST_USER,
        group=TEST_USER,
        uname="Darwin" if why == "macos" else None,
    )

    assert lines == [
        f"A new {home} would let the group {_group_name(parent)} change the code "
        "Apothem runs as you (umask 0002). To fix it, run umask 022, then run the "
        "installer again."
    ]


@posix_only
def test_a_missing_home_with_umask_022_gives_no_warning(tmp_path: Path) -> None:
    parent = _folder(tmp_path / "parent", PRIVATE_DIR)

    lines = _warnings(tmp_path, parent / "home", user=TEST_USER)

    assert lines == []


@pytest.mark.skipif(_SH is None, reason="no POSIX sh on this host")
def test_git_bash_skips_the_check(tmp_path: Path) -> None:
    """Under Git Bash the mode bits come from Windows permissions, so the sh
    scripts read nothing there."""
    parent = _folder(tmp_path / "parent", OPEN_DIR)
    home = _folder(parent / "home", OPEN_DIR)

    lines = _warnings(
        tmp_path, home, umask="000", user=TEST_USER, uname="MINGW64_NT-10.0-26100"
    )

    assert lines == []


@posix_only
def test_a_linked_home_names_the_target_and_the_link(tmp_path: Path) -> None:
    """The home check reads the folder the link leads to, and the folder that
    holds the link is checked too: whoever can write to it can re-point the
    link."""
    target_parent = _folder(tmp_path / "real-parent", PRIVATE_DIR)
    target = _folder(target_parent / "target", OPEN_DIR)
    link_parent = _folder(tmp_path / "link-parent", OPEN_DIR)
    link = link_parent / "home"
    link.symlink_to(target, target_is_directory=True)
    real_link_parent = str(link_parent)
    real = os.path.realpath(target)

    lines = _warnings(tmp_path, link, user=TEST_USER)

    assert lines == [
        f"{P_OPENING}{link}: all users can write to {real_link_parent}, the folder "
        f'that holds it. To fix it, run chmod go-w "{real_link_parent}", or move '
        "APOTHEM_HOME.",
        f'{H_OPENING} all users can write to {real}. To fix it, run chmod go-w "{real}", '
        "or move APOTHEM_HOME.",
    ]


def _owner_name(path: Path) -> str:
    """The owner's name as ls prints it: the user name, or the number when
    the user has none."""
    import pwd  # POSIX only; the tests that call this skip on Windows.

    uid = path.stat().st_uid
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


@posix_only
@pytest.mark.parametrize(
    "parent_mode", [PRIVATE_DIR, STICKY_OPEN_DIR], ids=["private", "sticky"]
)
def test_a_home_and_a_folder_someone_else_owns_name_the_owner(
    tmp_path: Path, parent_mode: int
) -> None:
    """A user other than you or root who owns APOTHEM_HOME or the folder
    that holds it can change either, whatever the mode bits say, and the
    sticky bit does not stop a folder's own owner. Here ``id -u`` gives
    another number than the folders' owner, as if someone else made them."""
    if os.getuid() == 0:
        pytest.skip("root owns these folders, and root is never named")
    parent = _folder(tmp_path / "parent", parent_mode)
    home = _folder(parent / "home", DEFAULT_DIR)
    real, real_parent = os.path.realpath(home), os.path.realpath(parent)
    owner = _owner_name(home)

    lines = _warnings(tmp_path, home, uid=str(os.getuid() + 1))

    assert lines == [
        f"{H_OPENING} the user {owner} owns {real}. {OWNER_FIX}",
        f"{H_OPENING} the user {owner} owns {real_parent}. {OWNER_FIX}",
    ]


@posix_only
def test_folders_root_owns_give_no_warning(tmp_path: Path) -> None:
    """root can change any folder anyway, so a folder root owns, such as
    /usr/share, is not named. Run as root, the folder's owner is you, so
    the test would show nothing about root."""
    if os.getuid() == 0:
        pytest.skip("root owns these folders and is you here, so nothing is tested")
    home = Path("/usr/share")
    for folder in (home, home.parent):
        info = folder.stat() if folder.is_dir() else None
        if info is None or info.st_uid != 0 or info.st_mode & 0o022:
            pytest.skip(f"{folder} is not a folder only root can write")

    lines = _warnings(tmp_path, home, user=TEST_USER)

    assert lines == []


#: Access lists as getfacl prints them, each on a folder whose mode bits a
#: real access list gives it (the group bits are the mask), the group stat
#: names (None: the folder's real group, which is not yours here), and the
#: names the warning gives (empty: no warning).
ACCESS_LIST_CASES: tuple[tuple[str, int, str | None, tuple[str, ...], str], ...] = (
    (
        # You, root, a group named after you and a default entry (for what
        # is made inside) are not named; the group's own entry (group::)
        # has no w, so the mask's w in the group bits names no group.
        "named-entries",
        DEFAULT_DIR | stat.S_IWGRP,
        None,
        (
            "# file: home",
            "user::rwx",
            "user:bob:rwx",
            f"user:{TEST_USER}:rwx",
            "user:root:rwx",
            "group::r-x",
            f"group:{TEST_USER}:rwx",
            "group:staff:rwx",
            "mask::rwx",
            "other::r-x",
            "default:user:dave:rwx",
        ),
        "the user bob, the group staff",
    ),
    (
        "only-you",
        DEFAULT_DIR | stat.S_IWGRP,
        None,
        ("user::rwx", f"user:{TEST_USER}:rwx", "group::r-x", "mask::rwx", "other::r-x"),
        "",
    ),
    (
        # The mask takes write from every entry: getfacl says so after #
        # (as Linux writes it, and as FreeBSD writes it, with spaces).
        "masked",
        DEFAULT_DIR,
        None,
        (
            "user::rwx",
            "user:carol:rwx\t\t\t#effective:r-x",
            "user:erin:rwx\t\t# effective: r-x",
            "group::r-x",
            "group:wheel:rwx\t\t# effective: r-x",
            "mask::r-x",
            "other::r-x",
        ),
        "",
    ),
    (
        # The group's own entry lets it write: it is named once, first.
        "group-entry-writes",
        DEFAULT_DIR | stat.S_IWGRP,
        "staff",
        (
            "user::rwx",
            "user:bob:rwx",
            "group::rwx",
            "group:staff:rwx",
            "mask::rwx",
            "other::r-x",
        ),
        "the group staff, the user bob",
    ),
)


@posix_only
@pytest.mark.parametrize(
    ("case", "mode", "stat_group", "entries", "names"),
    ACCESS_LIST_CASES,
    ids=[c[0] for c in ACCESS_LIST_CASES],
)
def test_an_access_list_that_lets_others_write_names_them(
    tmp_path: Path,
    case: str,
    mode: int,
    stat_group: str | None,
    entries: tuple[str, ...],
    names: str,
) -> None:
    """getfacl, where installed, lists the users and groups an access list
    gives write access, and each is named. With an access list, ls shows
    the list's mask in the group bits, so the folder's group is named only
    when its own entry (group::) lets it write. You, root, a group named
    after you, an entry the mask takes write from and a default entry are
    not named; the folder holding the home has no list."""
    parent = _folder(tmp_path / "parent", PRIVATE_DIR)
    home = _folder(parent / "home", mode)
    real = os.path.realpath(home)

    lines = _warnings(
        tmp_path,
        home,
        user=TEST_USER,
        stat_group=stat_group,
        acl={real: "\n".join(entries)},
    )

    expected = (
        [
            f"{H_OPENING} {names} can write to {real}. "
            f'To fix it, run chmod go-w "{real}", or move APOTHEM_HOME.'
        ]
        if names
        else []
    )
    assert lines == expected


@posix_only
@pytest.mark.parametrize(
    ("parent_mode", "named"),
    [(0o770, True), (STICKY_OPEN_DIR, False)],
    ids=["private", "sticky"],
)
def test_an_access_list_on_the_folder_that_holds_the_home(
    tmp_path: Path, parent_mode: int, named: bool
) -> None:
    """An access-list entry that lets bob write to the folder holding the
    home lets bob rename the home away; a sticky folder stops that, so its
    access list is not read."""
    parent = _folder(tmp_path / "parent", parent_mode)
    home = _folder(parent / "home", DEFAULT_DIR)
    real, real_parent = os.path.realpath(home), os.path.realpath(parent)
    entries = ("user::rwx", "user:bob:rwx", "group::---", "mask::rwx", "other::---")

    lines = _warnings(
        tmp_path, home, user=TEST_USER, acl={real_parent: "\n".join(entries)}
    )

    expected = [
        f"{P_OPENING}{real}: the user bob can write to {real_parent}, the folder "
        f'that holds it. To fix it, run chmod go-w "{real_parent}", or move '
        "APOTHEM_HOME."
    ]
    assert lines == (expected if named else [])


@posix_only
def test_only_the_folder_that_holds_the_home_owned_by_another_user(
    tmp_path: Path,
) -> None:
    """The owner check reads each folder's own owner: here only the folder
    holding the home belongs to another user number (ls -n)."""
    if os.getuid() == 0:
        pytest.skip("root owns these folders, and root is never named")
    parent = _folder(tmp_path / "parent", PRIVATE_DIR)
    home = _folder(parent / "home", DEFAULT_DIR)
    real_parent = os.path.realpath(parent)

    lines = _warnings(tmp_path, home, owner_number=(real_parent, "4242"))

    assert lines == [
        f"{H_OPENING} the user {_owner_name(parent)} owns {real_parent}. {OWNER_FIX}"
    ]


@posix_only
def test_the_warning_goes_on_when_the_owner_number_cannot_be_read(
    tmp_path: Path,
) -> None:
    """When ls -n fails, only the owner check is lost: a home all users may
    write is still named (the ps1 scripts do the same outside Windows)."""
    parent = _folder(tmp_path / "parent", PRIVATE_DIR)
    home = _folder(parent / "home", DEFAULT_DIR | stat.S_IWOTH)
    real = os.path.realpath(home)

    lines = _warnings(tmp_path, home, user=TEST_USER, owner_number=(real, "fail"))

    assert lines == [
        f'{H_OPENING} all users can write to {real}. To fix it, run chmod go-w "{real}", '
        "or move APOTHEM_HOME."
    ]


@posix_only
@pytest.mark.parametrize("shell", _shells())
def test_a_group_name_holding_a_backslash_is_named_as_it_is(
    tmp_path: Path, shell: str
) -> None:
    """A group from a Windows domain (winbind, sssd) can hold a backslash.
    The names reach awk through the environment, which keeps a backslash;
    awk -v reads one as an escape, so \\t became a tab."""
    parent = _folder(tmp_path / "parent", PRIVATE_DIR)
    home = _folder(parent / "home", DEFAULT_DIR | stat.S_IWGRP)
    real = os.path.realpath(home)

    lines = _warnings(
        tmp_path, home, user=TEST_USER, stat_group="CORP\\tools", shell=shell
    )

    assert lines == [
        f"{H_OPENING} the group CORP\\tools can write to {real}. "
        f'To fix it, run chmod go-w "{real}", or move APOTHEM_HOME.'
    ]


@posix_only
@pytest.mark.parametrize("shell", _shells())
def test_a_user_name_holding_a_backslash_is_read_as_it_is(
    tmp_path: Path, shell: str
) -> None:
    """A user from a Windows domain can have a name such as CORP\\tom, and a
    group of that name is their own. The user name reaches awk through the
    environment too: awk -v would read it as CORP, a tab and om, and name
    the user's own group."""
    parent = _folder(tmp_path / "parent", PRIVATE_DIR)
    home = _folder(parent / "home", DEFAULT_DIR | stat.S_IWGRP)

    lines = _warnings(
        tmp_path, home, user="CORP\\tom", stat_group="CORP\\tom", shell=shell
    )

    assert lines == []


@posix_only
@pytest.mark.parametrize("shell", _shells())
def test_a_primary_group_holding_a_backslash_is_named_as_it_is(
    tmp_path: Path, shell: str
) -> None:
    """On Linux a new home takes your primary group (id -gn), which on a host
    joined to a Windows domain can hold a backslash. It reaches awk through
    the environment and is named as it is. uname is stubbed as Linux: on
    macOS and the BSDs a new folder takes the group of the folder above it."""
    parent = _folder(tmp_path / "parent", PRIVATE_DIR)
    home = parent / "home"

    lines = _warnings(
        tmp_path,
        home,
        umask="002",
        user=TEST_USER,
        group="CORP\\tools",
        uname="Linux",
        shell=shell,
    )

    assert lines == [
        f"A new {home} would let the group CORP\\tools change the code Apothem runs "
        "as you (umask 0002). To fix it, run umask 022, then run the installer again."
    ]


@posix_only
@pytest.mark.parametrize("shell", _shells())
def test_an_access_list_name_is_read_back_as_getfacl_escapes_it(
    tmp_path: Path, shell: str
) -> None:
    """getfacl writes a \\ in a name as \\\\, and a space, tab, line break,
    colon or comma as \\ and three octal digits. Each name is read back as
    it is: your own entry as a domain user (CORP\\alice, written
    CORP\\\\alice) is not named, and the others are named as they are."""
    parent = _folder(tmp_path / "parent", PRIVATE_DIR)
    home = _folder(parent / "home", DEFAULT_DIR | stat.S_IWGRP)
    real = os.path.realpath(home)
    entries = (
        "user::rwx",
        "user:CORP\\\\alice:rwx",
        "user:CORP\\\\bob:rwx",
        "group::r-x",
        "group:domain\\040admins:rwx",
        "mask::rwx",
        "other::r-x",
    )

    lines = _warnings(
        tmp_path,
        home,
        user="CORP\\alice",
        acl={real: "\n".join(entries)},
        shell=shell,
    )

    assert lines == [
        f"{H_OPENING} the user CORP\\bob, the group domain admins can write to "
        f'{real}. To fix it, run chmod go-w "{real}", or move APOTHEM_HOME.'
    ]


def test_both_sh_scripts_carry_the_same_functions() -> None:
    update = (INSTALLER / "update.sh").read_text(encoding="utf-8")
    for name in ("warn_home_access", "warn_writable"):
        assert _sh_function(update, name) == _sh_function(SH_SCRIPT, name), name
