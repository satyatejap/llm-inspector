# Loaded automatically by Python when this directory is on PYTHONPATH.
# Lets you capture LLM calls in ANY python process (uvicorn --reload, gunicorn
# workers, subprocesses) by setting LLM_INSPECTOR=1. See `python -m llm_inspector env`.
import os

if os.environ.get("LLM_INSPECTOR") == "1":
    try:
        from llm_inspector.capture import install
        install(os.environ.get("LLM_INSPECTOR_DIR"))
    except Exception:
        pass
