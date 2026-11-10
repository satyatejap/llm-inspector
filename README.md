# llm_inspector

Capture LangChain / LangGraph LLM calls in-process and explore them in a web viewer: every prompt, every response, and how much of each prompt was served from the provider's prompt cache.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .          # requires langchain-core
```

## Usage

```bash
python -m llm_inspector run my_agent.py          # capture, no code changes
python -m llm_inspector run -m my_pkg.main       # capture a module
python -m llm_inspector serve --open             # viewer at http://127.0.0.1:8765
eval "$(python -m llm_inspector env)"            # capture any Python process (uvicorn, gunicorn, subprocesses)
```

Runs are saved to `~/.llm_inspector/runs/` (override with `LLM_INSPECTOR_DIR` or `--out` / `--dir`). The viewer updates live while a run is in progress, and `serve` does not need langchain installed.

## Reading the viewer

- Each **column** is one LLM call; each **box** is one part of the prompt (tool schemas, system, messages), sized by tokens.
- The strip on a box's left edge: **green** = read from cache, **amber** = written to cache, **grey** = not cached.
- A dashed **"history changed here"** line marks where a prompt diverges from the previous call, so the cache can't be reused below it.
- Plain-language findings at the top flag cache misses and failed calls. Click any box for full content; use `←` `→` to step between calls, `/` to filter runs, `?` for help.
- The cost estimate uses editable per-million-token prices (placeholders by default).

## Try the demos

No API key needed; they use a fake model that simulates prompt-cache reporting.

```bash
pip install langgraph
export LLM_INSPECTOR_DIR=$PWD/.demo-runs
python -m llm_inspector run demos/chain_demo.py
python -m llm_inspector run demos/agent_demo.py
python -m llm_inspector serve --dir .demo-runs --open
```

## Layout

```text
llm_inspector/
├── __main__.py              CLI: run / serve / env
├── capture.py               global LangChain callback hook + recorder
├── capture_dir.py           default run directory
├── server.py                dependency-free HTTP server (JSON API + viewer)
├── _inject/sitecustomize.py capture any process via PYTHONPATH
└── static/index.html        viewer UI
demos/                       offline demo agents
```
