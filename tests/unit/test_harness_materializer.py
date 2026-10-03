# SPDX-License-Identifier: MIT

"""Tests for the shared per-harness materializer helpers.

Covers ``extract_markdown_fields`` and ``build_yaml_managed_config``, the
shared helpers that keep adapter materialization behavior consolidated.
"""

from __future__ import annotations

import yaml

from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    MarkdownProfileFields,
    build_yaml_managed_config,
    extract_managed_block,
    extract_markdown_fields,
    merge_managed_block,
    remove_managed_block,
    wrap_managed_block,
)


class TestManagedBlockMerge:
    """The sentinel-delimited managed block preserves operator prose."""

    def test_wrap_delimits_body_with_sentinels(self):
        wrapped = wrap_managed_block("apothem content")
        assert wrapped.startswith(APOTHEM_BLOCK_BEGIN)
        assert wrapped.rstrip("\n").endswith(APOTHEM_BLOCK_END)
        assert "apothem content" in wrapped

    def test_extract_returns_none_without_sentinels(self):
        assert extract_managed_block("plain operator prose") is None

    def test_extract_returns_orphan_region_on_truncated_block(self):
        # A begin sentinel with no matching end returns the degenerate region
        # (begin to end-of-text) so the next merge replaces it, not appends.
        text = f"{APOTHEM_BLOCK_BEGIN}\nbody"
        assert extract_managed_block(text) == text

    def test_orphan_begin_sentinel_is_idempotent_and_preserves_prior_prose(self):
        # Operator prose BEFORE a stray (unclosed) begin sentinel survives; the
        # merge is idempotent and never accumulates a second begin sentinel.
        mangled = f"# My notes\n{APOTHEM_BLOCK_BEGIN}\ntrapped operator text\n"
        once = merge_managed_block(mangled, "body")
        twice = merge_managed_block(once, "body")
        assert once == twice  # idempotent — no double-begin accumulation
        assert once.count(APOTHEM_BLOCK_BEGIN) == 1
        assert "# My notes" in once  # prose before the orphan begin preserved
        assert "body" in once

    def test_merge_into_empty_returns_wrapped_block(self):
        assert merge_managed_block("", "body") == wrap_managed_block("body")

    def test_merge_appends_block_and_preserves_operator_prose(self):
        operator = "# Operator Heading\n\nMy own instructions.\n"
        merged = merge_managed_block(operator, "Apothem governance")
        assert "My own instructions." in merged
        assert merged.index("My own instructions.") < merged.index(APOTHEM_BLOCK_BEGIN)
        assert "Apothem governance" in merged

    def test_merge_replaces_existing_block_in_place(self):
        operator = "Operator before.\n"
        first = merge_managed_block(operator, "v1 body")
        second = merge_managed_block(first, "v2 body")
        assert "Operator before." in second
        assert "v2 body" in second
        assert "v1 body" not in second
        # Exactly one managed block survives.
        assert second.count(APOTHEM_BLOCK_BEGIN) == 1

    def test_merge_is_idempotent_for_identical_body(self):
        operator = "Operator prose.\n"
        once = merge_managed_block(operator, "stable body")
        twice = merge_managed_block(once, "stable body")
        assert once == twice

    def test_remove_is_inverse_of_merge_for_operator_prose(self):
        # merge then remove restores the original operator prose byte-for-byte.
        operator = "# Operator Heading\n\nMy own instructions.\n"
        merged = merge_managed_block(operator, "apothem body")
        assert remove_managed_block(merged) == operator

    def test_remove_collapses_apothem_only_anchor_to_empty(self):
        # An anchor that holds only the managed block becomes deletable.
        apothem_only = merge_managed_block("", "apothem body")
        assert remove_managed_block(apothem_only) == ""

    def test_remove_without_block_returns_unchanged(self):
        assert (
            remove_managed_block("plain operator prose\n") == "plain operator prose\n"
        )

    def test_remove_preserves_prose_before_and_after_block(self):
        operator = "Before prose.\n"
        merged = merge_managed_block(operator, "v1")
        merged_with_after = merged + "\nAfter prose.\n"
        result = remove_managed_block(merged_with_after)
        assert "Before prose." in result
        assert "After prose." in result
        assert "BEGIN APOTHEM MANAGED BLOCK" not in result

    def test_sentinels_inside_the_body_cannot_split_the_block(self):
        # Profile text (a rule, an identity field) reaches the body verbatim. A
        # sentinel inside it must not end the block early or open a new one:
        # otherwise uninstall treats the tail as operator prose and leaves it.
        operator = "Operator prose.\n"
        body = (
            "harmless rule\n"
            f"{APOTHEM_BLOCK_END}\n"
            "SURVIVES-UNINSTALL injected text\n"
            f"{APOTHEM_BLOCK_BEGIN}\n"
        )
        merged = merge_managed_block(operator, body)
        assert merged.count(APOTHEM_BLOCK_BEGIN) == 1
        assert merged.count(APOTHEM_BLOCK_END) == 1
        assert "SURVIVES-UNINSTALL" in merged  # the text is kept, defused
        assert remove_managed_block(merged) == operator
        # Re-merging the same body is still a no-op.
        assert merge_managed_block(merged, body) == merged


