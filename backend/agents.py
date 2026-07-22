"""Agent orchestration: LLM abstraction + orchestrator + SSE event bus."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

from emergentintegrations.llm.chat import LlmChat, StreamDone, TextDelta, UserMessage

from config import AGENT_PROMPTS, AGENT_TYPES, TIERS
from deps import db, new_id, now_utc

EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]

MODEL_MAP = {
    "openai": ("openai", "gpt-5.2"),
    "gemini": ("gemini", "gemini-3-flash-preview"),
}


class RunBus:
    """Per-run pub/sub for SSE. Buffers past events so late subscribers can catch up."""

    _buses: dict[str, "RunBus"] = {}

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.subscribers: list[asyncio.Queue] = []
        self.events: list[dict] = []
        self.closed = False

    @classmethod
    def get(cls, run_id: str) -> "RunBus":
        b = cls._buses.get(run_id)
        if not b:
            b = cls(run_id)
            cls._buses[run_id] = b
        return b

    async def publish(self, event: dict) -> None:
        self.events.append(event)
        for q in list(self.subscribers):
            await q.put(event)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        for e in self.events:
            q.put_nowait(e)
        self.subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self.subscribers:
            self.subscribers.remove(q)

    async def close(self) -> None:
        self.closed = True
        for q in list(self.subscribers):
            await q.put({"event": "end"})


async def stream_llm(provider: str, session_id: str, system: str, user_text: str) -> AsyncIterator[str]:
    prov, model = MODEL_MAP.get(provider, MODEL_MAP["gemini"])
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=system,
    ).with_model(prov, model)
    try:
        async for ev in chat.stream_message(UserMessage(text=user_text)):
            if isinstance(ev, TextDelta):
                yield ev.content
            elif isinstance(ev, StreamDone):
                break
    except Exception as e:
        yield f"\n[stream_error] {type(e).__name__}: {str(e)[:200]}"


def build_user_prompt(agent_type: str, base_input: str, prior_outputs: dict[str, str]) -> str:
    parts = [f"# INPUT\n{base_input[:20000]}"]
    if prior_outputs:
        parts.append("\n# PRIOR AGENT OUTPUTS")
        for k, v in prior_outputs.items():
            parts.append(f"\n## {k}\n{v[:8000]}")
    parts.append(
        f"\n\n# TASK\nAs {agent_type}, produce your output in JSON as specified. "
        "Wrap the final JSON in a ```json code block. Keep prose commentary before the JSON to under 2 sentences."
    )
    return "\n".join(parts)


async def run_agent(
    run_id: str, agent_id: str, agent_type: str, provider: str,
    base_input: str, prior_outputs: dict[str, str], tier: dict,
) -> str:
    bus = RunBus.get(run_id)
    system = AGENT_PROMPTS.get(agent_type, "You are a helpful analytic agent. Return concise JSON.")
    user_text = build_user_prompt(agent_type, base_input, prior_outputs)

    await bus.publish({"event": "agent_status", "agent_id": agent_id, "status": "running", "ts": now_utc().isoformat()})
    await db.agent_traces.update_one(
        {"agent_id": agent_id},
        {"$set": {"status": "running", "started_at": now_utc().isoformat()}},
    )

    output_parts: list[str] = []
    retries_allowed = tier.get("retries", 1)
    timeout = tier.get("agent_timeout_sec", 30)

    attempt = 0
    while attempt <= retries_allowed:
        try:
            async def _stream() -> None:
                async for chunk in stream_llm(provider, f"{run_id}:{agent_id}:{attempt}", system, user_text):
                    output_parts.append(chunk)
                    await bus.publish({"event": "agent_token", "agent_id": agent_id, "delta": chunk})

            await asyncio.wait_for(_stream(), timeout=timeout)
            break
        except asyncio.TimeoutError:
            attempt += 1
            if attempt > retries_allowed:
                await bus.publish({"event": "agent_status", "agent_id": agent_id, "status": "timeout"})
                await db.agent_traces.update_one({"agent_id": agent_id}, {"$set": {"status": "timeout", "ended_at": now_utc().isoformat()}})
                return ""
            await bus.publish({"event": "agent_status", "agent_id": agent_id, "status": "retrying", "attempt": attempt})
            await asyncio.sleep(2 ** attempt)
            output_parts.clear()
        except Exception as e:
            attempt += 1
            if attempt > retries_allowed:
                msg = f"[failed] {type(e).__name__}: {str(e)[:200]}"
                output_parts.append(msg)
                await bus.publish({"event": "agent_status", "agent_id": agent_id, "status": "failed", "error": msg})
                await db.agent_traces.update_one({"agent_id": agent_id}, {"$set": {"status": "failed", "ended_at": now_utc().isoformat(), "output": "".join(output_parts)}})
                return "".join(output_parts)
            await bus.publish({"event": "agent_status", "agent_id": agent_id, "status": "retrying", "attempt": attempt})
            await asyncio.sleep(2 ** attempt)
            output_parts.clear()

    final_output = "".join(output_parts)
    await bus.publish({"event": "agent_status", "agent_id": agent_id, "status": "completed"})
    await db.agent_traces.update_one(
        {"agent_id": agent_id},
        {"$set": {"status": "completed", "ended_at": now_utc().isoformat(), "output": final_output}},
    )
    return final_output


async def orchestrate_run(run_id: str) -> None:
    run = await db.runs.find_one({"run_id": run_id}, {"_id": 0})
    if not run:
        return
    bus = RunBus.get(run_id)
    tier = TIERS[run["tier_at_run_time"]]
    agent_configs: list[dict] = run["agents"]
    base_input = run["input_text"]
    prior_outputs: dict[str, str] = {}

    await db.runs.update_one({"run_id": run_id}, {"$set": {"status": "streaming", "started_at": now_utc().isoformat()}})
    await bus.publish({"event": "run_status", "status": "streaming"})

    try:
        run_timeout = tier.get("run_timeout_sec", 600)

        async def _pipeline() -> None:
            for ac in agent_configs:
                output = await run_agent(
                    run_id, ac["agent_id"], ac["type"], ac["provider"],
                    base_input, prior_outputs, tier,
                )
                prior_outputs[ac["type"]] = output

        await asyncio.wait_for(_pipeline(), timeout=run_timeout)

        final = prior_outputs.get("Synthesizer") or (list(prior_outputs.values())[-1] if prior_outputs else "")
        await db.runs.update_one(
            {"run_id": run_id},
            {"$set": {
                "status": "completed",
                "ended_at": now_utc().isoformat(),
                "final_output": final,
                "agent_outputs": prior_outputs,
            }},
        )
        await bus.publish({"event": "run_status", "status": "completed"})
    except asyncio.TimeoutError:
        await db.runs.update_one({"run_id": run_id}, {"$set": {"status": "failed", "ended_at": now_utc().isoformat(), "error": "run_timeout"}})
        await bus.publish({"event": "run_status", "status": "failed", "error": "run_timeout"})
    except Exception as e:
        await db.runs.update_one({"run_id": run_id}, {"$set": {"status": "failed", "ended_at": now_utc().isoformat(), "error": str(e)[:400]}})
        await bus.publish({"event": "run_status", "status": "failed", "error": str(e)[:400]})
    finally:
        await bus.close()
