"""Unit tests for agentos_cli/ui/selectors.py."""
from __future__ import annotations

import pytest

from agentos_cli.ui import selectors as S


class TestRoutes:
    def test_routes_nonempty(self):
        assert isinstance(S.ROUTES, list)
        assert len(S.ROUTES) >= 5

    def test_required_routes_present(self):
        for r in ["/", "/context", "/memory", "/adapters",
                  "/policies", "/skills", "/approvals", "/audit"]:
            assert r in S.ROUTES

    def test_routes_are_strings_starting_with_slash(self):
        for r in S.ROUTES:
            assert isinstance(r, str)
            assert r.startswith("/")


class TestTopBarConstants:
    def test_project_select_is_string(self):
        assert isinstance(S.PROJECT_SELECT, str)
        assert "Project" in S.PROJECT_SELECT
        assert "select" in S.PROJECT_SELECT

    def test_theme_toggle_starts_with_match(self):
        assert isinstance(S.THEME_TOGGLE, str)
        assert "Switch to" in S.THEME_TOGGLE


class TestApprovalButtons:
    @pytest.mark.parametrize("aid", [1, 7, 42, 99999])
    def test_approve_button_includes_id(self, aid):
        out = S.approve_button(aid)
        assert isinstance(out, str)
        assert f"#{aid}" in out
        assert "Approve" in out

    @pytest.mark.parametrize("aid", [1, 8, 123])
    def test_deny_button_includes_id(self, aid):
        out = S.deny_button(aid)
        assert f"#{aid}" in out
        assert "Deny" in out

    def test_approve_button_css(self):
        out = S.approve_button_css(5)
        assert "#5" in out
        assert "Approve" in out
        assert "tr:has" in out

    def test_deny_button_css(self):
        out = S.deny_button_css(5)
        assert "#5" in out
        assert "Deny" in out

    def test_approval_row(self):
        out = S.approval_row(123)
        assert "#123" in out
        assert out.startswith("tr:has")


class TestPageConstants:
    def test_compile_adapters_button_string(self):
        assert isinstance(S.COMPILE_ADAPTERS_BUTTON, str)
        assert "Compile now" in S.COMPILE_ADAPTERS_BUTTON
        assert "Enqueuing" in S.COMPILE_ADAPTERS_BUTTON

    def test_policy_simulate_button(self):
        assert isinstance(S.POLICY_SIMULATE_BUTTON, str)
        assert "Simulate" in S.POLICY_SIMULATE_BUTTON

    def test_policy_inputs_container(self):
        assert isinstance(S.POLICY_SIM_INPUTS_CONTAINER, str)
        assert "tool" in S.POLICY_SIM_INPUTS_CONTAINER

    def test_memory_search_input(self):
        assert isinstance(S.MEMORY_SEARCH_INPUT, str)
        assert "input" in S.MEMORY_SEARCH_INPUT
        assert "FTS" in S.MEMORY_SEARCH_INPUT

    def test_memory_semantic_button(self):
        assert isinstance(S.MEMORY_SEMANTIC_BUTTON, str)
        assert "Semantic" in S.MEMORY_SEMANTIC_BUTTON

    def test_app_shell_header(self):
        assert S.APP_SHELL_HEADER == "header"


class TestUniqueness:
    def test_distinct_ids_produce_distinct_selectors(self):
        a = S.approve_button(1)
        b = S.approve_button(2)
        assert a != b
