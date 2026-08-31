"""No-network tests for sconixapp.agent (pricing math + run accounting via a fake client)."""

from __future__ import annotations

import pytest
from sqlmodel import SQLModel

from sconixapp.agent import (
    NAV,
    PLANNER,
    WORKER,
    AgentRun,
    cost_usd,
    monthly_tokens,
    pick_model,
    run_agent,
)
from sconixapp.db import dispose_engine, get_session, init_engine


def test_model_constants() -> None:
    assert (PLANNER, WORKER, NAV) == (
        "claude-opus-5",
        "claude-sonnet-5",
        "claude-haiku-4-5",
    )


def test_cost_math() -> None:
    # 1M input + 1M output on sonnet-5 => $2 + $10
    assert cost_usd("claude-sonnet-5", 1_000_000, 1_000_000) == 12.0
    # cache reads priced at ~0.1x input
    assert cost_usd("claude-opus-5", 0, 0, 1_000_000) == 0.5
    # unknown model falls back to sonnet pricing
    assert cost_usd("mystery", 1_000_000, 0) == 2.0


def test_agent_run_table_registered() -> None:
    assert "agent_runs" in SQLModel.metadata.tables


# --- integration-lite: real sqlite session, fake Anthropic client -----------


class _Block:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _Usage:
    def __init__(self, i: int, o: int) -> None:
        self.input_tokens = i
        self.output_tokens = o
        self.cache_read_input_tokens = 0


class _Msg:
    stop_reason = "end_turn"

    def __init__(self, text: str, i: int, o: int) -> None:
        self.content = [_Block(text)]
        self.usage = _Usage(i, o)


class _Runner:
    def __init__(self, msgs: list[_Msg]) -> None:
        self._msgs = msgs

    def __aiter__(self):
        self._it = iter(self._msgs)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration from None


class _Messages:
    def __init__(self, msgs: list[_Msg]) -> None:
        self._msgs = msgs
        self.calls: list[dict] = []

    def tool_runner(self, **kwargs):
        self.calls.append(kwargs)
        return _Runner(self._msgs)

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._msgs[0]


class _Beta:
    def __init__(self, msgs: list[_Msg]) -> None:
        self.messages = _Messages(msgs)


class _FakeClient:
    def __init__(self, msgs: list[_Msg]) -> None:
        self.beta = _Beta(msgs)
        self.messages = self.beta.messages  # no-tools path uses client.messages.create


@pytest.fixture()
async def session():
    init_engine("sqlite+aiosqlite:///:memory:")
    from sconixapp.db import get_engine

    async with get_engine().begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    agen = get_session()
    s = await agen.__anext__()
    try:
        yield s
    finally:
        await s.rollback()
        await dispose_engine()


async def test_run_agent_records_a_run(session) -> None:
    client = _FakeClient([_Msg("here are your notes", 1200, 340)])
    result = await run_agent(
        client=client,
        session=session,
        user_id="u1",
        area="relnotes.generate",
        model=WORKER,
        system="be terse",
        messages=[{"role": "user", "content": "go"}],
        tools=[],
    )
    assert result.text == "here are your notes"
    assert result.run.turns == 1
    assert result.run.input_tokens == 1200
    assert result.run.output_tokens == 340
    assert result.run.status == "ok"
    assert result.run.cost_usd == cost_usd(WORKER, 1200, 340, 0)
    assert result.run.id is not None  # flushed
    # the runner was asked for adaptive thinking + effort
    call = client.beta.messages.calls[0]
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"] == {"effort": "high"}


async def test_run_agent_with_tools_uses_the_runner(session) -> None:
    client = _FakeClient([_Msg("a", 10, 5), _Msg("b", 20, 7)])

    def _noop() -> str:
        """A tool."""
        return "ok"

    result = await run_agent(
        client=client,
        session=session,
        user_id="u3",
        area="x.y",
        model=NAV,
        system="s",
        messages=[{"role": "user", "content": "go"}],
        tools=[_noop],
    )
    assert result.run.turns == 2
    assert result.run.input_tokens == 30
    assert "tools" in client.beta.messages.calls[0]


async def test_pick_model_soft_degrades_past_ceiling(session) -> None:
    assert await pick_model(session, "u2", WORKER, ceiling=0) == WORKER  # disabled
    assert await pick_model(session, "u2", WORKER, ceiling=1000) == WORKER  # nothing spent

    session.add(
        AgentRun(user_id="u2", area="x.y", model=WORKER, input_tokens=900, output_tokens=200)
    )
    await session.flush()
    assert await monthly_tokens(session, "u2") == 1100
    assert await pick_model(session, "u2", WORKER, ceiling=1000) == NAV
