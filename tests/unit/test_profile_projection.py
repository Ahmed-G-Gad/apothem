# SPDX-License-Identifier: MIT

"""Unit tests for the shared profile->harness projection seam.

Exercises :func:`project` (managed-block body rendering) and the MCP-renderer
transport mapping (:func:`render_mcp_standard`, :func:`render_mcp_opencode`,
:func:`mcp_servers_for`) directly. These cover the optional-identity-field and
per-transport branches that the install-path integration tests
(``test_profile_projection_fidelity.py``) do not reach.
"""

from __future__ import annotations

from typing import Any

import pytest

from apothem.lib.profile_projection import (
    ProjectedSurfaces,
    mcp_servers_for,
    project,
    render_mcp_opencode,
    render_mcp_standard,
)


def _full_profile() -> dict[str, Any]:
    """A profile exercising every optional managed-block section."""
    return {
        "identity": {
            "name": "Ada Lovelace",
            "role": "staff engineer",
            "email": "ada@example.invalid",
            "website": "https://ada.example.invalid",
            "github": "ada",
        },
        "preferences": {"language": "Python", "style": "concise"},
        "rules": ["Prefer pure functions.", "No bare excepts."],
        "seriousness": "SHARED",
        "enforcement": {"sprints": True, "learning_loop": True},
        "mcp_servers": {
            "zeta": {"transport": "stdio", "command": "z", "args": ["--a"]},
            "alpha": {"transport": "http", "url": "https://a.example.invalid"},
        },
    }


class TestProjectManagedBlock:
    """``project`` renders the managed-block body from a resolved profile."""

    def test_full_profile_renders_every_section(self) -> None:
        surfaces = project(_full_profile(), "claude-code")

        assert isinstance(surfaces, ProjectedSurfaces)
        body = surfaces.managed_block_body
        # Identity — the optional email/website/github branches the
        # integration tests do not exercise.
        assert "- **Name:** Ada Lovelace" in body
        assert "- **Email:** ada@example.invalid" in body
        assert "- **Website:** https://ada.example.invalid" in body
        assert "- **GitHub:** @ada" in body
        # Preferences — language is normalized to lowercase by the profile model.
        assert "- **Primary language:** python" in body
        assert "- **Response style:** concise" in body
        assert "- **Governance seriousness:** SHARED" in body
        # Custom rules.
        assert "## Custom Rules" in body
        assert "- Prefer pure functions." in body
        assert "- No bare excepts." in body
        # Opted-in behaviors — only the two enabled flags, by their labels.
        assert "## Opted-in Behaviors" in body
        assert "Sprint apparatus for non-trivial multi-step work" in body
        assert "Continuous-learning capture and pattern promotion" in body
        assert "Parallel multi-task execution" not in body
        # MCP server names, sorted, as instruction-context reference.
        assert "## MCP Servers" in body
        assert body.index("- alpha") < body.index("- zeta")

    def test_managed_block_carries_overwrite_warning(self) -> None:
        body = project(_full_profile(), "cursor").managed_block_body
        assert "overwritten on the next `apothem install`" in body

    def test_minimal_profile_omits_optional_sections(self) -> None:
        body = project({"identity": {"name": "Bob"}}, "zed").managed_block_body

        assert "- **Name:** Bob" in body
        assert "- **Email:**" not in body
        assert "- **Website:**" not in body
        assert "- **GitHub:**" not in body
        assert "## Custom Rules" not in body
        assert "## Opted-in Behaviors" not in body
        assert "## MCP Servers" not in body

    def test_absent_name_renders_unset_placeholder(self) -> None:
        # A falsy identity name flows through coerce_profile without a default,
        # so the managed block renders the explicit "(unset)" placeholder rather
        # than an empty value.
        body = project({"identity": {"name": ""}}, "zed").managed_block_body

        assert "- **Name:** (unset)" in body

    def test_default_off_enforcement_renders_no_behaviors_block(self) -> None:
        profile = _full_profile()
        profile["enforcement"] = {"sprints": False, "learning_loop": False}

        body = project(profile, "claude-code").managed_block_body

        assert "## Opted-in Behaviors" not in body

    def test_harness_id_does_not_change_the_body(self) -> None:
        profile = _full_profile()

        first = project(profile, "claude-code").managed_block_body
        second = project(profile, "windsurf").managed_block_body

        assert first == second


