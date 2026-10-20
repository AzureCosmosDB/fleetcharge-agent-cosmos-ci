"""Validate the terminal guard directly; application runs use actual Ollama."""

import pytest
from tool_review import REQUEST, run_tool_review

from app.agent import validate_terminal_response
from app.schemas import ReviewRequest
from app.tools import ReviewTools


async def test_terminal_guard_requires_complete_acknowledged_tools(store):
    _, settings, repo = store
    tools = ReviewTools(repo, ReviewRequest.model_validate(REQUEST), settings)
    with pytest.raises(ValueError, match="complete acknowledged"):
        validate_terminal_response("{}", tools)


@pytest.mark.parametrize("terminal", ["{}", "invalid JSON", '{"recommendation":"noAction"}'])
async def test_terminal_guard_rejects_invalid_output_without_deleting_audit(store, terminal):
    _, settings, repo = store
    result, tools = await run_tool_review(repo, ReviewRequest.model_validate(REQUEST), settings)
    with pytest.raises(ValueError):
        validate_terminal_response(terminal, tools)
    assert (await repo.read("recommendations", result.audit_id, "SEA-01"))["payload"]


async def test_terminal_guard_requires_exact_persisted_payload(store):
    _, settings, repo = store
    result, tools = await run_tool_review(repo, ReviewRequest.model_validate(REQUEST), settings)
    assert validate_terminal_response(result.model_dump_json(by_alias=True), tools) == result
    altered = result.model_copy(update={"decision_hash": "0" * 64})
    with pytest.raises(ValueError, match="does not match persisted"):
        validate_terminal_response(altered.model_dump_json(by_alias=True), tools)
