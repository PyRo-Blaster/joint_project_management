"""Prove every answer in docs/mcp/evaluation.xml from the MCP tools alone.

Each test takes the route an agent would: search, read the item, read its
history. If the seed or a tool changes so that an answer no longer follows,
this fails before a model is ever asked the question.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from app.evaluation.seed import PEOPLE, ROWS, seed_evaluation
from app.services.errors import ConflictError

EVALUATION = Path(__file__).resolve().parents[3] / "docs" / "mcp" / "evaluation.xml"
ENTRY = re.compile(r"^#(\d+) ", re.MULTILINE)


def _answers() -> list[str]:
    root = ET.parse(EVALUATION).getroot()
    return [pair.findtext("answer").strip() for pair in root.iter("qa_pair")]


@pytest.fixture
def seeded(cli_db, program, admin, vocab):
    seed_evaluation(cli_db, actor=admin, program=program)


def _entries(text: str) -> list[int]:
    return [int(number) for number in ENTRY.findall(text)]


def _sec_hplc(mcp) -> int:
    (entry,) = _entries(mcp.text("cmc_search_items", q="SEC-HPLC"))
    return entry


def test_the_file_has_ten_questions():
    assert len(_answers()) == 10


def test_the_dataset_loads_only_into_an_empty_programme(seeded, cli_db, program, admin):
    with pytest.raises(ConflictError):
        seed_evaluation(cli_db, actor=admin, program=program)


def test_answers_follow_from_the_tools(seeded, mcp_client):
    mcp = mcp_client
    derived = []

    # 1. Which item does a requalification note about the SEC-HPLC column belong on?
    derived.append(f"#{_sec_hplc(mcp)}")

    # 2. The root-cause update's date, from the item's timeline.
    updates = mcp.text("cmc_list_updates", entry_no=_sec_hplc(mcp), limit=20)
    (root_cause,) = [line for line in updates.splitlines() if "Root cause" in line]
    derived.append(re.search(r"\d{4}-\d{2}-\d{2}", root_cause).group(0))

    # 3. Earliest-due overdue GenSci P1, and its assignee.
    overdue = mcp.text(
        "cmc_search_items",
        owner_org=["gensci"],
        priority=["p1"],
        status=["open", "in_progress", "blocked", "on_hold"],
        due_before="2026-09-24",
        sort="due_on",
    )
    first = _entries(overdue)[0]
    detail = mcp.text("cmc_get_item", entry_no=first)
    derived.append(re.search(r"Assignee: (.+)$", detail, re.MULTILINE).group(1).strip())

    # 4. Current status after it was blocked.
    history = mcp.text("cmc_get_item_history", entry_no=_sec_hplc(mcp))
    assert "Blocked" in history or "blocked" in history
    detail = mcp.text("cmc_get_item", entry_no=_sec_hplc(mcp))
    state = re.search(r"State: (.+)$", detail, re.MULTILINE).group(1)
    assert state.startswith("In progress")
    derived.append("in_progress")

    # 5. Unfinished P1 actions due on or before 2026-06-30.
    p1 = mcp.text(
        "cmc_search_items",
        priority=["p1"],
        status=["open", "in_progress", "blocked", "on_hold"],
        due_before="2026-06-30",
    )
    derived.append(str(len(_entries(p1))))

    # 6. Who moved it from blocked to in progress: the history line names them.
    (moved,) = [
        line
        for line in history.splitlines()
        if "in progress" in line.lower() and "blocked" in line.lower()
    ]
    derived.append(re.search(r"\d{2}:\d{2}(?: \[agent\] via '[^']+')? (.+?):", moved).group(1))

    # 7. Actions in the Gen2 group.
    gen2 = mcp.text("cmc_search_items", group=["Gen2 (Process 2.0) CMC"], kind="action")
    derived.append(str(len(_entries(gen2))))

    # 8. The token an agent wrote the weekly digest through.
    (digest,) = [line for line in history.splitlines() if "Weekly digest" in line]
    derived.append(re.search(r"\[agent\] via '([^']+)'", digest).group(1))

    # 9. Whether "Formulation" is a group.
    refusal = mcp.error("cmc_search_items", group=["Formulation"])
    assert "is not a known term" in refusal
    derived.append(str("Formulation" in mcp.text("cmc_list_vocabulary")))

    # 10. Due date of the Yarrow in-progress action that is not P1.
    yarrow = mcp.text(
        "cmc_search_items", owner_org=["yarrow"], status=["in_progress"], priority=["p2", "p3"]
    )
    (only,) = _entries(yarrow)
    detail = mcp.text("cmc_get_item", entry_no=only)
    derived.append(re.search(r"Due: (\d{4}-\d{2}-\d{2})", detail).group(1))

    assert derived == _answers()


def test_the_dataset_is_fictional():
    # Every person is on the reserved example domain, so no real address ships.
    assert all(email.endswith("@eval.example") for _, email, _ in PEOPLE)
    assert len(ROWS) == 12


def test_seed_eval_cli_loads_once(cli_db, admin, program, vocab):
    from typer.testing import CliRunner

    from app.cli import cli

    runner = CliRunner()
    first = runner.invoke(cli, ["seed-eval"])
    assert first.exit_code == 0, first.output
    assert "seeded 12 evaluation items" in first.output
    second = runner.invoke(cli, ["seed-eval"])
    assert second.exit_code != 0
    assert "only into an empty programme" in second.output
