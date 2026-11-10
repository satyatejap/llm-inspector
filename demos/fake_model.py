"""Offline chat model that simulates Anthropic-style prompt caching (no API key needed)."""
from __future__ import annotations

import json
import time
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


def _tok(text: str) -> int:
    return max(1, len(text) // 4)


class FakeCachingChat(BaseChatModel):
    """Replies via `script(messages) -> AIMessage`; reports cache read/write like a real provider."""
    script: Any = None
    tools_spec: list = []
    _last: list = []          # token-count per block of previous prompt, with signatures
    _last_sigs: list = []

    @property
    def _llm_type(self) -> str:
        return "fake-caching"

    def bind_tools(self, tools, **kw):
        from langchain_core.utils.function_calling import convert_to_openai_tool
        return self.model_copy(update={"tools_spec": [convert_to_openai_tool(t) for t in tools]})

    def _generate(self, messages, stop=None, run_manager=None, **kw) -> ChatResult:
        sigs = [json.dumps(self.tools_spec)] if self.tools_spec else []
        sigs += [m.type + str(m.content) for m in messages]
        sizes = [_tok(s) for s in sigs]
        shared = 0
        while shared < min(len(sigs), len(self._last_sigs)) and sigs[shared] == self._last_sigs[shared]:
            shared += 1
        read = sum(sizes[:shared])
        total = sum(sizes)
        object.__setattr__(self, "_last_sigs", sigs)
        msg: AIMessage = self.script(messages)
        out = _tok(str(msg.content)) + 10
        msg.usage_metadata = {"input_tokens": total, "output_tokens": out, "total_tokens": total + out,
                              "input_token_details": {"cache_read": read, "cache_creation": total - read}}
        time.sleep(0.05)
        return ChatResult(generations=[ChatGeneration(message=msg)])
