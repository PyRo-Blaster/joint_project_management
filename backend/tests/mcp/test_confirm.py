"""Stateless confirm tokens: they confirm exactly what was previewed, by whom, briefly."""

from datetime import timedelta

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from app.mcp.confirm import issue, verify
from app.models.base import utcnow

REQUEST = {"entry_no": 42, "set": {"due_on": "2026-11-15"}}


def test_a_token_verifies_for_the_same_request_and_caller():
    issued = issue(tool="cmc_update_item", caller_token_id=7, request=REQUEST)
    assert issued.token.startswith("ct_")
    when = verify(issued.token, tool="cmc_update_item", caller_token_id=7, request=REQUEST)
    assert abs((when - utcnow()).total_seconds()) < 5


def test_changing_any_argument_breaks_it():
    issued = issue(tool="cmc_update_item", caller_token_id=7, request=REQUEST)
    other = {"entry_no": 42, "set": {"due_on": "2026-12-31"}}
    with pytest.raises(ToolError) as caught:
        verify(issued.token, tool="cmc_update_item", caller_token_id=7, request=other)
    assert "does not match" in str(caught.value)


def test_another_callers_token_cannot_confirm_it():
    issued = issue(tool="cmc_update_item", caller_token_id=7, request=REQUEST)
    with pytest.raises(ToolError):
        verify(issued.token, tool="cmc_update_item", caller_token_id=8, request=REQUEST)


def test_it_is_bound_to_the_tool():
    issued = issue(tool="cmc_update_item", caller_token_id=7, request=REQUEST)
    with pytest.raises(ToolError):
        verify(issued.token, tool="cmc_set_status", caller_token_id=7, request=REQUEST)


def test_it_expires():
    issued = issue(
        tool="cmc_update_item",
        caller_token_id=7,
        request=REQUEST,
        now=utcnow() - timedelta(minutes=11),
    )
    with pytest.raises(ToolError) as caught:
        verify(issued.token, tool="cmc_update_item", caller_token_id=7, request=REQUEST)
    assert "expired" in str(caught.value)


def test_a_forged_expiry_is_caught_by_the_signature():
    issued = issue(tool="cmc_update_item", caller_token_id=7, request=REQUEST)
    envelope, signature = issued.token[3:].rsplit(".", 1)
    forged = "ct_" + envelope[:-2] + ("AA" if envelope[-2:] != "AA" else "BB") + "." + signature
    with pytest.raises(ToolError):
        verify(forged, tool="cmc_update_item", caller_token_id=7, request=REQUEST)


def test_garbage_is_refused_clearly():
    with pytest.raises(ToolError) as caught:
        verify("not-a-token", tool="cmc_update_item", caller_token_id=7, request=REQUEST)
    assert "confirm token" in str(caught.value)
