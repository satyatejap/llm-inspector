"""CLI:
    python -m llm_inspector run [--out DIR] script.py [args...]
    python -m llm_inspector run [--out DIR] -m some.module [args...]
    python -m llm_inspector serve [--dir DIR] [--port 8765] [--open]
    python -m llm_inspector env            # print env vars to capture any python process
"""
from __future__ import annotations

import argparse
import os
import runpy
import sys
from pathlib import Path



def _run(argv: list[str]) -> None:
    from .capture import install
    out = None
    i = 0
    while i < len(argv) and argv[i].startswith("-") and argv[i] != "-m":
        if argv[i] == "--out" and i + 1 < len(argv):
            out, i = argv[i + 1], i + 2
        else:
            sys.exit(f"unknown option {argv[i]!r}")
    if i >= len(argv):
        sys.exit(__doc__)
    module = None
    if argv[i] == "-m":
        module, rest = argv[i + 1], argv[i + 2:]
        target = module
    else:
        target, rest = argv[i], argv[i + 1:]
    rec = install(out, command=" ".join(argv[i:]))
    print(f"[llm_inspector] capturing LLM calls -> {rec.out_dir}", file=sys.stderr)
    sys.argv = [target] + rest
    if module:
        runpy.run_module(module, run_name="__main__", alter_sys=True)
    else:
        sys.path.insert(0, os.path.dirname(os.path.abspath(target)))
        runpy.run_path(target, run_name="__main__")


def main() -> None:
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "run":
        _run(rest)
    elif cmd == "serve":
        from .capture_dir import default_dir
        from .server import serve
        p = argparse.ArgumentParser(prog="llm_inspector serve")
        p.add_argument("--dir", default=str(default_dir()))
        p.add_argument("--host", default="127.0.0.1")
        p.add_argument("--port", type=int, default=8765)
        p.add_argument("--open", action="store_true", help="open the viewer in a browser")
        a = p.parse_args(rest)
        serve(Path(a.dir).expanduser(), a.host, a.port, open_browser=a.open)
    elif cmd == "env":
        pkg_parent = str(Path(__file__).resolve().parent.parent)
        inject = str(Path(__file__).resolve().parent / "_inject")
        print(f'export PYTHONPATH="{inject}:{pkg_parent}:$PYTHONPATH"')
        print("export LLM_INSPECTOR=1")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
