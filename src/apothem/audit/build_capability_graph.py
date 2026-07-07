# SPDX-License-Identifier: MIT

"""Build a node-edge graph of cross-artifact references in the ecosystem.

Why this graph exists. Agents call skills. Commands invoke agents and
reference skills. Hooks bind to harness events. Output-styles route work
to specific surfaces. The textual cross-references between these
artifacts form a directed graph; without an explicit map of that graph,
orphan artifacts (no inbound edges) and dangling references (edges to
non-existent targets) stay invisible until they break at runtime. This
tool emits ``capability-graph.json`` once; downstream graph analysis
(orphan detection, dangling-reference detection) reads it.

What the graph captures. Nodes correspond to addressable ecosystem
units, keyed by their content-root-relative path: agents (one per
``agents/<name>.md``), commands (one per ``commands/*.md``), skills (one per
``skills/*/``), hooks (one per hook script under ``hooks/``), output-styles
(one per ``output-styles/*``), statuslines, and the harness events
themselves (SessionStart,
PreToolUse, PostToolUse, UserPromptSubmit, Notification, Stop,
PreCompact, PostCompact). Edges record observed textual references:
``invokes`` (agent / command body cites another agent or command),
``references`` (any artifact mentions another by name in prose),
``binds-to`` (hook artifact bound to a harness event in the engine hook
config), ``imports`` (Python module imports another).

Detection strategy. The tool first registers every node from the
inventory. It then scans the text of every node-bearing source file for
mentions of every other node's identifier. A textual match within an
artifact body emits an edge from the source artifact to the target
node. Hook bindings come from the ``hooks`` block of the engine
``hooks/hooks.json`` config rather than text scanning.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

# Edge relation taxonomy. Each edge carries exactly one relation value.
RELATION_INVOKES: Final[str] = "invokes"
RELATION_REFERENCES: Final[str] = "references"
RELATION_BINDS_TO: Final[str] = "binds-to"
RELATION_IMPORTS: Final[str] = "imports"

# Node-kind taxonomy mirrors the inventory's ecosystem classes for the
# subset that participates in the capability graph.
KIND_AGENT: Final[str] = "agent"
KIND_COMMAND: Final[str] = "command"
KIND_SKILL: Final[str] = "skill"
KIND_HOOK: Final[str] = "hook"
KIND_OUTPUT_STYLE: Final[str] = "output-style"
KIND_STATUSLINE: Final[str] = "statusline"
KIND_HARNESS_EVENT: Final[str] = "harness-event"
KIND_RULE: Final[str] = "rule"
KIND_MCP: Final[str] = "mcp"

# Canonical Claude Code hook events. Treated as virtual nodes so hook
# bindings have valid targets even though no source file represents the
# event itself.
HARNESS_EVENTS: Final[tuple[str, ...]] = (
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "Notification",
    "Stop",
    "SubagentStop",
    "PreCompact",
    "PostCompact",
)

# Content-root-relative paths whose ``hooks`` block contributes binds-to
# edges. The committed ``hooks/hooks.json`` is the source-of-truth engine
# hook block the plugin tree and the per-harness settings templates render
# from; it lives inside the scanned content root, so its variable-prefixed
# script references resolve to bare hook node ids without crossing the root.
HOOK_CONFIG_RELPATHS: Final[tuple[str, ...]] = ("hooks/hooks.json",)

# Hook-artifact references inside a ``hooks.json`` command string carry a
# variable-prefixed absolute form (e.g.
# ``"${CLAUDE_PLUGIN_ROOT}/src/apothem/hooks/lib/bootstrap.sh"``). The capture
# group isolates the content-root-relative tail (``hooks/lib/bootstrap.sh``),
# which equals the hook node id the inventory assigns; the optional
# ``src/apothem/`` segment is consumed so the captured id never carries the
# content-root prefix. Message ``.md`` files count alongside the script
# extensions because the engine config binds them to context-emitting events.
_HOOK_REF_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?:src/apothem/)?(hooks/[\w./\-]+\.(?:ps1|sh|py|md))"
)

# Filenames inside src/apothem/skills/ that mark the entry point.
SKILL_ENTRY_FILENAME: Final[str] = "SKILL.md"

# Filename suffix that marks a persistent agent (flat <name>.md under src/apothem/agents/).
AGENT_ENTRY_SUFFIX: Final[str] = ".md"

# Maximum bytes read from a source file when scanning for references.
# The reference scan only inspects body content; large files (rare in
# this corpus) are truncated to keep the scan bounded.
SCAN_MAX_BYTES: Final[int] = 256_000

# Hook-script extensions. Shell and PowerShell stubs reference their siblings
# by bare filename, not by the content-root-relative node id: a POSIX stub
# sources ``. lib/find-python.sh``, a PowerShell stub joins
# ``hooks\lib\find-python.ps1`` with backslashes, and sibling comments name the
# counterpart as ``find-pwsh.ps1``. None of those carry the forward-slash node
# id the reference scan otherwise matches, so script-to-script references
# resolve by unique basename instead (see ``scan_text_references``).
SCRIPT_SUFFIXES: Final[tuple[str, ...]] = (".sh", ".ps1")

EXIT_OK: Final[int] = 0
EXIT_ERROR: Final[int] = 1


@dataclass(slots=True)
class Node:
    """A capability-graph node — one unit with an addressable identifier."""

    id: str
    kind: str
    path: str | None  # None for harness-event virtual nodes.

    def to_json(self) -> dict[str, object]:
        """Return the node as its serialisable id / kind / path dict."""
        return {"id": self.id, "kind": self.kind, "path": self.path}


@dataclass(slots=True)
class Edge:
    """A directed reference from one node to another."""

    source: str
    target: str
    relation: str
    evidence_path: str  # Source-side path where the reference was observed.

    def to_json(self) -> dict[str, object]:
        """Return the edge as its serialisable source / target / relation / evidence dict."""
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "evidence-path": self.evidence_path,
        }


@dataclass(slots=True)
class Graph:
    """The full capability graph — nodes plus edges, deduplicated."""

    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    edge_keys: set[tuple[str, str, str]] = field(default_factory=set)

    def add_node(self, node: Node) -> None:
        """Append the node unless one with the same id and kind already exists."""
        if not any(n.id == node.id and n.kind == node.kind for n in self.nodes):
            self.nodes.append(node)

    def add_edge(self, edge: Edge) -> None:
        """Append the edge unless a (source, target, relation) duplicate is already present."""
        key = (edge.source, edge.target, edge.relation)
        if key in self.edge_keys:
            return
        self.edge_keys.add(key)
        self.edges.append(edge)


def load_inventory(path: Path) -> dict[str, object]:
    """Read inventory.json and return its parsed payload."""
    with path.open("r", encoding="utf-8") as handle:
        payload: dict[str, object] = json.load(handle)
    return payload


def derive_node_id(file_class: str, relative_path: str) -> str | None:
    """Convert an inventory entry to its capability-graph node identifier.

    Inventory paths are relative to the ecosystem content root (``src/apothem``
    in this repo), so they carry bare top-level directory prefixes —
    ``agents/<name>.md``, ``commands/<name>.md``, ``skills/<name>/SKILL.md``,
    ``rules/<name>.md`` — matching the inventory's own ``classify_file``
    keys. Agents, commands, output-styles, and rules drop that bare prefix and
    the suffix; skills derive from the parent-directory name beneath
    ``skills/``; hooks, statuslines, and MCP files use the relative path
    verbatim.
    """
    if (
        file_class == KIND_AGENT
        and relative_path.startswith("agents/")
        and relative_path.endswith(AGENT_ENTRY_SUFFIX)
    ):
        return relative_path.removeprefix("agents/").removesuffix(AGENT_ENTRY_SUFFIX)
    if file_class == KIND_COMMAND and relative_path.endswith(".md"):
        return relative_path.removeprefix("commands/").removesuffix(".md")
    if file_class == KIND_SKILL and relative_path.endswith(SKILL_ENTRY_FILENAME):
        # The parent directory of SKILL.md identifies the skill.
        parts = relative_path.split("/")
        if len(parts) >= 3 and parts[0] == "skills":
            return parts[1]
        return None
    if file_class == KIND_HOOK:
        return relative_path
    if file_class == KIND_OUTPUT_STYLE:
        return (
            relative_path.removeprefix("output-styles/")
            .removesuffix(".md")
            .removesuffix(".json")
        )
    if file_class == KIND_STATUSLINE:
        return relative_path
    if file_class == "docs" and relative_path.startswith("rules/"):
        return relative_path.removeprefix("rules/").removesuffix(".md")
    if file_class == KIND_MCP:
        return relative_path
    return None


def register_nodes(inventory: dict[str, object], graph: Graph) -> None:
    """Walk the inventory and populate ``graph.nodes`` for every addressable unit."""
    files = inventory["files"]
    if isinstance(files, list):
        _register_file_nodes(files, graph)

    # Register the canonical Claude Code hook events as virtual nodes so
    # hook bindings can target them even though no source file represents
    # an event itself.
    for event in HARNESS_EVENTS:
        graph.add_node(Node(id=event, kind=KIND_HARNESS_EVENT, path=None))


def _register_file_nodes(files: list[object], graph: Graph) -> None:
    """Register one node per addressable inventory record in ``files``."""
    for record in files:
        if not isinstance(record, dict):
            continue
        cls = record.get("class")
        path = record.get("path")
        if not isinstance(cls, str) or not isinstance(path, str):
            continue
        identifier = derive_node_id(cls, path)
        if identifier is None:
            continue

        kind_map = {
            "agent": KIND_AGENT,
            "command": KIND_COMMAND,
            "skill": KIND_SKILL,
            "hook": KIND_HOOK,
            "output-style": KIND_OUTPUT_STYLE,
            "statusline": KIND_STATUSLINE,
            "mcp": KIND_MCP,
        }
        if cls in kind_map:
            graph.add_node(Node(id=identifier, kind=kind_map[cls], path=path))
        elif cls == "docs" and path.startswith("rules/"):
            graph.add_node(Node(id=identifier, kind=KIND_RULE, path=path))


def read_text(absolute_path: Path) -> str:
    """Read up to SCAN_MAX_BYTES of the file as UTF-8 text."""
    try:
        with absolute_path.open("rb") as handle:
            data = handle.read(SCAN_MAX_BYTES)
        return data.decode("utf-8", errors="replace")
    except OSError:
        return ""


def scan_text_references(graph: Graph, root: Path) -> None:
    """For each text source, scan for mentions of every other node identifier.

    Source nodes are agents, commands, skills, output-styles, rules, and
    hook bodies — Markdown, Python, shell, and PowerShell. The body of each
    source is read and matched against every other node's identifier as a
    whole-word reference. Matches emit an ``invokes`` edge for agent / command
    sources and a ``references`` edge for any other source kind.

    Hook scripts additionally resolve their siblings by bare filename: a shell
    or PowerShell stub names ``find-python.sh``, the backslash path
    ``hooks\\lib\\find-python.ps1``, or the counterpart ``find-pwsh.ps1`` — never
    the forward-slash node id — so script-source bodies are scanned for the
    unique basenames of script nodes as well.
    """
    text_kinds = {
        KIND_AGENT,
        KIND_COMMAND,
        KIND_SKILL,
        KIND_OUTPUT_STYLE,
        KIND_RULE,
        KIND_HOOK,
    }

    non_event_nodes = [n for n in graph.nodes if n.kind != KIND_HARNESS_EVENT]
    target_ids = sorted(
        {n.id for n in non_event_nodes},
        key=len,
        reverse=True,
    )
    patterns: dict[str, re.Pattern[str]] = {
        identifier: re.compile(rf"\b{re.escape(identifier)}\b")
        for identifier in target_ids
    }

    # Script-sibling basename index: a shell / PowerShell stub references its
    # siblings by filename, not by the content-root-relative node id. Map each
    # script node's basename to its id, dropping basenames shared by more than
    # one node so an ambiguous filename never mis-attributes an edge.
    basename_ids: dict[str, list[str]] = {}
    for node in non_event_nodes:
        if node.path and node.path.endswith(SCRIPT_SUFFIXES):
            basename_ids.setdefault(node.path.rsplit("/", 1)[-1], []).append(node.id)
    script_targets: dict[str, str] = {
        base: ids[0] for base, ids in basename_ids.items() if len(ids) == 1
    }
    script_patterns: dict[str, re.Pattern[str]] = {
        base: re.compile(rf"\b{re.escape(base)}\b") for base in script_targets
    }

    for source in graph.nodes:
        if source.kind not in text_kinds or source.path is None:
            continue
        if source.kind == KIND_HOOK and not source.path.endswith(
            (".md", ".py", *SCRIPT_SUFFIXES)
        ):
            continue

        absolute = root / source.path
        body = read_text(absolute)
        if not body:
            continue

        for target_id in target_ids:
            if target_id == source.id:
                continue
            if patterns[target_id].search(body):
                relation = (
                    RELATION_INVOKES
                    if source.kind in (KIND_AGENT, KIND_COMMAND)
                    else RELATION_REFERENCES
                )
                graph.add_edge(
                    Edge(
                        source=source.id,
                        target=target_id,
                        relation=relation,
                        evidence_path=source.path,
                    )
                )

        # Script siblings resolve their counterparts by bare filename, which
        # the content-root-relative node-id scan above never matches.
        if not source.path.endswith(SCRIPT_SUFFIXES):
            continue
        for base, pattern in script_patterns.items():
            target_id = script_targets[base]
            if target_id == source.id:
                continue
            if pattern.search(body):
                graph.add_edge(
                    Edge(
                        source=source.id,
                        target=target_id,
                        relation=RELATION_REFERENCES,
                        evidence_path=source.path,
                    )
                )


def scan_hook_bindings(graph: Graph, root: Path) -> None:
    """Parse the engine hook config for event-name → hook-artifact bindings.

    The committed ``hooks/hooks.json`` is the source-of-truth hook block the
    plugin tree and the per-harness settings templates render from. Each
    entry in its ``hooks`` block binds one or more hook artifacts — a
    bootstrap stub plus, for context-emitting events, a message file — to a
    harness event; every such pairing emits a ``binds-to`` edge from the hook
    node to the event node. A single command may reference several artifacts,
    so every distinct on-disk reference contributes its own edge.
    """
    for relpath in HOOK_CONFIG_RELPATHS:
        path = root / relpath
        if not path.is_file():
            continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                config = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(config, dict):
            continue

        hooks_block = config.get("hooks", {})
        if not isinstance(hooks_block, dict):
            continue

        for event_name, entries in hooks_block.items():
            if event_name not in HARNESS_EVENTS:
                continue
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                hook_handlers = entry.get("hooks", [])
                if not isinstance(hook_handlers, list):
                    continue
                for handler in hook_handlers:
                    if not isinstance(handler, dict):
                        continue
                    command = handler.get("command", "")
                    if not isinstance(command, str):
                        continue
                    for node_id in _extract_hook_node_ids(command, root):
                        graph.add_edge(
                            Edge(
                                source=node_id,
                                target=event_name,
                                relation=RELATION_BINDS_TO,
                                evidence_path=relpath,
                            )
                        )


def _extract_hook_node_ids(command: str, root: Path) -> list[str]:
    """Extract the content-root-relative hook node ids a command references.

    A ``hooks.json`` ``command`` field is a shell invocation (PowerShell or
    bash) that runs one or more hook artifacts — a bootstrap stub, and for
    context-emitting events the per-event message file. Each is named by a
    variable-prefixed path (e.g.
    ``"${CLAUDE_PLUGIN_ROOT}/src/apothem/hooks/messages/stop.md"``); the
    meaningful ``binds-to`` target is the content-root-relative tail
    (``hooks/messages/stop.md``), which equals the inventory's hook node id.
    Every distinct reference that resolves to a file on disk is returned in
    first-seen order, so a single command binds every hook node it names.
    """
    node_ids: list[str] = []
    seen: set[str] = set()
    for match in _HOOK_REF_PATTERN.finditer(command):
        node_id = match.group(1)
        if node_id in seen:
            continue
        if not (root / node_id).is_file():
            continue
        seen.add(node_id)
        node_ids.append(node_id)
    return node_ids


def _python_import_names(relative_path: str, package_root: str) -> list[str]:
    """Module names by which the Python file at ``relative_path`` is importable.

    A file is importable under several names depending on which ancestor
    directory is on ``sys.path`` at runtime. Returns the content-root-relative
    dotted path (``hooks.lib.log``), the installed-package form
    (``apothem.hooks.lib.log``), and — for a non-package module — the bare leaf
    name (``log``). The hook bootstrap inserts both ``hooks/`` and ``hooks/lib/``
    onto ``sys.path``, so the lib modules are imported by bare leaf name
    (``from log import get_logger``); the bare-leaf candidate is what resolves
    those edges. A package ``__init__.py`` is named for its directory, never the
    literal ``__init__`` leaf, so it is never imported by leaf name.
    """
    parts = relative_path.removesuffix(".py").split("/")
    is_package = parts[-1] == "__init__"
    if is_package:
        parts = parts[:-1]
    if not parts:
        return []
    dotted = ".".join(parts)
    names = [dotted, f"{package_root}.{dotted}"]
    if not is_package:
        names.append(parts[-1])
    return names


def scan_python_imports(graph: Graph, root: Path) -> None:
    """Trace import edges between Python source files in the graph.

    Each Python node is indexed under every module name it answers to (see
    ``_python_import_names``). An import statement whose module equals a known
    name — or names a submodule of a known package — emits an ``imports`` edge
    to that node. Bare-leaf indexing is what makes the hook lib modules resolve:
    they are imported by bare name (``from log import …``) because the bootstrap
    puts ``hooks/lib/`` on ``sys.path``, never by their content-root dotted path.
    """
    # Pair each Python node with its non-None path so the edge endpoints are
    # typed ``str`` rather than ``str | None``.
    py_paths: list[tuple[Node, str]] = [
        (n, n.path)
        for n in graph.nodes
        if n.path is not None and n.path.endswith(".py")
    ]
    # Index every importable name to its file. First-seen wins on the rare
    # basename collision; package ``__init__`` modules are excluded from bare-
    # leaf indexing, so collisions are vanishingly unlikely in practice.
    module_index: dict[str, str] = {}
    for _node, path in py_paths:
        for candidate in _python_import_names(path, root.name):
            module_index.setdefault(candidate, path)

    import_pattern = re.compile(
        r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))",
        re.MULTILINE,
    )

    for _source, source_path in py_paths:
        body = read_text(root / source_path)
        if not body:
            continue
        for match in import_pattern.finditer(body):
            module = match.group(1) or match.group(2)
            if not module:
                continue
            for known_module, known_path in module_index.items():
                if module == known_module or module.startswith(known_module + "."):
                    if known_path == source_path:
                        continue
                    graph.add_edge(
                        Edge(
                            source=source_path,
                            target=known_path,
                            relation=RELATION_IMPORTS,
                            evidence_path=source_path,
                        )
                    )


def emit_graph(graph: Graph, output: Path) -> None:
    """Serialise the graph to ``output`` as pretty-printed JSON."""
    payload = {
        "generated-at": datetime.now(tz=timezone.utc).isoformat(),
        "node-count": len(graph.nodes),
        "edge-count": len(graph.edges),
        "nodes": sorted(
            (n.to_json() for n in graph.nodes),
            key=lambda n: (n["kind"], n["id"]),
        ),
        "edges": sorted(
            (e.to_json() for e in graph.edges),
            key=lambda e: (e["source"], e["relation"], e["target"]),
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False, ensure_ascii=False)
        handle.write("\n")


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """CLI surface — root, inventory, and output are required."""
    parser = argparse.ArgumentParser(
        prog="build_capability_graph",
        description="Build a capability graph from the inventory.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        required=True,
        help="Working-tree root containing the source artifacts.",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        required=True,
        help="Inventory JSON path produced by build_inventory.py.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output JSON path (e.g., .audit/capability-graph.json).",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    """Entry point — returns the exit code."""
    args = parse_arguments(argv)
    root = args.root.resolve()
    inventory_path = args.inventory.resolve()
    output = args.output.resolve()

    if not inventory_path.is_file():
        print(f"error: inventory not found: {inventory_path}", file=sys.stderr)
        return EXIT_ERROR

    inventory = load_inventory(inventory_path)
    graph = Graph()
    register_nodes(inventory, graph)
    scan_text_references(graph, root)
    scan_hook_bindings(graph, root)
    scan_python_imports(graph, root)
    emit_graph(graph, output)

    print(
        f"capability-graph: {len(graph.nodes)} nodes; "
        f"{len(graph.edges)} edges; output={output}"
    )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
