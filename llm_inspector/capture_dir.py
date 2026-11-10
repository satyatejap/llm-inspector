"""Default run directory (kept separate so the viewer needs no langchain)."""
import os
from pathlib import Path


def default_dir() -> Path:
    env = os.environ.get("LLM_INSPECTOR_DIR")
    return Path(env).expanduser() if env else Path.home() / ".llm_inspector" / "runs"
