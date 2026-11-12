# SPDX-License-Identifier: MIT

"""Tests for the shared per-harness materializer helpers.

Covers ``extract_markdown_fields`` and ``build_yaml_managed_config``, the
shared helpers that keep adapter materialization behavior consolidated.
"""

from __future__ import annotations

import pytest
import yaml

from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    MarkdownProfileFields,
    build_yaml_managed_config,
    complete_managed_block,
    extract_managed_block,
    extract_markdown_fields,
    has_stray_begin,
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
        # A begin sentinel with no matching end returns the region from it to
        # the end of the text, so callers can tell such a marker is there.
        text = f"{APOTHEM_BLOCK_BEGIN}\nbody"
        assert extract_managed_block(text) == text

    def test_a_begin_without_end_keeps_its_text_and_gets_a_fresh_block(self):
        # Install and update never cut the text after a BEGIN with no END:
        # it stays, a whole block is added, and the next merge finds that
        # block by its own sentinels, so merging again changes nothing.
        mangled = f"# My notes\n{APOTHEM_BLOCK_BEGIN}\ntrapped operator text\n"
        once = merge_managed_block(mangled, "body")
        twice = merge_managed_block(once, "body")
        assert once == twice
        assert once.startswith(mangled)
        assert once.count(APOTHEM_BLOCK_BEGIN) == 2
        assert once.count(APOTHEM_BLOCK_END) == 1
        assert has_stray_begin(once)

    def test_merge_replaces_the_whole_block_and_keeps_a_stray_begin(self):
        block = wrap_managed_block("v1").rstrip("\n")
        text = f"{APOTHEM_BLOCK_BEGIN}\nmine\n\n{block}\n"
        merged = merge_managed_block(text, "v2")
        assert merged == text.replace(block, wrap_managed_block("v2").rstrip("\n"))

    def test_a_marker_counts_only_as_a_whole_line_outside_fenced_code(self):
        block = wrap_managed_block("body")
        fenced = f"```\n{APOTHEM_BLOCK_BEGIN}\nexample\n{APOTHEM_BLOCK_END}\n```\n"
        inline = f"Apothem writes `{APOTHEM_BLOCK_BEGIN}` first.\n"
        assert complete_managed_block(fenced) is None
        assert not has_stray_begin(fenced)
        assert not has_stray_begin(inline)
        assert complete_managed_block(f"{fenced}\n{block}") == block.rstrip("\n")
        assert (
            merge_managed_block(inline, "v1") == f"{inline}\n{wrap_managed_block('v1')}"
        )

    def test_merge_and_remove_leave_a_fenced_copy_above_the_block(self):
        block = wrap_managed_block("v1")
        fenced = f"```\n{block}```\n"
        text = f"{fenced}\n{block}"
        assert merge_managed_block(text, "v2").startswith(fenced)
        assert remove_managed_block(text) == fenced

    def test_an_unclosed_fence_does_not_hide_the_block(self):
        block = wrap_managed_block("v1")
        text = f"```\nnot closed\n\n{block}"
        assert complete_managed_block(text) == block.rstrip("\n")

    def test_has_stray_begin(self):
        block = wrap_managed_block("body")
        assert not has_stray_begin(f"mine\n\n{block}")
        assert not has_stray_begin("plain operator prose")
        assert has_stray_begin(f"{APOTHEM_BLOCK_BEGIN}\nmine\n")
        assert has_stray_begin(f"{APOTHEM_BLOCK_BEGIN}\nmine\n\n{block}")
        assert has_stray_begin(f"{block}\n{APOTHEM_BLOCK_BEGIN}\nmine\n")

    def test_complete_block_needs_both_sentinels(self):
        block = wrap_managed_block("body").rstrip("\n")
        assert complete_managed_block(f"mine\n{block}\nmore\n") == block
        assert complete_managed_block(f"{APOTHEM_BLOCK_BEGIN}\nbody") is None
        assert complete_managed_block("plain operator prose") is None

    def test_remove_leaves_a_block_without_its_end_sentinel(self):
        # The text below a begin sentinel with no end may be the operator's.
        text = f"Before.\n\n{APOTHEM_BLOCK_BEGIN}\nbody\nmy own line\n"
        assert remove_managed_block(text) == text

    def test_remove_keeps_frontmatter_first_file_whose_block_has_no_end(self):
        text = f"---\ndescription: x\n---\n{APOTHEM_BLOCK_BEGIN}\nbody\nmine\n"
        assert remove_managed_block(text) == text

    def test_complete_block_starts_at_the_nearest_begin_before_its_end(self):
        # A BEGIN marker left without its END above a whole block is not the
        # start of the block: the text after it is the operator's.
        block = wrap_managed_block("body").rstrip("\n")
        text = f"{APOTHEM_BLOCK_BEGIN}\nmine, below a stray marker\n{block}\n"
        assert complete_managed_block(text) == block
        assert (
            remove_managed_block(text)
            == f"{APOTHEM_BLOCK_BEGIN}\nmine, below a stray marker\n"
        )

    def test_a_stray_end_marker_above_the_block_is_skipped(self):
        block = wrap_managed_block("body").rstrip("\n")
        text = f"{APOTHEM_BLOCK_END}\nmine\n\n{block}\n"
        assert complete_managed_block(text) == block

    def test_remove_takes_out_every_whole_block(self):
        # A block pasted in twice must not leave the file Apothem's.
        block = wrap_managed_block("body")
        text = f"pre\n\n{block}\nmid\n\n{block}\npost\n"
        assert remove_managed_block(text) == "pre\n\nmid\n\npost\n"

    def test_frontmatter_merge_keeps_a_second_block_and_a_quoted_pair(self):
        # Only Apothem's own block is replaced; a marker pair the operator
        # quotes after it stays.
        fm = "---\ndescription: x\n---\n"
        first = merge_managed_block("", fm + "v1")
        quoted = f"Mine: {APOTHEM_BLOCK_BEGIN} and {APOTHEM_BLOCK_END} mark it.\n"
        merged = merge_managed_block(first + "\n" + quoted, fm + "v2")
        assert quoted in merged
        assert "v2" in merged
        assert "v1" not in merged

    def test_remove_keeps_a_quoted_marker_pair_after_the_block(self):
        # Only Apothem's block and its exact copies go: a marker pair the
        # operator quotes stays, with the text between the markers.
        block = wrap_managed_block("body")
        quoted = f"```\n{APOTHEM_BLOCK_BEGIN}\nmy example\n{APOTHEM_BLOCK_END}\n```\n"
        assert remove_managed_block(f"{block}\n{quoted}") == quoted

    def test_install_merge_keeps_a_frontmatter_block_without_end(self):
        cut = f"---\ndescription: x\n---\n{APOTHEM_BLOCK_BEGIN}\nold body\n"
        body = "---\ndescription: x\n---\nnew body"
        merged = merge_managed_block(cut, body)
        assert "old body" in merged
        assert "new body" in merged
        assert merged.count(APOTHEM_BLOCK_END) == 1
        assert merge_managed_block(merged, body) == merged

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