class TestRenderMcpStandard:
    """``render_mcp_standard`` maps the canonical MCP shape to ``mcpServers``."""

    def test_stdio_maps_command_args_env(self) -> None:
        out = render_mcp_standard(
            {
                "s": {
                    "transport": "stdio",
                    "command": "run",
                    "args": ["--x"],
                    "env": {"K": "V"},
                }
            }
        )
        assert out["s"] == {"command": "run", "args": ["--x"], "env": {"K": "V"}}

    def test_stdio_omits_absent_keys(self) -> None:
        # No command/args/env -> empty entry (the absent-command branch).
        assert render_mcp_standard({"s": {"transport": "stdio"}}) == {"s": {}}

    def test_http_maps_to_standard_type_and_url(self) -> None:
        # Default (standard) variant: spec ``type`` discriminator + ``url``.
        out = render_mcp_standard({"b": {"transport": "http", "url": "https://b"}})
        assert out["b"] == {"type": "http", "url": "https://b"}

    def test_streamable_http_maps_to_type_http_and_url(self) -> None:
        # streamable-http is the modern default; it renders spec ``type: http``.
        out = render_mcp_standard(
            {"s": {"transport": "streamable-http", "url": "https://s"}}
        )
        assert out["s"] == {"type": "http", "url": "https://s"}

    def test_bare_sse_is_back_compat_type_sse(self) -> None:
        # Deprecated sse is accepted for back-compat but distinguished as sse;
        # it is never a rendered default (streamable-http is preferred).
        out = render_mcp_standard({"a": {"transport": "sse", "url": "https://a"}})
        assert out["a"] == {"type": "sse", "url": "https://a"}

    def test_headers_pass_through_for_remote(self) -> None:
        out = render_mcp_standard(
            {
                "s": {
                    "transport": "streamable-http",
                    "url": "https://s",
                    "headers": {"Authorization": "Bearer ${API_TOKEN}"},
                }
            }
        )
        assert out["s"]["headers"] == {"Authorization": "Bearer ${API_TOKEN}"}

    def test_env_var_reference_passes_through_verbatim(self) -> None:
        # A ${VAR} secret reference must NOT be resolved at render time — it is
        # emitted byte-for-byte so no raw secret literal reaches native config.
        out = render_mcp_standard(
            {
                "s": {
                    "transport": "stdio",
                    "command": "run",
                    "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}"},
                }
            }
        )
        assert out["s"]["env"] == {"GITHUB_TOKEN": "${GITHUB_TOKEN}"}

    def test_gemini_variant_keeps_httpurl_for_streamable(self) -> None:
        out = render_mcp_standard(
            {"s": {"transport": "streamable-http", "url": "https://s"}},
            variant="gemini",
        )
        assert out["s"] == {"httpUrl": "https://s"}

    def test_gemini_variant_uses_url_for_http_and_sse(self) -> None:
        out = render_mcp_standard(
            {
                "a": {"transport": "sse", "url": "https://a"},
                "b": {"transport": "http", "url": "https://b"},
            },
            variant="gemini",
        )
        assert out["a"] == {"url": "https://a"}
        assert out["b"] == {"url": "https://b"}

    def test_gemini_variant_passes_headers_through_for_remote(self) -> None:
        # The gemini branch carries its own headers pass-through, distinct from
        # the standard-variant one; a ${VAR} auth token is emitted verbatim so no
        # raw secret literal reaches native config.
        out = render_mcp_standard(
            {
                "s": {
                    "transport": "streamable-http",
                    "url": "https://s",
                    "headers": {"Authorization": "Bearer ${API_TOKEN}"},
                }
            },
            variant="gemini",
        )
        assert out["s"] == {
            "httpUrl": "https://s",
            "headers": {"Authorization": "Bearer ${API_TOKEN}"},
        }

    def test_transport_defaults_to_stdio(self) -> None:
        out = render_mcp_standard({"s": {"command": "run"}})
        assert out["s"] == {"command": "run"}


