"""Agentic building block: the Anthropic Tool Runner loop + per-run accounting.

    from sconixapp.agent import run_agent, WORKER, pick_model

    model = await pick_model(session, user_id, WORKER, ceiling=settings.agent_token_ceiling)
    result = await run_agent(
        client=anthropic_client,               # anthropic.AsyncAnthropic
        session=db_session, user_id=user_id, area="relnotes.generate",
        model=model,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        tools=[list_merged_prs, fetch_pr],     # @beta_async_tool functions
    )
    result.text          # final assistant text
    result.run.cost_usd  # what this run cost

Every call writes an ``AgentRun`` row (turns, tokens, cost, duration, status).

    # app: expose the table to Alembic autogenerate
    from sconixapp.agent import AgentRun  # noqa: F401

Needs the ``agent`` extra: ``uv add "sconixapp[agent]"`` (pulls ``anthropic``).
"""

from __future__ import annotations

import functools
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column, DateTime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Field, SQLModel, func, select

from sconixapp.logging import get_logger

log = get_logger("sconixapp.agent")

# Model policy (STACK.md / PHASE1.md): plan expensive, work mid, navigate cheap.
PLANNER = "claude-opus-5"  # one-shot planning, hard reasoning
WORKER = "claude-sonnet-5"  # the main job
NAV = "claude-haiku-4-5"  # status / navigation / cheap turns

# $ per 1M tokens: (input, output, cache_read ~= 0.1x input).
_PRICING: dict[str, tuple[float, float, float]] = {
    "claude-opus-5": (5.0, 25.0, 0.50),
    "claude-fable-5": (10.0, 50.0, 1.00),
    "claude-sonnet-5": (2.0, 10.0, 0.20),
    "claude-haiku-4-5": (1.0, 5.0, 0.10),
}
_DEFAULT_PRICING = _PRICING["claude-sonnet-5"]

# Adaptive thinking + `output_config.effort` are Opus 4.6+ / Sonnet 4.6+ / Fable 5.
# Haiku 4.5 and older reject both with a 400.
_ADAPTIVE_PREFIXES = (
    "claude-opus-5",
    "claude-opus-4-6",
    "claude-opus-4-7",
    "claude-opus-4-8",
    "claude-sonnet-5",
    "claude-sonnet-4-6",
    "claude-fable-5",
    "claude-mythos-5",
)


def _supports_adaptive(model: str) -> bool:
    return any(model.startswith(p) for p in _ADAPTIVE_PREFIXES)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def cost_usd(
    model: str, input_tokens: int, output_tokens: int, cache_read_tokens: int = 0
) -> float:
    pi, po, pc = _PRICING.get(model, _DEFAULT_PRICING)
    return round((input_tokens * pi + output_tokens * po + cache_read_tokens * pc) / 1_000_000, 6)


class AgentRun(SQLModel, table=True):
    __tablename__ = "agent_runs"

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    area: str = Field(index=True)  # "<app>.<action>"
    model: str
    status: str = "ok"  # ok | error
    turns: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    error: str | None = None
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


@dataclass
class AgentResult:
    text: str
    run: AgentRun
    messages: list[dict[str, Any]] = field(default_factory=list)


async def monthly_tokens(session: AsyncSession, user_id: str) -> int:
    """Input+output tokens this user has spent since the 1st of the month."""
    since = _utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = (
        await session.execute(
            select(
                func.coalesce(func.sum(AgentRun.input_tokens + AgentRun.output_tokens), 0)
            ).where(AgentRun.user_id == user_id, AgentRun.created_at >= since)
        )
    ).scalar_one()
    return int(total or 0)


async def pick_model(
    session: AsyncSession,
    user_id: str,
    preferred: str,
    *,
    ceiling: int,
    floor: str = NAV,
) -> str:
    """Soft-degrade: once the user is past ``ceiling`` tokens this month, drop
    to ``floor``. ``ceiling <= 0`` disables the check."""
    if ceiling and ceiling > 0 and await monthly_tokens(session, user_id) >= ceiling:
        log.info("agent.ceiling.hit", user_id=user_id, ceiling=ceiling, floor=floor)
        return floor
    return preferred