_BOM = "﻿"
_QUOTED = f"{APOTHEM_BLOCK_BEGIN}\nquoted example\n{APOTHEM_BLOCK_END}\n"


class TestMarkerReading:
    """A marker counts only where CommonMark reads it as a line that is not code.

    Each case puts Apothem's real block between operator text: the merge
    replaces only that block, a second merge changes nothing, and the removal
    keeps every operator line.
    """

    @pytest.mark.parametrize(
        ("before", "after"),
        [
            pytest.param(f"````markdown\n```\n{_QUOTED}```\n````\n\n", "", id="nested"),
            pytest.param(
                f"```text\n{_QUOTED}```python is how\n```\n\n", "", id="info-closer"
            ),
            pytest.param(f"~~~\n{_QUOTED}```\n~~~\n\n", "", id="other-char-closer"),
            pytest.param(
                f"- a\n  - b\n\n    ```\n    {APOTHEM_BLOCK_BEGIN}\n    ex\n"
                f"    {APOTHEM_BLOCK_END}\n    ```\n\n",
                "",
                id="fence-in-nested-list",
            ),
            pytest.param(
                f"Example:\n\n    {APOTHEM_BLOCK_BEGIN}\n    ex\n"
                f"    {APOTHEM_BLOCK_END}\n\n",
                "",
                id="indented-code",
            ),
            pytest.param(
                f"Example:\n\n\t{APOTHEM_BLOCK_BEGIN}\n\tex\n\t{APOTHEM_BLOCK_END}\n\n",
                "",
                id="tab-indented-code",
            ),
            pytest.param(
                f"```\n{_QUOTED}```\n\n", "\n```\nleft open\n", id="open-fence-below"
            ),
            pytest.param("```\nleft open\n\n", "", id="open-fence-above"),
            pytest.param(
                "```npm ci``` must pass\n\n", "```y``` too\n", id="inline-code-lines"
            ),
            pytest.param(_BOM, "", id="bom"),
            pytest.param(f"{_BOM}mine\n\n", "\nafter\n", id="bom-and-text"),
        ],
    )
    def test_only_the_real_block_is_replaced_and_removed(
        self, before: str, after: str
    ) -> None:
        text = before + wrap_managed_block("old") + after

        merged = merge_managed_block(text, "new")

        assert merged == before + wrap_managed_block("new") + after
        assert merge_managed_block(merged, "new") == merged
        assert not has_stray_begin(text)
        assert complete_managed_block(text) == wrap_managed_block("old").rstrip("\n")
        removed = remove_managed_block(text)
        assert removed.count(APOTHEM_BLOCK_BEGIN) == (before + after).count(
            APOTHEM_BLOCK_BEGIN
        )
        for line in (before + after).splitlines():
            assert line.strip(_BOM) in removed

    def test_a_bom_stays_in_front_and_goes_with_an_emptied_file(self) -> None:
        block = wrap_managed_block("body")

        assert merge_managed_block(_BOM, "body") == _BOM + block
        assert remove_managed_block(_BOM + block) == ""
        assert remove_managed_block(f"{_BOM}mine\n\n{block}") == f"{_BOM}mine\n"
        assert has_stray_begin(f"{_BOM}{APOTHEM_BLOCK_BEGIN}\nmine\n")
        assert extract_managed_block(f"{_BOM}{block}") == block.rstrip("\n")

    def test_a_fence_in_apothem_text_does_not_hide_its_end_marker(self) -> None:
        # A multi-line profile rule can leave a fence open in Apothem's own
        # text; an operator line below the block must not close it.
        body = "## Custom Rules\n\n- Wrap shell in a fence like:\n```bash\nls"
        text = merge_managed_block("KEEP top\n", body) + "```KEEP inline```\n"

        assert merge_managed_block(text, body) == text
        assert not has_stray_begin(text)
        assert remove_managed_block(text) == "KEEP top\n\n```KEEP inline```\n"

    def test_a_fence_in_apothem_text_after_an_unclosed_fence_is_one_block(
        self,
    ) -> None:
        body = "rules\n```sh\nls\n```\nmore"
        text = merge_managed_block("```\nleft open\n", body)

        assert merge_managed_block(text, body) == text
        assert text.count(APOTHEM_BLOCK_BEGIN) == 1
        assert not has_stray_begin(text)

    def test_crlf_and_trailing_whitespace_around_the_markers(self) -> None:
        text = (
            f"mine\r\n\r\n{APOTHEM_BLOCK_BEGIN}  \r\nbody\r\n{APOTHEM_BLOCK_END}\t\r\n"
        )

        assert complete_managed_block(text) is not None
        assert not has_stray_begin(text)
        assert APOTHEM_BLOCK_BEGIN not in remove_managed_block(text)

    def test_a_stray_begin_above_a_quoted_pair_and_the_block(self) -> None:
        # The quoted pair is not paired with the stray marker above it.
        block = wrap_managed_block("old")
        text = f"{APOTHEM_BLOCK_BEGIN}\nold text\n\n```\n{_QUOTED}```\n\n{block}"

        merged = merge_managed_block(text, "new")

        assert has_stray_begin(text)
        assert merged == text.replace(block, wrap_managed_block("new"))


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
            SKILLS_DIRECTORY,
        )
        from apothem.harnesses.hermes.materializer import (
            materialize_native_config as hm,
        )

        out = hm(self._profile())
        assert len(out) > 0, "hermes produced empty output"
        # The one skills key Apothem authors is skills.external_dirs, pointed at
        # the support skills directory; skills.config holds per-skill settings
        # the operator owns. A no-MCP profile renders that key and nothing else.
        assert yaml.safe_load(out) == {"skills": {"external_dirs": [SKILLS_DIRECTORY]}}

    def test_json_adapters_render_vendor_shaped_config(self):
        import json

        from apothem.harnesses.open_claw.materializer import (
            SKILLS_DIRECTORY,
        )
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
        # Apothem authors skills.load.extraDirs, pointed at the support skills
        # directory, and its path in the bootstrap-extra-files hook entry.
        # agents.defaults.skills is a NAME allowlist the operator owns, so a
        # directory path never goes there.
        assert openclaw_parsed == {
            "skills": {"load": {"extraDirs": [SKILLS_DIRECTORY]}},
            "hooks": {
                "internal": {
                    "entries": {
                        "bootstrap-extra-files": {
                            "enabled": True,
                            "paths": ["apothem/AGENTS.md"],
                        }
                    }
                }
            },
        }

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
