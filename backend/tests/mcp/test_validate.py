"""Bad values get an error that names the valid ones, per spec section 8."""

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from app.mcp.validate import check_priority, check_status, check_term


def test_a_valid_status_passes_through_normalised():
    assert check_status("In_Progress") == "in_progress"


def test_a_synonym_is_suggested():
    with pytest.raises(ToolError) as caught:
        check_status("done")
    message = str(caught.value)
    assert '"done" is not a status' in message
    assert "Valid: open, in_progress, blocked, on_hold, completed, cancelled" in message
    assert 'Did you mean "completed"?' in message


def test_a_near_miss_is_suggested():
    with pytest.raises(ToolError) as caught:
        check_status("blockd")
    assert 'Did you mean "blocked"?' in str(caught.value)


def test_no_suggestion_when_nothing_is_close():
    with pytest.raises(ToolError) as caught:
        check_priority("urgent-ish")
    assert "Did you mean" not in str(caught.value)
    assert "Valid: p1, p2, p3" in str(caught.value)


def test_a_term_matches_case_insensitively(db, program, vocab):
    assert check_term(db, program.id, "group", "general issues") == "General Issues"


def test_an_unknown_group_lists_the_active_ones(db, program, vocab):
    with pytest.raises(ToolError) as caught:
        check_term(db, program.id, "group", "Gen2 CMC", active_only=True)
    message = str(caught.value)
    assert 'Group "Gen2 CMC" is not an active term' in message
    assert "General Issues" in message
    assert "An admin adds terms in the web UI" in message
