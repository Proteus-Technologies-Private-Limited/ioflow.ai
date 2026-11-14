#!/usr/bin/env python3
"""Regenerate ioflow-plugin/agents/*.md from the agent pack (backend/agent_pack).

The pack is the one definition of IOFlow's design agents; the plugin copies are
generated so they can never drift. ``--check`` exits 1 when a copy is stale
(used by tests/test_agent_pack.py).
"""
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from agent_pack import load_pack, render_plugin_agent  # noqa: E402

PLUGIN_AGENTS = os.path.join(os.path.dirname(BACKEND), "ioflow-plugin", "agents")


def main(check: bool) -> int:
    stale = []
    for agent in load_pack()["agents"]:
        path = os.path.join(PLUGIN_AGENTS, f"{agent['name']}.md")
        wanted = render_plugin_agent(agent)
        current = open(path, encoding="utf-8").read() if os.path.exists(path) else None
        if current == wanted:
            continue
        stale.append(path)
        if not check:
            with open(path, "w", encoding="utf-8") as f:
                f.write(wanted)
    for path in stale:
        print(("stale: " if check else "wrote: ") + os.path.relpath(path, os.path.dirname(BACKEND)))
    return 1 if (check and stale) else 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv[1:]))