# A guard decides whether one mutating tool call may proceed. Return ``True`` to
# allow; return a string (the reason) or ``False`` to block — the model gets the
# reason back as the tool result and carries on.
Guard = Callable[[str, dict[str, Any]], Awaitable[bool | str]]


def guarded_tool(fn: Any, *, guard: Guard) -> Any:
    """Wrap an async tool function so ``guard(name, kwargs)`` runs before it does.

    Use for any tool with real side effects (restart, deploy, delete). The
    returned object is a normal ``@beta_async_tool`` — schema inference still
    sees ``fn``'s signature — so it drops straight into ``run_agent(tools=...)``.

        tools = [read_only_probe, guarded_tool(restart_app, guard=my_policy)]
    """
    from anthropic import beta_async_tool

    name = getattr(fn, "__name__", "tool")

    @functools.wraps(fn)
    async def _inner(**kwargs: Any) -> Any:
        verdict = await guard(name, kwargs)
        if verdict is not True:
            reason = verdict if isinstance(verdict, str) else "operator denied this action"
            log.info("agent.tool.blocked", tool=name, reason=reason)
            return f"BLOCKED: {reason}"
        return await fn(**kwargs)

    return beta_async_tool(_inner)


async def run_agent(
    *,
    client: Any,  # anthropic.AsyncAnthropic
    session: AsyncSession,
    user_id: str,
    area: str,
    model: str,
    system: str,
    messages: list[dict[str, Any]],
    tools: Sequence[Any],
    effort: str = "high",
    max_tokens: int = 16000,
    max_turns: int = 24,
    extra: dict[str, Any] | None = None,
) -> AgentResult:
    """Drive the Anthropic Tool Runner loop to completion, accounting every turn.

    ``tools`` are ``@beta_async_tool``-decorated functions (and/or raw server-tool
    dicts). On any exception an ``AgentRun`` row with ``status="error"`` is still
    written, then the exception re-raises.
    """
    started = time.monotonic()
    run = AgentRun(user_id=user_id, area=area, model=model)
    history: list[dict[str, Any]] = list(messages)
    text_parts: list[str] = []

    create_kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
    }
    if _supports_adaptive(model):
        create_kwargs["thinking"] = {"type": "adaptive"}
        create_kwargs["output_config"] = {"effort": effort}
    if extra:
        create_kwargs.update(extra)

    def _account(message: Any) -> None:
        run.turns += 1
        usage = getattr(message, "usage", None)
        if usage is not None:
            run.input_tokens += getattr(usage, "input_tokens", 0) or 0
            run.output_tokens += getattr(usage, "output_tokens", 0) or 0
            run.cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
        history.append({"role": "assistant", "content": message.content})
        for block in message.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(block.text)

    try:
        if tools:
            runner = client.beta.messages.tool_runner(tools=list(tools), **create_kwargs)
            async for message in runner:
                _account(message)
                if run.turns >= max_turns:
                    log.warning("agent.max_turns", area=area, turns=run.turns)
                    break
        else:
            # no tools -> a single completion, still accounted as one turn
            _account(await client.messages.create(**create_kwargs))
        run.status = "ok"
    except Exception as exc:  # noqa: BLE001 - record the failure, then re-raise
        run.status = "error"
        run.error = f"{exc.__class__.__name__}: {exc}"[:500]
        raise
    finally:
        run.cost_usd = cost_usd(model, run.input_tokens, run.output_tokens, run.cache_read_tokens)
        run.duration_ms = int((time.monotonic() - started) * 1000)
        session.add(run)
        await session.flush()
        log.info(
            "agent.run",
            area=area,
            model=model,
            status=run.status,
            turns=run.turns,
            cost_usd=run.cost_usd,
            ms=run.duration_ms,
        )

    return AgentResult(
        text="\n".join(p for p in text_parts if p).strip(),
        run=run,
        messages=history,
    )
