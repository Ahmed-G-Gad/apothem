# SPDX-License-Identifier: MIT

"""Unit tests for the capability-graph builder.

``apothem.audit.build_capability_graph`` registers one node per addressable
ecosystem unit, then scans artifact bodies, settings hook blocks, and Python
imports to emit the cross-reference edges ``analyze_graph`` later consumes. The
node-id derivation, the four scanners, and the serializer are pure transforms
over inventory records and on-disk text, so they are covered directly; ``main``
is exercised end-to-end through a fixture tree written to ``tmp_path``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apothem.audit.build_capability_graph import (
    EXIT_ERROR,
    EXIT_OK,
    KIND_HARNESS_EVENT,
    RELATION_BINDS_TO,
    RELATION_IMPORTS,
    RELATION_INVOKES,
    RELATION_REFERENCES,
    SCAN_MAX_BYTES,
    Edge,
    Graph,
    Node,
    _extract_hook_node_ids,
    _python_import_names,
    derive_node_id,
    emit_graph,
    load_inventory,
    main,
    read_text,
    register_nodes,
    scan_hook_bindings,
    scan_python_imports,
    scan_text_references,
)


class TestNodeAndEdge:
    def test_node_to_json_round_trips_fields(self) -> None:
        node = Node(id="rule-a", kind="rule", path="src/apothem/rules/a.md")
        assert node.to_json() == {
            "id": "rule-a",
            "kind": "rule",
            "path": "src/apothem/rules/a.md",
        }

    def test_edge_to_json_renames_evidence_path_to_hyphen(self) -> None:
        edge = Edge(source="a", target="b", relation="invokes", evidence_path="a.md")
        assert edge.to_json() == {
            "source": "a",
            "target": "b",
            "relation": "invokes",
            "evidence-path": "a.md",
        }


class TestGraphDedup:
    def test_add_node_is_idempotent_per_id_and_kind(self) -> None:
        graph = Graph()
        graph.add_node(Node(id="a", kind="rule", path="a.md"))
        graph.add_node(Node(id="a", kind="rule", path="a.md"))

        assert len(graph.nodes) == 1

    def test_same_id_different_kind_is_distinct(self) -> None:
        graph = Graph()
        graph.add_node(Node(id="a", kind="rule", path="a.md"))
        graph.add_node(Node(id="a", kind="skill", path="a/SKILL.md"))

        assert len(graph.nodes) == 2

    def test_add_edge_dedups_on_source_target_relation(self) -> None:
        graph = Graph()
        graph.add_edge(Edge("a", "b", "invokes", "a.md"))
        graph.add_edge(Edge("a", "b", "invokes", "other.md"))  # same key -> dropped
        graph.add_edge(Edge("a", "b", "references", "a.md"))  # different relation

        assert len(graph.edges) == 2


class TestDeriveNodeId:
    # Inventory paths are relative to the content root (src/apothem), so they
    # carry bare top-level directory prefixes — agents/, commands/, rules/ —
    # the same keys the inventory's classify_file matches on.
    def test_agent_drops_prefix_and_suffix(self) -> None:
        assert derive_node_id("agent", "agents/explorer.md") == "explorer"

    def test_command_drops_prefix_and_suffix(self) -> None:
        assert derive_node_id("command", "commands/plan.md") == "plan"

    def test_skill_derives_from_parent_dir_under_skills_prefix(self) -> None:
        assert derive_node_id("skill", "skills/refactor/SKILL.md") == "refactor"
        # A non-bare 'src/apothem/skills/...' form is not the inventory scheme.
        assert derive_node_id("skill", "src/apothem/skills/refactor/SKILL.md") is None

    def test_hook_uses_relative_path_verbatim(self) -> None:
        assert derive_node_id("hook", "hooks/dispatch.py") == "hooks/dispatch.py"

    def test_output_style_drops_prefix_and_either_suffix(self) -> None:
        assert derive_node_id("output-style", "output-styles/concise.md") == "concise"

    def test_rule_docs_path_drops_rules_prefix(self) -> None:
        assert derive_node_id("docs", "rules/naturalism.md") == "naturalism"

    def test_statusline_and_mcp_use_relative_path_verbatim(self) -> None:
        assert (
            derive_node_id("statusline", "statuslines/line.py") == "statuslines/line.py"
        )
        assert derive_node_id("mcp", "mcp/server.json") == "mcp/server.json"

    def test_prefixed_form_is_not_the_inventory_scheme(self) -> None:
        # Regression guard: a stale 'src/apothem/'-prefixed path (which the
        # inventory never emits) does not derive an agent or rule id. Before
        # the prefix fix, the agent/rule branches keyed off this form and so
        # silently produced zero agent and zero rule nodes.
        assert derive_node_id("agent", "src/apothem/agents/explorer.md") is None
        assert derive_node_id("docs", "src/apothem/rules/naturalism.md") is None

    def test_unmatched_class_returns_none(self) -> None:
        assert derive_node_id("memory", "memory/topic.md") is None
        # A docs file outside the rules tree is not a rule node.
        assert derive_node_id("docs", "site/content/docs/page.md") is None


class TestRegisterNodes:
    def test_populates_nodes_and_virtual_events(self) -> None:
        inventory: dict[str, Any] = {
            "files": [
                {"class": "agent", "path": "agents/explorer.md"},
                {"class": "command", "path": "commands/plan.md"},
                {"class": "docs", "path": "rules/naturalism.md"},
                {"class": "memory", "path": "memory/x.md"},  # not addressable
            ]
        }
        graph = Graph()
        register_nodes(inventory, graph)

        kinds = {(n.id, n.kind) for n in graph.nodes}
        assert ("explorer", "agent") in kinds
        assert ("plan", "command") in kinds
        assert ("naturalism", "rule") in kinds
        # Every canonical harness event is registered as a virtual node.
        events = {n.id for n in graph.nodes if n.kind == KIND_HARNESS_EVENT}
        assert "SessionStart" in events
        assert "PostToolUse" in events


class TestReadText:
    def test_reads_utf8(self, tmp_path: Path) -> None:
        f = tmp_path / "a.md"
        f.write_text("hello", encoding="utf-8")
        assert read_text(f) == "hello"

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert read_text(tmp_path / "absent.md") == ""

    def test_truncates_to_scan_max_bytes(self, tmp_path: Path) -> None:
        f = tmp_path / "big.md"
        f.write_text("x" * (SCAN_MAX_BYTES + 50), encoding="utf-8")
        assert len(read_text(f)) == SCAN_MAX_BYTES


class TestScanTextReferences:
    def test_agent_source_emits_invokes_other_emits_references(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "src/apothem/agents").mkdir(parents=True)
        (tmp_path / "src/apothem/rules").mkdir(parents=True)
        # The agent body mentions the rule id 'naturalism'.
        (tmp_path / "src/apothem/agents/explorer.md").write_text(
            "This agent honors naturalism when scanning.", encoding="utf-8"
        )
        # The rule body mentions the agent id 'explorer'.
        (tmp_path / "src/apothem/rules/naturalism.md").write_text(
            "The explorer surface is in scope.", encoding="utf-8"
        )
        graph = Graph()
        graph.add_node(
            Node(id="explorer", kind="agent", path="src/apothem/agents/explorer.md")
        )
        graph.add_node(
            Node(id="naturalism", kind="rule", path="src/apothem/rules/naturalism.md")
        )

        scan_text_references(graph, tmp_path)

        rels = {(e.source, e.target, e.relation) for e in graph.edges}
        # Agent -> rule is 'invokes'; rule -> agent is 'references'.
        assert ("explorer", "naturalism", RELATION_INVOKES) in rels
        assert ("naturalism", "explorer", RELATION_REFERENCES) in rels

    def test_self_reference_is_not_an_edge(self, tmp_path: Path) -> None:
        (tmp_path / "src/apothem/rules").mkdir(parents=True)
        (tmp_path / "src/apothem/rules/naturalism.md").write_text(
            "naturalism naturalism naturalism", encoding="utf-8"
        )
        graph = Graph()
        graph.add_node(
            Node(id="naturalism", kind="rule", path="src/apothem/rules/naturalism.md")
        )

        scan_text_references(graph, tmp_path)

        assert graph.edges == []

    def test_shell_source_resolves_sibling_by_full_node_id(
        self, tmp_path: Path
    ) -> None:
        # Regression guard: a shell hook stub naming a sibling by its
        # content-root path emits a references edge once .sh bodies are scanned.
        # Before scanning shell bodies, hooks/lib/find-python.sh looked orphan.
        (tmp_path / "hooks/lib").mkdir(parents=True)
        (tmp_path / "hooks/lib/bootstrap.sh").write_text(
            'locator="$root/hooks/lib/find-python.sh"', encoding="utf-8"
        )
        (tmp_path / "hooks/lib/find-python.sh").write_text("x", encoding="utf-8")
        graph = Graph()
        graph.add_node(
            Node(
                id="hooks/lib/bootstrap.sh",
                kind="hook",
                path="hooks/lib/bootstrap.sh",
            )
        )
        graph.add_node(
            Node(
                id="hooks/lib/find-python.sh",
                kind="hook",
                path="hooks/lib/find-python.sh",
            )
        )

        scan_text_references(graph, tmp_path)

        rels = {(e.source, e.target, e.relation) for e in graph.edges}
        assert (
            "hooks/lib/bootstrap.sh",
            "hooks/lib/find-python.sh",
            RELATION_REFERENCES,
        ) in rels

    def test_script_sibling_resolves_by_bare_basename(self, tmp_path: Path) -> None:
        # find-pwsh.* is referenced only by bare filename (a sibling comment, a
        # backslash path) — never by the forward-slash node id. Unique-basename
        # matching is what removes its false-orphan flag.
        (tmp_path / "hooks/lib").mkdir(parents=True)
        (tmp_path / "hooks/lib/find-pwsh.sh").write_text(
            "# Sibling: find-pwsh.ps1 (PowerShell counterpart)", encoding="utf-8"
        )
        (tmp_path / "hooks/lib/find-pwsh.ps1").write_text("x", encoding="utf-8")
        graph = Graph()
        graph.add_node(
            Node(
                id="hooks/lib/find-pwsh.sh",
                kind="hook",
                path="hooks/lib/find-pwsh.sh",
            )
        )
        graph.add_node(
            Node(
                id="hooks/lib/find-pwsh.ps1",
                kind="hook",
                path="hooks/lib/find-pwsh.ps1",
            )
        )

        scan_text_references(graph, tmp_path)

        rels = {(e.source, e.target, e.relation) for e in graph.edges}
        assert (
            "hooks/lib/find-pwsh.sh",
            "hooks/lib/find-pwsh.ps1",
            RELATION_REFERENCES,
        ) in rels

    def test_backslash_path_resolves_by_basename(self, tmp_path: Path) -> None:
        # A PowerShell stub joins the locator path with backslashes
        # (hooks\lib\find-python.ps1); the forward-slash node id never matches,
        # but the bare basename does.
        (tmp_path / "hooks/lib").mkdir(parents=True)
        (tmp_path / "hooks/lib/bootstrap.ps1").write_text(
            "$locator = Join-Path $root 'hooks\\lib\\find-python.ps1'",
            encoding="utf-8",
        )
        (tmp_path / "hooks/lib/find-python.ps1").write_text("x", encoding="utf-8")
        graph = Graph()
        graph.add_node(
            Node(
                id="hooks/lib/bootstrap.ps1",
                kind="hook",
                path="hooks/lib/bootstrap.ps1",
            )
        )
        graph.add_node(
            Node(
                id="hooks/lib/find-python.ps1",
                kind="hook",
                path="hooks/lib/find-python.ps1",
            )
        )

        scan_text_references(graph, tmp_path)

        rels = {(e.source, e.target, e.relation) for e in graph.edges}
        assert (
            "hooks/lib/bootstrap.ps1",
            "hooks/lib/find-python.ps1",
            RELATION_REFERENCES,
        ) in rels

    def test_ambiguous_basename_is_not_matched(self, tmp_path: Path) -> None:
        # Two script nodes share the basename 'common.sh'; a bare-name reference
        # must NOT mis-attribute an edge to either — ambiguous basenames are
        # dropped from the index.
        (tmp_path / "a").mkdir(parents=True)
        (tmp_path / "b").mkdir(parents=True)
        (tmp_path / "hooks/lib").mkdir(parents=True)
        (tmp_path / "hooks/lib/caller.sh").write_text(". common.sh", encoding="utf-8")
        (tmp_path / "a/common.sh").write_text("x", encoding="utf-8")
        (tmp_path / "b/common.sh").write_text("x", encoding="utf-8")
        graph = Graph()
        graph.add_node(
            Node(id="hooks/lib/caller.sh", kind="hook", path="hooks/lib/caller.sh")
        )
        graph.add_node(Node(id="a/common.sh", kind="hook", path="a/common.sh"))
        graph.add_node(Node(id="b/common.sh", kind="hook", path="b/common.sh"))

        scan_text_references(graph, tmp_path)

        targets = {e.target for e in graph.edges}
        assert "a/common.sh" not in targets
        assert "b/common.sh" not in targets

    def test_non_script_hook_body_is_not_scanned(self, tmp_path: Path) -> None:
        # A .json hook body (e.g. the engine hooks.json) is not a text-reference
        # source; the engine config is read by scan_hook_bindings instead.
        (tmp_path / "hooks").mkdir(parents=True)
        (tmp_path / "rules").mkdir(parents=True)
        (tmp_path / "hooks/config.json").write_text("naturalism", encoding="utf-8")
        (tmp_path / "rules/naturalism.md").write_text("rule", encoding="utf-8")
        graph = Graph()
        graph.add_node(
            Node(id="hooks/config.json", kind="hook", path="hooks/config.json")
        )
        graph.add_node(Node(id="naturalism", kind="rule", path="rules/naturalism.md"))

        scan_text_references(graph, tmp_path)

        sources = {e.source for e in graph.edges}
        assert "hooks/config.json" not in sources


class TestScanHookBindings:
    # The engine hook config lives at the content-root-relative
    # ``hooks/hooks.json``; its command strings name hook artifacts by a
    # variable-prefixed path the scan resolves to a bare ``hooks/<...>`` id.
    @staticmethod
    def _write_config(root: Path, config: dict[str, Any]) -> None:
        (root / "hooks").mkdir(parents=True, exist_ok=True)
        (root / "hooks/hooks.json").write_text(json.dumps(config), encoding="utf-8")

    def test_binds_each_referenced_artifact_to_its_event(self, tmp_path: Path) -> None:
        # One command names a bootstrap stub AND a message file; both bind to
        # the event, keyed by their bare content-root-relative node ids.
        (tmp_path / "hooks/lib").mkdir(parents=True)
        (tmp_path / "hooks/messages").mkdir(parents=True)
        (tmp_path / "hooks/lib/bootstrap.sh").write_text("x", encoding="utf-8")
        (tmp_path / "hooks/messages/stop.md").write_text("x", encoding="utf-8")
        command = (
            '"${CLAUDE_PLUGIN_ROOT}/src/apothem/hooks/lib/bootstrap.sh" Stop '
            '"${CLAUDE_PLUGIN_ROOT}/src/apothem/hooks/messages/stop.md"'
        )
        self._write_config(
            tmp_path, {"hooks": {"Stop": [{"hooks": [{"command": command}]}]}}
        )
        graph = Graph()

        scan_hook_bindings(graph, tmp_path)

        rels = {(e.source, e.target, e.relation) for e in graph.edges}
        assert ("hooks/lib/bootstrap.sh", "Stop", RELATION_BINDS_TO) in rels
        assert ("hooks/messages/stop.md", "Stop", RELATION_BINDS_TO) in rels

    def test_missing_config_file_is_a_no_op(self, tmp_path: Path) -> None:
        graph = Graph()
        scan_hook_bindings(graph, tmp_path)
        assert graph.edges == []

    def test_malformed_json_is_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "hooks").mkdir(parents=True)
        (tmp_path / "hooks/hooks.json").write_text("{ not json", encoding="utf-8")
        graph = Graph()
        scan_hook_bindings(graph, tmp_path)
        assert graph.edges == []

    def test_defensive_guards_against_malformed_hook_block(
        self, tmp_path: Path
    ) -> None:
        # Each malformed shape exercises a distinct guard: unknown event name,
        # non-dict entry, non-list handlers, non-dict handler, non-str command,
        # and a command with no resolvable hook path.
        config: dict[str, Any] = {
            "hooks": {
                "NotAnEvent": [{"hooks": [{"command": "x"}]}],  # unknown event
                "Stop": [
                    "not-a-dict",  # entry not a dict
                    {"hooks": "not-a-list"},  # hook_handlers not a list
                    {"hooks": ["not-a-dict-handler"]},  # handler not a dict
                    {"hooks": [{"command": 123}]},  # command not a str
                    {"hooks": [{"command": "echo no-hook-path-here"}]},  # no path
                ],
            }
        }
        self._write_config(tmp_path, config)
        graph = Graph()

        scan_hook_bindings(graph, tmp_path)

        # No edge survives any of the malformed shapes.
        assert graph.edges == []

    def test_non_dict_hooks_block_is_skipped(self, tmp_path: Path) -> None:
        self._write_config(tmp_path, {"hooks": "not-a-dict"})
        graph = Graph()
        scan_hook_bindings(graph, tmp_path)
        assert graph.edges == []

    def test_non_dict_root_config_is_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "hooks").mkdir(parents=True)
        (tmp_path / "hooks/hooks.json").write_text("[]", encoding="utf-8")
        graph = Graph()
        scan_hook_bindings(graph, tmp_path)
        assert graph.edges == []


class TestExtractHookNodeIds:
    def test_returns_all_resolvable_bare_node_ids_in_order(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "hooks/lib").mkdir(parents=True)
        (tmp_path / "hooks/messages").mkdir(parents=True)
        (tmp_path / "hooks/lib/bootstrap.ps1").write_text("x", encoding="utf-8")
        (tmp_path / "hooks/messages/pretooluse-write.md").write_text(
            "x", encoding="utf-8"
        )
        command = (
            'pwsh -File "${CLAUDE_PLUGIN_ROOT}/src/apothem/hooks/lib/bootstrap.ps1" '
            "PreToolUse "
            '"${CLAUDE_PLUGIN_ROOT}/src/apothem/hooks/messages/pretooluse-write.md"'
        )

        # The src/apothem/ prefix is stripped; ids are first-seen order.
        assert _extract_hook_node_ids(command, tmp_path) == [
            "hooks/lib/bootstrap.ps1",
            "hooks/messages/pretooluse-write.md",
        ]

    def test_unresolvable_path_is_omitted(self, tmp_path: Path) -> None:
        command = "python ${CLAUDE_PLUGIN_ROOT}/src/apothem/hooks/ghost.py"
        assert _extract_hook_node_ids(command, tmp_path) == []

    def test_duplicate_references_are_deduped(self, tmp_path: Path) -> None:
        (tmp_path / "hooks").mkdir(parents=True)
        (tmp_path / "hooks/dispatch.py").write_text("x", encoding="utf-8")
        command = (
            "${CLAUDE_PLUGIN_ROOT}/src/apothem/hooks/dispatch.py "
            "${CLAUDE_PLUGIN_ROOT}/src/apothem/hooks/dispatch.py"
        )
        assert _extract_hook_node_ids(command, tmp_path) == ["hooks/dispatch.py"]

    def test_bare_hooks_prefix_without_src_apothem_resolves(
        self, tmp_path: Path
    ) -> None:
        # The src/apothem/ segment is optional; a bare hooks/ reference resolves.
        (tmp_path / "hooks").mkdir(parents=True)
        (tmp_path / "hooks/dispatch.py").write_text("x", encoding="utf-8")
        assert _extract_hook_node_ids("run hooks/dispatch.py now", tmp_path) == [
            "hooks/dispatch.py"
        ]


class TestPythonImportNames:
    def test_module_indexes_full_dotted_package_and_bare_leaf(self) -> None:
        # A non-package module answers to its content-root dotted path, the
        # installed-package form, and its bare leaf name — the form the hook
        # bootstrap imports it by once hooks/lib/ is on sys.path.
        assert _python_import_names("hooks/lib/log.py", "apothem") == [
            "hooks.lib.log",
            "apothem.hooks.lib.log",
            "log",
        ]

    def test_package_init_is_named_for_directory_not_leaf(self) -> None:
        # __init__.py is never imported by the literal '__init__' leaf; it is
        # named for its directory, so no bare-leaf candidate is produced and a
        # bare 'import __init__' can never bind a package marker.
        assert _python_import_names("hooks/lib/__init__.py", "apothem") == [
            "hooks.lib",
            "apothem.hooks.lib",
        ]


class TestScanPythonImports:
    def test_bare_leaf_import_resolves_to_lib_module(self, tmp_path: Path) -> None:
        # Regression guard: the hook lib modules are imported by bare leaf name
        # (the bootstrap puts hooks/lib/ on sys.path), never by the content-root
        # dotted path. Before bare-leaf indexing, this produced zero import
        # edges and hooks/lib/log.py looked like an orphan.
        (tmp_path / "hooks/lib").mkdir(parents=True)
        (tmp_path / "hooks/emit_hook_context.py").write_text(
            "from log import get_logger", encoding="utf-8"
        )
        (tmp_path / "hooks/lib/log.py").write_text("x", encoding="utf-8")
        graph = Graph()
        graph.add_node(
            Node(
                id="hooks/emit_hook_context.py",
                kind="hook",
                path="hooks/emit_hook_context.py",
            )
        )
        graph.add_node(
            Node(id="hooks/lib/log.py", kind="hook", path="hooks/lib/log.py")
        )

        scan_python_imports(graph, tmp_path)

        rels = {(e.source, e.target, e.relation) for e in graph.edges}
        assert (
            "hooks/emit_hook_context.py",
            "hooks/lib/log.py",
            RELATION_IMPORTS,
        ) in rels

    def test_similar_bare_name_does_not_false_match(self, tmp_path: Path) -> None:
        # A stdlib import whose name is a prefix of a bare-leaf node ('logging'
        # vs 'log') must not bind the node — the prefix match requires a dotted
        # boundary, not a substring.
        (tmp_path / "hooks/lib").mkdir(parents=True)
        (tmp_path / "hooks/dispatch.py").write_text("import logging", encoding="utf-8")
        (tmp_path / "hooks/lib/log.py").write_text("x", encoding="utf-8")
        graph = Graph()
        graph.add_node(
            Node(id="hooks/dispatch.py", kind="hook", path="hooks/dispatch.py")
        )
        graph.add_node(
            Node(id="hooks/lib/log.py", kind="hook", path="hooks/lib/log.py")
        )

        scan_python_imports(graph, tmp_path)

        assert graph.edges == []

    def test_emits_import_edge_between_known_modules(self, tmp_path: Path) -> None:
        (tmp_path / "src/apothem/hooks").mkdir(parents=True)
        (tmp_path / "src/apothem/hooks/dispatch.py").write_text(
            "from src.apothem.hooks.helper import run", encoding="utf-8"
        )
        (tmp_path / "src/apothem/hooks/helper.py").write_text("x", encoding="utf-8")
        graph = Graph()
        graph.add_node(Node(id="d", kind="hook", path="src/apothem/hooks/dispatch.py"))
        graph.add_node(Node(id="h", kind="hook", path="src/apothem/hooks/helper.py"))

        scan_python_imports(graph, tmp_path)

        rels = {(e.source, e.target, e.relation) for e in graph.edges}
        assert (
            "src/apothem/hooks/dispatch.py",
            "src/apothem/hooks/helper.py",
            RELATION_IMPORTS,
        ) in rels

    def test_self_import_is_not_an_edge(self, tmp_path: Path) -> None:
        # A module importing its own dotted name produces no self-edge.
        (tmp_path / "src/apothem/hooks").mkdir(parents=True)
        (tmp_path / "src/apothem/hooks/dispatch.py").write_text(
            "from src.apothem.hooks.dispatch import thing", encoding="utf-8"
        )
        graph = Graph()
        graph.add_node(Node(id="d", kind="hook", path="src/apothem/hooks/dispatch.py"))

        scan_python_imports(graph, tmp_path)

        assert graph.edges == []


class TestEmitGraph:
    def test_serialises_sorted_payload_with_counts(self, tmp_path: Path) -> None:
        graph = Graph()
        graph.add_node(Node(id="z", kind="rule", path="z.md"))
        graph.add_node(Node(id="a", kind="rule", path="a.md"))
        graph.add_edge(Edge("a", "z", "references", "a.md"))
        out = tmp_path / "nested" / "graph.json"

        emit_graph(graph, out)

        doc = json.loads(out.read_text(encoding="utf-8"))
        assert doc["node-count"] == 2
        assert doc["edge-count"] == 1
        # Nodes sorted by (kind, id) -> 'a' precedes 'z'.
        assert [n["id"] for n in doc["nodes"]] == ["a", "z"]


class TestMain:
    def test_missing_inventory_returns_error(self, tmp_path: Path) -> None:
        code = main(
            [
                "--root",
                str(tmp_path),
                "--inventory",
                str(tmp_path / "absent.json"),
                "--output",
                str(tmp_path / "g.json"),
            ]
        )
        assert code == EXIT_ERROR

    def test_full_pipeline_writes_the_graph(self, tmp_path: Path) -> None:
        # Inventory paths are content-root-relative (bare 'agents/', 'rules/'),
        # so the fixture tree mirrors that under tmp_path as the scan root.
        (tmp_path / "agents").mkdir(parents=True)
        (tmp_path / "rules").mkdir(parents=True)
        (tmp_path / "agents/explorer.md").write_text(
            "honors naturalism", encoding="utf-8"
        )
        (tmp_path / "rules/naturalism.md").write_text("the rule", encoding="utf-8")
        inventory = {
            "files": [
                {"class": "agent", "path": "agents/explorer.md"},
                {"class": "docs", "path": "rules/naturalism.md"},
            ]
        }
        inv_path = tmp_path / "inventory.json"
        inv_path.write_text(json.dumps(inventory), encoding="utf-8")
        out = tmp_path / "graph.json"

        code = main(
            [
                "--root",
                str(tmp_path),
                "--inventory",
                str(inv_path),
                "--output",
                str(out),
            ]
        )

        assert code == EXIT_OK
        doc = json.loads(out.read_text(encoding="utf-8"))
        # Two real nodes plus the virtual harness events.
        assert doc["node-count"] >= 2
        # The agent's mention of 'naturalism' produced an invokes edge.
        assert any(
            e["source"] == "explorer"
            and e["target"] == "naturalism"
            and e["relation"] == RELATION_INVOKES
            for e in doc["edges"]
        )

    def test_full_pipeline_emits_hook_binding_edges(self, tmp_path: Path) -> None:
        # Regression guard: main() emits binds-to edges from the engine
        # hooks/hooks.json, keyed by bare content-root-relative hook node ids.
        # Before the content-root scan fix, the build produced zero binds-to
        # edges and every hook node looked disconnected from its event.
        (tmp_path / "hooks/lib").mkdir(parents=True)
        (tmp_path / "hooks/messages").mkdir(parents=True)
        (tmp_path / "hooks/lib/bootstrap.sh").write_text("x", encoding="utf-8")
        (tmp_path / "hooks/messages/stop.md").write_text("x", encoding="utf-8")
        command = (
            '"${CLAUDE_PLUGIN_ROOT}/src/apothem/hooks/lib/bootstrap.sh" Stop '
            '"${CLAUDE_PLUGIN_ROOT}/src/apothem/hooks/messages/stop.md"'
        )
        (tmp_path / "hooks/hooks.json").write_text(
            json.dumps({"hooks": {"Stop": [{"hooks": [{"command": command}]}]}}),
            encoding="utf-8",
        )
        inventory = {
            "files": [
                {"class": "hook", "path": "hooks/lib/bootstrap.sh"},
                {"class": "hook", "path": "hooks/messages/stop.md"},
                {"class": "hook", "path": "hooks/hooks.json"},
            ]
        }
        inv_path = tmp_path / "inventory.json"
        inv_path.write_text(json.dumps(inventory), encoding="utf-8")
        out = tmp_path / "graph.json"

        code = main(
            [
                "--root",
                str(tmp_path),
                "--inventory",
                str(inv_path),
                "--output",
                str(out),
            ]
        )

        assert code == EXIT_OK
        doc = json.loads(out.read_text(encoding="utf-8"))
        binds = {
            (e["source"], e["target"])
            for e in doc["edges"]
            if e["relation"] == RELATION_BINDS_TO
        }
        assert ("hooks/lib/bootstrap.sh", "Stop") in binds
        assert ("hooks/messages/stop.md", "Stop") in binds


class TestLoadInventory:
    def test_round_trips_payload(self, tmp_path: Path) -> None:
        path = tmp_path / "inv.json"
        payload = {"files": [{"class": "agent", "path": "a.md"}]}
        path.write_text(json.dumps(payload), encoding="utf-8")
        assert load_inventory(path) == payload
