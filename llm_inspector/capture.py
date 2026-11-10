"""Capture every LangChain / LangGraph chat-model call made in this process.

No application code changes are needed. `install()` registers a callback
handler through LangChain's global configure hook, so every Runnable,
chain, LangGraph node and agent created afterwards (or before) picks it up.

Each process execution is written to one JSON file:
    <out_dir>/<execution_id>.json
The file is rewritten atomically after every LLM call, so a viewer can
follow a run while it is still going.
"""
from __future__ import annotations

import atexit
import json
import os
import sys
import threading
import time
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from .capture_dir import default_dir
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.tracers.context import register_configure_hook


def _ser_message(m: Any) -> dict:
    d: dict[str, Any] = {"type": getattr(m, "type", type(m).__name__), "content": m.content}
    for key in ("name", "tool_call_id", "id"):
        val = getattr(m, key, None)
        if val:
            d[key] = val
    tool_calls = getattr(m, "tool_calls", None)
    if tool_calls:
        d["tool_calls"] = tool_calls
    return d


class Recorder(BaseCallbackHandler):
    raise_error = False  # never break the host application

    def __init__(self, out_dir: Path, command: str):
        self.out_dir = out_dir
        self.lock = threading.Lock()
        self.parent: dict[str, str | None] = {}
        self.calls: dict[str, dict] = {}
        self.order: list[str] = []
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self.data: dict[str, Any] = {
            "id": f"{stamp}-{uuid.uuid4().hex[:6]}",
            "started": time.time(),
            "ended": None,
            "command": command,
            "cwd": os.getcwd(),
            "pid": os.getpid(),
            "calls": [],
        }

    # ---------- run tree tracking (to group calls per top-level invocation)
    def _link(self, run_id, parent_run_id):
        with self.lock:
            self.parent[str(run_id)] = str(parent_run_id) if parent_run_id else None

    def _root(self, run_id: str) -> str:
        for _ in range(1000):
            p = self.parent.get(run_id)
            if not p:
                break
            run_id = p
        return run_id

    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, **kw):
        self._link(run_id, parent_run_id)

    def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, **kw):
        self._link(run_id, parent_run_id)

    def on_retriever_start(self, serialized, query, *, run_id, parent_run_id=None, **kw):
        self._link(run_id, parent_run_id)

    def on_llm_start(self, serialized, prompts, *, run_id, parent_run_id=None, **kw):
        self._link(run_id, parent_run_id)

    # ---------- the calls we care about
    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None,
                            tags=None, metadata=None, **kwargs):
        self._link(run_id, parent_run_id)
        metadata = metadata or {}
        params = kwargs.get("invocation_params") or {}
        rid = str(run_id)
        call = {
            "run_id": rid,
            "root_run_id": self._root(rid),
            "started": time.time(),
            "node": metadata.get("langgraph_node"),
            "step": metadata.get("langgraph_step"),
            "provider": metadata.get("ls_provider"),
            "model": (metadata.get("ls_model_name") or params.get("model")
                      or params.get("model_name") or params.get("model_id")),
            "tags": tags or [],
            "messages": [_ser_message(m) for m in (messages[0] if messages else [])],
            "tools": params.get("tools") or params.get("functions"),
        }
        with self.lock:
            self.calls[rid] = call
            self.order.append(rid)
            self.data["calls"].append(call)

    def on_llm_end(self, response, *, run_id, **kwargs):
        call = self.calls.get(str(run_id))
        if call is None:
            return
        out: dict[str, Any] = {}
        usage: dict[str, Any] = {}
        try:
            gen = response.generations[0][0]
            msg = getattr(gen, "message", None)
            if msg is not None:
                out = _ser_message(msg)
                usage = getattr(msg, "usage_metadata", None) or {}
                rm = getattr(msg, "response_metadata", None) or {}
                call["stop_reason"] = rm.get("stop_reason") or rm.get("finish_reason")
            else:
                out = {"type": "ai", "content": getattr(gen, "text", "")}
        except Exception:
            pass
        if not usage and getattr(response, "llm_output", None):
            tu = response.llm_output.get("token_usage") or {}
            usage = {"input_tokens": tu.get("prompt_tokens"), "output_tokens": tu.get("completion_tokens")}
        details = usage.get("input_token_details") or {}
        call.update(
            output=out,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            cache_read=details.get("cache_read", 0) or 0,
            cache_creation=details.get("cache_creation", 0) or 0,
            latency=time.time() - call["started"],
        )
        self.flush()

    def on_llm_error(self, error, *, run_id, **kwargs):
        call = self.calls.get(str(run_id))
        if call is not None:
            call["error"] = f"{type(error).__name__}: {error}"
            call["latency"] = time.time() - call["started"]
            self.flush()

    # ---------- persistence
    def flush(self):
        try:
            with self.lock:
                if not self.data["calls"]:
                    return
                self.out_dir.mkdir(parents=True, exist_ok=True)
                path = self.out_dir / f"{self.data['id']}.json"
                tmp = path.with_suffix(".tmp")
                tmp.write_text(json.dumps(self.data, default=str))
                os.replace(tmp, path)
        except Exception as exc:  # pragma: no cover
            print(f"[llm_inspector] could not write run file: {exc}", file=sys.stderr)

    def close(self):
        self.data["ended"] = time.time()
        self.flush()


_installed: Recorder | None = None


def install(out_dir: str | os.PathLike | None = None, command: str | None = None) -> Recorder:
    """Register the recorder globally. Safe to call more than once."""
    global _installed
    if _installed is not None:
        return _installed
    rec = Recorder(Path(out_dir).expanduser() if out_dir else default_dir(),
                   command or " ".join(sys.argv))
    # A ContextVar whose *default* is the recorder is visible in every thread
    # and asyncio task, including worker threads that LangGraph spawns.
    var: ContextVar = ContextVar("llm_inspector_recorder", default=rec)
    register_configure_hook(var, inheritable=True)
    atexit.register(rec.close)
    _installed = rec
    return rec