class TestRenderMcpOpencode:
    """``render_mcp_opencode`` maps the canonical MCP shape to opencode's ``mcp``."""

    def test_stdio_maps_to_local_with_command_list_and_env(self) -> None:
        out = render_mcp_opencode(
            {
                "s": {
                    "transport": "stdio",
                    "command": "run",
                    "args": ["--x"],
                    "env": {"K": "V"},
                }
            }
        )
        assert out["s"] == {
            "type": "local",
            "command": ["run", "--x"],
            "enabled": True,
            "environment": {"K": "V"},
        }

    def test_stdio_without_env_omits_environment(self) -> None:
        out = render_mcp_opencode({"s": {"transport": "stdio", "command": "run"}})
        assert "environment" not in out["s"]
        assert out["s"]["command"] == ["run"]
        assert out["s"]["type"] == "local"

    def test_remote_transport_maps_to_remote(self) -> None:
        out = render_mcp_opencode({"s": {"transport": "http", "url": "https://s"}})
        assert out["s"] == {"type": "remote", "url": "https://s", "enabled": True}

    def test_remote_header_reference_becomes_an_opencode_env_reference(
        self,
    ) -> None:
        # OpenCode substitutes {env:NAME}, never ${NAME}, so the auth header
        # keeps its reference (no raw secret reaches native config) in the form
        # OpenCode expands. streamable-http is the preferred remote transport.
        out = render_mcp_opencode(
            {
                "s": {
                    "transport": "streamable-http",
                    "url": "https://s",
                    "headers": {"Authorization": "Bearer ${API_TOKEN}"},
                }
            }
        )
        assert out["s"] == {
            "type": "remote",
            "url": "https://s",
            "enabled": True,
            "headers": {"Authorization": "Bearer {env:API_TOKEN}"},
        }

    def test_local_env_references_become_env_references_but_arguments_stay(
        self,
    ) -> None:
        # An argument is left for the server, or a shell it runs, to expand.
        out = render_mcp_opencode(
            {
                "s": {
                    "transport": "stdio",
                    "command": "run",
                    "args": ["--token", "${API_KEY}"],
                    "env": {"GITHUB_TOKEN": "${GH_PAT}"},
                }
            }
        )
        assert out["s"]["command"] == ["run", "--token", "${API_KEY}"]
        assert out["s"]["environment"] == {"GITHUB_TOKEN": "{env:GH_PAT}"}

    def test_every_reference_in_a_value_and_the_url_is_rewritten(self) -> None:
        out = render_mcp_opencode(
            {
                "s": {
                    "transport": "http",
                    "url": "https://${HOST}/mcp",
                    "headers": {"X-Auth": "${USER_NAME}:${USER_PASS} (v1)"},
                }
            }
        )
        assert out["s"]["url"] == "https://{env:HOST}/mcp"
        assert out["s"]["headers"] == {"X-Auth": "{env:USER_NAME}:{env:USER_PASS} (v1)"}

    def test_values_without_a_plain_reference_are_kept(self) -> None:
        # OpenCode has no default syntax and no bare $NAME form, so those are
        # copied as written; keys are never rewritten.
        out = render_mcp_opencode(
            {
                "s": {
                    "transport": "stdio",
                    "command": "run",
                    "env": {
                        "PLAIN": "value",
                        "DEFAULTED": "${NAME:-fallback}",
                        "BARE": "$NAME",
                        "DOUBLED": "$${NAME}",
                        "${KEY}": "x",
                    },
                }
            }
        )
        assert out["s"]["environment"] == {
            "PLAIN": "value",
            "DEFAULTED": "${NAME:-fallback}",
            "BARE": "$NAME",
            "DOUBLED": "$${NAME}",
            "${KEY}": "x",
        }