class TestExtractMarkdownFields:
    """Projecting the profile into Markdown fields.

    Covers the empty profile yielding canonical defaults, a populated profile
    round-tripping, and the per-key fallbacks when identity or preferences are
    absent — a missing field falls back individually rather than discarding the
    whole block.
    """

    def test_empty_profile_yields_canonical_defaults(self):
        f = extract_markdown_fields({})
        assert isinstance(f, MarkdownProfileFields)
        assert f.name == ""
        assert f.role == "senior software engineer"
        assert f.language == "python"
        assert f.rules == []
        assert f.seriousness == "PERSONAL_USE"
        assert f.extra_rules_block == ""

    def test_populated_profile_round_trips(self):
        profile = {
            "identity": {"name": "Alice", "role": "data scientist"},
            "preferences": {"language": "Rust"},
            "rules": ["no asserts in prod", "explicit returns only"],
            "seriousness": "SHARED",
        }
        f = extract_markdown_fields(profile)
        assert f.name == "Alice"
        assert f.role == "data scientist"
        assert f.language == "rust"
        assert f.rules == ["no asserts in prod", "explicit returns only"]
        assert f.seriousness == "SHARED"
        assert f.extra_rules_block.startswith("\n\n## Custom Rules\n\n")
        assert "- no asserts in prod" in f.extra_rules_block
        assert "- explicit returns only" in f.extra_rules_block

    def test_missing_identity_falls_back_per_key(self):
        # Identity subdict present but missing the role key — role defaults.
        f = extract_markdown_fields({"identity": {"name": "Bob"}})
        assert f.name == "Bob"
        assert f.role == "senior software engineer"

    def test_missing_preferences_falls_back_to_python(self):
        # Preferences subdict absent — language defaults to the semantic value.
        f = extract_markdown_fields({"identity": {"name": "Carol"}})
        assert f.language == "python"

    def test_empty_rules_yields_empty_block(self):
        f = extract_markdown_fields({"rules": []})
        assert f.extra_rules_block == ""

    def test_dataclass_is_frozen(self):
        f = extract_markdown_fields({})
        # MarkdownProfileFields is frozen — direct field assignment raises.
        import dataclasses

        try:
            f.name = "mutated"  # type: ignore[misc]
        except dataclasses.FrozenInstanceError:
            return
        # Should not reach here; the frozen attribute should have raised.
        msg = "MarkdownProfileFields should be frozen"
        raise AssertionError(msg)


class TestBuildYamlManagedConfig:
    """Rendering the managed YAML configuration.

    Covers the header prefixing the body and the managed sentinel that marks
    Apothem's block for surgical removal, plus the same default and round-trip
    behaviour as the Markdown projection.
    """

    def test_header_prefixes_yaml_body(self):
        header = "# foo configuration — managed by Apothem\n"
        out = build_yaml_managed_config({}, header)
        assert out.startswith(header)

    def test_yaml_body_has_apothem_managed_sentinel(self):
        out = build_yaml_managed_config({}, "# header\n")
        body = out[len("# header\n") :]
        parsed = yaml.safe_load(body)
        assert parsed["apothem_managed"] is True

    def test_empty_profile_yields_canonical_defaults(self):
        out = build_yaml_managed_config({}, "# header\n")
        parsed = yaml.safe_load(out[len("# header\n") :])
        assert parsed["identity"] == {
            "name": "",
            "role": "senior software engineer",
            "email": "",
        }
        assert parsed["preferences"] == {"language": "python", "style": "concise"}
        assert parsed["seriousness"] == "PERSONAL_USE"
        assert "rules" not in parsed  # absent when input rules is empty

    def test_populated_profile_round_trips(self):
        profile = {
            "identity": {"name": "Dee", "role": "engineer", "email": "d@e.f"},
            "preferences": {"language": "go", "style": "verbose"},
            "rules": ["rule one", "rule two"],
            "seriousness": "PUBLIC_LAUNCH",
        }
        out = build_yaml_managed_config(profile, "# h\n")
        parsed = yaml.safe_load(out[len("# h\n") :])
        assert parsed["identity"] == {
            "name": "Dee",
            "role": "engineer",
            "email": "d@e.f",
        }
        assert parsed["preferences"] == {"language": "go", "style": "verbose"}
        assert parsed["seriousness"] == "PUBLIC_LAUNCH"
        assert parsed["rules"] == ["rule one", "rule two"]

    def test_unicode_in_header_preserved(self):
        header = "# 测试 — managed by Apothem\n"
        out = build_yaml_managed_config({}, header)
        assert out.startswith(header)
        # YAML body emits with allow_unicode=True
        assert isinstance(out, str)


