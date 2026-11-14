"""
The connection points (React Flow "handles") each node type has in the flow
designer, and the check every flow validator applies to an edge's handles.

An edge may name the handle it leaves from (``sourceHandle``) and the one it
enters (``targetHandle``). Leaving them out is fine — the designer then uses
the node's first handle, which is what the flow guides show. Naming a handle
the node does NOT have is not: the flow still runs (execution follows
source/target only), but the designer cannot draw the connection, so the flow
opens as unconnected boxes. Agents fell into that by inventing
``"output"`` / ``"input"`` after a validator told them handles were required.

``NODE_HANDLES`` mirrors the ``<Handle id=…>`` declarations in
``frontend/src/components/flow/*Node.js``; ``tests/test_agent_pack.py``
re-reads those files so the two cannot drift.
"""
from typing import Dict, List, Optional

# Every node is wrapped in ResizableNode, which adds the error-branch output
# (NodeErrorHandlingConfig.ERROR_HANDLE_ID).
ERROR_HANDLE = "error"

NODE_HANDLES: Dict[str, Dict[str, tuple]] = {
    "trigger":        {"source": ("bottom", "right"),         "target": ()},
    "action":         {"source": ("bottom", "right"),         "target": ("top", "left")},
    "transform":      {"source": ("bottom", "right"),         "target": ("top", "left")},
    "human_in_loop":  {"source": ("bottom", "right"),         "target": ("top", "left")},
    "wait_for_event": {"source": ("bottom", "right"),         "target": ("top", "left")},
    "response":       {"source": (),                          "target": ("top", "left")},
    "condition":      {"source": ("true", "false"),           "target": ("a",)},
    "loop":           {"source": ("loop-body", "continue"),   "target": ("input", "loop-back")},
}


def allowed_handles(node_type: str, kind: str) -> Optional[tuple]:
    """The handle ids a node type has on its ``kind`` ("source"/"target")
    side, or None for a type this table does not describe (not judged)."""
    spec = NODE_HANDLES.get(node_type)
    if spec is None:
        return None
    handles = spec[kind]
    return handles + (ERROR_HANDLE,) if kind == "source" else handles


def edge_handle_errors(edge: dict, node_types: Dict[str, str]) -> List[str]:
    """Messages for each handle on ``edge`` its node does not have.

    ``node_types`` maps node id -> node type. A missing/empty handle is never
    an error; an edge whose node is unknown is left to the connectivity checks.
    """
    errors: List[str] = []
    label = edge.get("id") or f"{edge.get('source')}->{edge.get('target')}"
    for kind, end in (("source", "source"), ("target", "target")):
        handle = edge.get(f"{kind}Handle")
        if handle in (None, ""):
            continue
        node_type = node_types.get(edge.get(end))
        allowed = allowed_handles(node_type, kind) if node_type else None
        if allowed is None or handle in allowed:
            continue
        if allowed:
            fix = (f"use one of: {', '.join(allowed)} — or leave {kind}Handle out "
                   f"to use the default")
        else:
            fix = f"a {node_type} node has no {kind} handle; remove {kind}Handle"
        errors.append(
            f"Edge {label}: {kind}Handle '{handle}' does not exist on {node_type} node "
            f"'{edge.get(end)}', so the flow designer cannot draw this connection — {fix}"
        )
    return errors