class TestRenderMcpOpencodePassThrough:
    """An environment entry naming its own variable is left out for OpenCode.

    OpenCode starts a local server with its own environment and lays
    ``environment`` over it, in both release lines, so ``FOO: ${FOO}`` adds
    nothing. Written as ``{env:FOO}`` it would be pasted into the config text
    unescaped, which stops OpenCode 1 reading the file when the value holds a
    backslash, a double quote or a control character.
    """

    @staticmethod
    def _local(env: dict[str, Any]) -> dict[str, Any]:
        out = render_mcp_opencode(
            {"s": {"transport": "stdio", "command": "run", "env": env}}
        )
        return out["s"]

    def test_an_entry_naming_its_own_variable_is_left_out(self) -> None:
        server = self._local({"FOO": "${FOO}", "MODE": "fast"})
        assert server["environment"] == {"MODE": "fast"}

    def test_renamed_and_embedded_references_are_kept(self) -> None:
        server = self._local(
            {
                "TOKEN": "${FS_TOKEN}",
                "AUTH": "Bearer ${AUTH}",
                "PATHS": "${PATHS}:/opt/bin",
                "LOWER": "${lower}",
            }
        )
        assert server["environment"] == {
            "TOKEN": "{env:FS_TOKEN}",
            "AUTH": "Bearer {env:AUTH}",
            "PATHS": "{env:PATHS}:/opt/bin",
            "LOWER": "{env:lower}",
        }

    def test_other_forms_of_the_own_name_are_kept(self) -> None:
        # Only an exact ${KEY} is a pass-through; the other forms reach the
        # server as written today and keep doing so.
        env = {
            "A": "$A",
            "B": "${B:-x}",
            "C": "$${C}",
            "E-F": "${E-F}",
        }
        assert self._local(env)["environment"] == env

    def test_a_mix_in_one_server_keeps_order_and_drops_only_pass_through(
        self,
    ) -> None:
        server = self._local(
            {
                "GITHUB_TOKEN": "${GITHUB_TOKEN}",
                "API_KEY": "${OPENAI_API_KEY}",
                "HOME_DIR": "${HOME_DIR}",
                "URL": "https://${HOST}/v1",
                "LEVEL": "debug",
            }
        )
        assert list(server["environment"].items()) == [
            ("API_KEY", "{env:OPENAI_API_KEY}"),
            ("URL", "https://{env:HOST}/v1"),
            ("LEVEL", "debug"),
        ]

    def test_an_environment_left_empty_is_not_written(self) -> None:
        server = self._local({"FOO": "${FOO}", "BAR": "${BAR}"})
        assert server == {"type": "local", "command": ["run"], "enabled": True}

    def test_the_render_does_not_depend_on_whether_the_variable_is_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unset ``FOO`` no longer reaches the server as ``""``.

        Written as ``{env:FOO}``, an unset variable was substituted as the
        empty string, so the server saw ``FOO`` set to ``""``. With the entry
        left out the server inherits OpenCode's environment, where ``FOO`` is
        absent, so it stays unset. The render does not depend on the variable.
        """
        monkeypatch.delenv("FOO", raising=False)
        unset = self._local({"FOO": "${FOO}"})
        monkeypatch.setenv("FOO", "C:\\keys\\token")
        assert self._local({"FOO": "${FOO}"}) == unset
        assert "environment" not in unset

    def test_headers_and_url_are_unchanged(self) -> None:
        out = render_mcp_opencode(
            {
                "s": {
                    "transport": "streamable-http",
                    "url": "https://${API_HOST}/mcp",
                    "headers": {
                        "API_TOKEN": "${API_TOKEN}",
                        "Authorization": "Bearer ${API_TOKEN}",
                    },
                }
            }
        )
        assert out["s"] == {
            "type": "remote",
            "url": "https://{env:API_HOST}/mcp",
            "enabled": True,
            "headers": {
                "API_TOKEN": "{env:API_TOKEN}",
                "Authorization": "Bearer {env:API_TOKEN}",
            },
        }

    def test_other_harnesses_keep_the_entry(self) -> None:
        out = render_mcp_standard(
            {"s": {"transport": "stdio", "command": "run", "env": {"FOO": "${FOO}"}}}
        )
        assert out["s"]["env"] == {"FOO": "${FOO}"}


class TestMcpServersFor:
    """``mcp_servers_for`` returns a per-server copy of the MCP inventory."""

    def test_returns_top_level_independent_copies(self) -> None:
        profile = {"mcp_servers": {"s": {"transport": "stdio", "command": "run"}}}

        out = mcp_servers_for(profile)
        out["s"]["command"] = "MUTATED"

        # Mutating the returned per-server dict must not reach the source.
        assert profile["mcp_servers"]["s"]["command"] == "run"

    def test_empty_when_no_servers(self) -> None:
        assert mcp_servers_for({}) == {}