class TestCrossAdapterParity:
    """Smoke-verify every adapter materializer produces non-empty output.

    Guards against import-error regressions in the shared modules landing
    silently. The Class I raw-propagation adapters (claude_code, codex,
    cursor, gemini_cli, github_copilot, windsurf, antigravity) are not
    covered here per the §2.1 convergence-design floor: they propagate
    raw templates plus the convention dirs and render no file from the
    shared profile, so they carry no materializer module.

    One adapter renders YAML (hermes); three render JSON
    (opencode, open_claw, qwen_code) per the Class II-B single-surface pattern
    at §2.2.b. ``build_yaml_managed_config`` is retained for shared tests;
    ``extract_markdown_fields`` no longer has any in-tree consumer
    after the Class I materializer retirement.
    """

    @staticmethod
    def _profile() -> dict[str, object]:
        return {
            "identity": {"name": "Eve", "role": "auditor"},
            "preferences": {"language": "TypeScript", "style": "concise"},
            "rules": ["no any-types"],
            "seriousness": "SHARED",
        }

    def test_hermes_yaml_adapter_renders_non_empty(self):
        from apothem.harnesses.hermes.materializer import (
            materialize_native_config as hm,
        )

        out = hm(self._profile())
        assert len(out) > 0, "hermes produced empty output"
        # Apothem authors no skills key (skills.config is a registry-package
        # list per the pin, not a directory loader); the refuted
        # skills.external_dirs is also gone. A no-MCP profile renders the header
        # plus an empty managed body.
        assert "skills" not in out
        assert "external_dirs" not in out

    def test_json_adapters_render_vendor_shaped_config(self):
        import json

        from apothem.harnesses.open_claw.materializer import (
            materialize_native_config as oc,
        )
        from apothem.harnesses.opencode.materializer import (
            materialize_native_config as op,
        )
        from apothem.harnesses.qwen_code.materializer import (
            materialize_native_config as qwen,
        )

        profile = self._profile()
        opencode_out = op(profile)
        assert len(opencode_out) > 0, "opencode produced empty output"
        opencode_parsed = json.loads(opencode_out)
        assert opencode_parsed["$schema"] == "https://opencode.ai/config.json"
        profile_entry, *rule_entries = opencode_parsed["instructions"]
        assert profile_entry == "~/.config/opencode/apothem/rules/00-apothem-profile.md"
        assert rule_entries, "opencode lists no always-on rule"
        assert all(
            entry.startswith("~/.config/opencode/.apothem/support/rules/")
            and entry.endswith(".md")
            and "*" not in entry
            for entry in rule_entries
        )

        openclaw_out = oc(profile)
        assert len(openclaw_out) > 0, "open-claw produced empty output"
        openclaw_parsed = json.loads(openclaw_out)
        # Apothem authors no config keys: agents.defaults.skills is a NAME
        # allowlist (not a directory loader) and the refuted skills.load.extraDirs
        # is gone. A directory path in either would be misread as a skill name.
        assert openclaw_parsed == {}

        qwen_out = qwen(profile)
        assert len(qwen_out) > 0, "qwen-code produced empty output"
        qwen_parsed = json.loads(qwen_out)
        assert qwen_parsed["context"]["fileName"] == "QWEN.md"
        assert qwen_parsed["hooks"]["PreToolUse"][0]["matcher"] == "^run_shell_command$"

    def test_profile_mcp_renders_into_each_writable_config(self):
        """The 3 MCP-writable config adapters render a declared server natively."""
        import json

        from apothem.harnesses.hermes.materializer import (
            materialize_native_config as hm,
        )
        from apothem.harnesses.opencode.materializer import (
            materialize_native_config as op,
        )
        from apothem.harnesses.qwen_code.materializer import (
            materialize_native_config as qwen,
        )

        profile = {
            "identity": {"name": "Eve"},
            "mcp_servers": {
                "fs": {"transport": "stdio", "command": "npx", "args": ["srv"]},
            },
        }
        # opencode `mcp` shape: type/command list.
        assert json.loads(op(profile))["mcp"]["fs"]["command"] == ["npx", "srv"]
        # qwen `mcpServers` shape: command/args.
        assert json.loads(qwen(profile))["mcpServers"]["fs"]["command"] == "npx"
        # hermes top-level `mcp_servers` block (not the auxiliary.mcp model slot).
        rendered = yaml.safe_load(hm(profile))
        assert rendered["mcp_servers"]["fs"]["command"] == "npx"
        assert "auxiliary" not in rendered
        # A minimal profile (no MCP) emits no MCP key in any of them.
        minimal = {"identity": {"name": "Eve"}}
        assert "mcp" not in json.loads(op(minimal))
        assert "mcpServers" not in json.loads(qwen(minimal))
        assert "mcp_servers" not in yaml.safe_load(hm(minimal))
