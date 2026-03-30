import json
import html
import re
import uuid
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

# ── Signal category tagging from transcript intelligence layer ──
try:
    from utils.transcript_live import (
        SIGNAL_COLORS,
        OUTLOOK_KEYWORDS,
        RISK_KEYWORDS,
        OPPORTUNITY_KEYWORDS,
        INVESTMENT_KEYWORDS,
        PRODUCT_SHIFT_KEYWORDS,
        USER_BEHAVIOR_KEYWORDS,
        MONETIZATION_KEYWORDS,
        STRATEGIC_DIRECTION_KEYWORDS,
        BROADCASTER_THREAT_KEYWORDS,
    )
except ImportError:
    SIGNAL_COLORS = {}
    OUTLOOK_KEYWORDS = RISK_KEYWORDS = OPPORTUNITY_KEYWORDS = []
    INVESTMENT_KEYWORDS = PRODUCT_SHIFT_KEYWORDS = USER_BEHAVIOR_KEYWORDS = []
    MONETIZATION_KEYWORDS = STRATEGIC_DIRECTION_KEYWORDS = BROADCASTER_THREAT_KEYWORDS = []

_SIGNAL_KEYWORD_MAP = {
    "Outlook": OUTLOOK_KEYWORDS,
    "Risks": RISK_KEYWORDS,
    "Opportunities": OPPORTUNITY_KEYWORDS,
    "Investment": INVESTMENT_KEYWORDS,
    "Product Shifts": PRODUCT_SHIFT_KEYWORDS,
    "User Behavior": USER_BEHAVIOR_KEYWORDS,
    "Monetization": MONETIZATION_KEYWORDS,
    "Strategic Direction": STRATEGIC_DIRECTION_KEYWORDS,
    "Broadcaster Threats": BROADCASTER_THREAT_KEYWORDS,
}


def match_signal_category(text: str) -> tuple[str, str]:
    """Match node text against signal keyword maps. Returns (category, border_color) or ("","")."""
    text_lower = text.lower()
    best_cat = ""
    best_score = 0
    for cat, keywords in _SIGNAL_KEYWORD_MAP.items():
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        if score > best_score:
            best_score = score
            best_cat = cat
    if best_score >= 1 and best_cat in SIGNAL_COLORS:
        return best_cat, SIGNAL_COLORS[best_cat]["border"]
    return "", ""


# ── Depth mode definitions ──
DEPTH_MODES = {
    "focused": {
        "label": "3-4 nodes",
        "icon": "",
        "desc": "",
        "prompt_insert": (
            "MODE: FOCUSED (3-4 nodes). Build a tight CAUSAL CHAIN. "
            "Each step must logically follow the previous one. "
            "Use exactly: [STEP 1] → [STEP 2] → [STEP 3] → [CONCLUSION]. "
            "No branches. Linear reasoning only. Every link should feel inevitable."
        ),
    },
    "balanced": {
        "label": "5-7 nodes",
        "icon": "",
        "desc": "",
        "prompt_insert": (
            "MODE: BALANCED (5-7 nodes). Build a BRANCHING TREE. "
            "Start with 2-3 sequential steps, then FORK into at least one [BRANCH]. "
            "One branch should loop back to challenge an earlier step. "
            "Include ONE surprising lateral connection the user would not expect. "
            "Use: [STEP 1] → [STEP 2] → [BRANCH A] alternative → [STEP 3] → [BRANCH B] risk → [CONCLUSION]."
        ),
    },
    "deep": {
        "label": "8-12 nodes",
        "icon": "",
        "desc": "",
        "prompt_insert": (
            "MODE: DEEP WEB (8-12 nodes). Build a complex WEB of reasoning. "
            "Include SECOND-ORDER effects (what happens because of what happens). "
            "Include at least 2 [BRANCH] nodes that are CONTRARIAN — ideas that push back "
            "on the main thesis or reveal a hidden risk. "
            "Create CROSS-CONNECTIONS between branches (mention earlier steps by name). "
            "Include an [OBSERVATION] that connects two seemingly unrelated data points. "
            "The map should feel like a network, not a line. "
            "Use all marker types: STEP, BRANCH, OBSERVATION, INFERENCE, ANALYSIS, RISK, CONCLUSION."
        ),
    },
}


def _empty_map() -> dict:
    return {"nodes": {}, "edges": [], "root_ids": [], "version": 1}


def _get_map() -> dict:
    if "thought_map" not in st.session_state:
        st.session_state["thought_map"] = _empty_map()
    return st.session_state["thought_map"]


def get_depth_prompt_insert() -> str:
    """Return the prompt insert for the current depth mode."""
    mode = st.session_state.get("thought_map_depth", "balanced")
    return DEPTH_MODES.get(mode, DEPTH_MODES["balanced"])["prompt_insert"]


def render_depth_selector():
    """Render depth selector as clean pill buttons with clear selected state."""
    current = st.session_state.get("thought_map_depth", "balanced")

    # CSS for the depth pills
    st.markdown("""<style>
    .depth-pills { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 8px 0 16px 0; }
    .depth-pills div[data-testid="stButton"] > button {
        border-radius: 999px !important;
        border: 1px solid #d9dde5 !important;
        background: rgba(238,240,244,0.15) !important;
        background-image: none !important;
        color: #CBD5E1 !important;
        font-size: 0.9rem !important;
        font-weight: 500 !important;
        padding: 10px 20px !important;
        height: 44px !important;
        transition: all 200ms ease !important;
    }
    .depth-pills div[data-testid="stButton"] > button:hover {
        border-color: #ff5b1f !important;
        background: rgba(255,91,31,0.08) !important;
        background-image: none !important;
        color: #ff8c42 !important;
    }
    .depth-pills div[data-testid="stButton"] > button:active,
    .depth-pills div[data-testid="stButton"] > button:focus,
    .depth-pills div[data-testid="stButton"] > button:focus-visible {
        background-image: none !important;
        outline: none !important;
        box-shadow: none !important;
    }
    .depth-pills div[data-testid="stButton"] > button[kind="primary"] {
        border-color: #ff5b1f !important;
        background: rgba(255,91,31,0.15) !important;
        background-image: none !important;
        color: #ff8c42 !important;
        font-weight: 700 !important;
        box-shadow: 0 0 12px rgba(255,91,31,0.12) !important;
    }
    </style>""", unsafe_allow_html=True)

    st.markdown('<div class="depth-pills">', unsafe_allow_html=True)
    cols = st.columns(len(DEPTH_MODES))
    for i, (key, mode) in enumerate(DEPTH_MODES.items()):
        with cols[i]:
            is_active = key == current
            if st.button(
                mode["label"],
                key=f"depth_{key}",
                type="primary" if is_active else "secondary",
                use_container_width=True,
            ):
                st.session_state["thought_map_depth"] = key
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


STEP_PATTERN = re.compile(
    r"\[(STEP\s*\d+|BRANCH\s*[A-Z0-9]+|CONCLUSION|OBSERVATION|INFERENCE|ANALYSIS|RISK)\]"
    r"\s*(?:([^:\n]+):\s*)?(.+?)(?=\n*\[(?:STEP|BRANCH|CONCLUSION|OBSERVATION|INFERENCE|ANALYSIS|RISK)|$)",
    re.DOTALL | re.IGNORECASE,
)

NODE_TYPE_MAP = {
    "STEP": "step",
    "BRANCH": "branch",
    "CONCLUSION": "conclusion",
    "OBSERVATION": "step",
    "INFERENCE": "step",
    "ANALYSIS": "step",
    "RISK": "branch",
}

NODE_COLORS = {
    "root": "#0073FF",
    "step": "#0073FF",
    "branch": "#F59E0B",
    "conclusion": "#10B981",
    "human": "#8B5CF6",
    "queued": "#ff5b1f",
}


def add_queued_node(text: str, source_type: str = "suggestion", meta: dict = None):
    """Add a queued (pending) node to the thought map. Not yet reasoned about."""
    tm = _get_map()
    node_id = str(uuid.uuid4())[:8]
    label = text[:60] + ("…" if len(text) > 60 else "")
    node = {
        "id": node_id,
        "type": "queued",
        "label": label,
        "content": text,
        "parent_id": None,
        "children": [],
        "depth": 0,
        "collapsed": False,
        "created_at": datetime.now().isoformat(),
        "source_type": source_type,
        "meta": meta or {},
    }
    tm["nodes"][node_id] = node
    tm["root_ids"].append(node_id)
    st.session_state["thought_map"] = tm
    return node_id


def get_queued_nodes() -> list[dict]:
    """Return all queued (pending) nodes from the thought map."""
    tm = _get_map()
    return [n for n in tm["nodes"].values() if n.get("type") == "queued"]


def remove_node_from_map(node_id: str) -> bool:
    """Remove a node and its connected edges from the thought map."""
    tm = _get_map()
    if node_id not in tm["nodes"]:
        return False
    del tm["nodes"][node_id]
    tm["root_ids"] = [rid for rid in tm["root_ids"] if rid != node_id]
    tm["edges"] = [e for e in tm["edges"] if e["from"] != node_id and e["to"] != node_id]
    for node in tm["nodes"].values():
        if node_id in node.get("children", []):
            node["children"].remove(node_id)
    st.session_state["thought_map"] = tm
    return True


def promote_queued_nodes():
    """Mark all queued nodes as 'root' after AI reasoning starts. Returns the combined prompt text."""
    tm = _get_map()
    queued = [n for n in tm["nodes"].values() if n.get("type") == "queued"]
    texts = []
    for node in queued:
        node["type"] = "root"
        texts.append(node["content"])
    st.session_state["thought_map"] = tm
    return texts


def get_pending_human_notes() -> list[dict]:
    """Return human-authored notes that have not yet been included in a Genie prompt."""
    tm = _get_map()
    pending = []
    for node in tm["nodes"].values():
        if node.get("type") != "human":
            continue
        meta = node.get("meta") or {}
        if not meta.get("prompt_consumed", False):
            pending.append(node)
    return sorted(pending, key=lambda node: node.get("created_at", ""))


def consume_pending_human_notes() -> list[str]:
    """Mark pending human notes as consumed and return their text for prompt injection."""
    tm = _get_map()
    texts = []
    changed = False
    for node in get_pending_human_notes():
        text = str(node.get("content", "") or "").strip()
        if text:
            texts.append(text)
        meta = dict(node.get("meta") or {})
        meta["prompt_consumed"] = True
        meta["prompt_consumed_at"] = datetime.now().isoformat()
        node["meta"] = meta
        changed = True
    if changed:
        st.session_state["thought_map"] = tm
    return texts


def is_reasoning_node(node: dict) -> bool:
    """Return True only for assistant-generated reasoning nodes."""
    if node.get("type") not in {"step", "branch", "conclusion"}:
        return False
    try:
        return int(node.get("source_message_index", -1)) >= 0
    except (TypeError, ValueError):
        return False


def parse_response_to_nodes(response_text: str, message_index: int) -> list[dict]:
    """Parse a Genie response into structured thought map nodes."""
    matches = list(STEP_PATTERN.finditer(response_text))

    if not matches:
        return [
            {
                "id": str(uuid.uuid4())[:8],
                "type": "root",
                "label": f"Response #{message_index + 1}",
                "content": response_text[:200].strip() + ("…" if len(response_text) > 200 else ""),
                "parent_id": None,
                "children": [],
                "depth": 0,
                "collapsed": False,
                "created_at": datetime.now().isoformat(),
                "source_message_index": message_index,
            }
        ]

    nodes: list[dict] = []
    prev_id = None

    for i, match in enumerate(matches):
        raw_type = match.group(1).strip().upper()
        base_type = re.split(r"\s+\d+|\s+[A-Z]", raw_type)[0].strip()
        node_type = NODE_TYPE_MAP.get(base_type, "step")

        label = (match.group(2) or raw_type).strip()[:60]
        content = match.group(3).strip()

        node_id = str(uuid.uuid4())[:8]
        nodes.append(
            {
                "id": node_id,
                "type": node_type,
                "label": label,
                "content": content,
                "parent_id": prev_id,
                "children": [],
                "depth": i,
                "collapsed": False,
                "created_at": datetime.now().isoformat(),
                "source_message_index": message_index,
            }
        )

        if node_type != "branch":
            prev_id = node_id

    return nodes


def add_nodes_to_map(new_nodes: list[dict], parent_node_id: str = None):
    """Merge parsed nodes into session thought map."""
    tm = _get_map()

    for i, node in enumerate(new_nodes):
        if parent_node_id and i == 0:
            node["parent_id"] = parent_node_id
            if parent_node_id in tm["nodes"]:
                node["depth"] = tm["nodes"][parent_node_id]["depth"] + 1

        tm["nodes"][node["id"]] = node

        if node["parent_id"] is None:
            tm["root_ids"].append(node["id"])
        else:
            parent = tm["nodes"].get(node["parent_id"])
            if parent and node["id"] not in parent["children"]:
                parent["children"].append(node["id"])
            edge = {"from": node["parent_id"], "to": node["id"]}
            if edge not in tm["edges"]:
                tm["edges"].append(edge)

    st.session_state["thought_map"] = tm


def render_thought_map(height: int = 620, view_mode: str = "classic"):
    """Render the Genie thought map with selectable Genie-only views."""
    tm = _get_map()

    is_empty = not tm["nodes"]

    cy_nodes = []
    for node in tm["nodes"].values():
        color = NODE_COLORS.get(node["type"], "#64748B")
        sig_cat, sig_color = match_signal_category(
            node.get("label", "") + " " + node.get("content", "")
        )
        if sig_color:
            color = sig_color
        cy_nodes.append(
            {
                "data": {
                    "id": node["id"],
                    "label": node["label"][:30] + ("..." if len(node["label"]) > 30 else ""),
                    "fullLabel": node["label"],
                    "content": node["content"][:150] + ("..." if len(node["content"]) > 150 else ""),
                    "fullContent": node["content"],
                    "type": node["type"],
                    "color": color,
                    "depth": node["depth"],
                    "signalCategory": sig_cat,
                    "sourceType": node.get("source_type", ""),
                }
            }
        )

    cy_edges = []
    for edge in tm["edges"]:
        src = tm["nodes"].get(edge["from"], {})
        tgt = tm["nodes"].get(edge["to"], {})
        src_t = src.get("type", "")
        tgt_t = tgt.get("type", "")
        edge_label = ""
        if tgt_t == "branch":
            edge_label = "branches to"
        elif tgt_t == "conclusion":
            edge_label = "concludes"
        elif src_t == "root" and tgt_t == "step":
            edge_label = "leads to"
        elif src_t == "step":
            edge_label = "then"
        cy_edges.append(
            {
                "data": {
                    "id": "e_" + edge["from"] + "_" + edge["to"],
                    "source": edge["from"],
                    "target": edge["to"],
                    "edgeLabel": edge_label,
                }
            }
        )

    elements_json = json.dumps(cy_nodes + cy_edges)

    type_counts = {}
    for node in tm["nodes"].values():
        node_type = node["type"]
        type_counts[node_type] = type_counts.get(node_type, 0) + 1

    depth_mode = st.session_state.get("thought_map_depth", "balanced")
    context_company = str(st.session_state.get("genie_context_company", "") or "").strip() or "Cross-company"
    context_year = st.session_state.get("genie_context_year")
    context_quarter = str(st.session_state.get("genie_context_quarter", "") or "").strip() or "All quarters"

    meta_json = json.dumps(
        {
            "nodeCount": len(tm["nodes"]),
            "edgeCount": len(tm["edges"]),
            "counts": {
                "all": len(tm["nodes"]),
                "step": type_counts.get("step", 0) + type_counts.get("root", 0),
                "branch": type_counts.get("branch", 0),
                "conclusion": type_counts.get("conclusion", 0),
                "queued": type_counts.get("queued", 0),
                "human": type_counts.get("human", 0),
            },
            "context": {
                "company": context_company,
                "year": context_year if context_year is not None else "Latest year",
                "quarter": context_quarter,
                "depth": DEPTH_MODES.get(depth_mode, DEPTH_MODES["balanced"])["label"],
            },
        },
        default=str,
    )

    html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.26.0/cytoscape.min.js"></script>
  <style>
    * { box-sizing: border-box; }
    html, body {
      width: 100%;
      height: 100%;
      margin: 0;
      padding: 0;
      background: #08101d;
      color: #e2e8f0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      overflow: hidden;
    }
    #tm-app {
      width: 100%;
      height: 100%;
      display: grid;
      grid-template-columns: 1fr;
      background: linear-gradient(135deg, #0a1220 0%, #101c31 52%, #0a1220 100%);
      position: relative;
      overflow: hidden;
    }
    #tm-app.view-studio {
      grid-template-columns: minmax(0, 1fr) 320px;
    }
    #tm-app.view-classic #studio-sidebar,
    #tm-app.view-focus #studio-sidebar {
      display: none;
    }
    #tm-app.view-studio #classic-toolbar,
    #tm-app.view-studio #focus-dock {
      display: none;
    }
    #tm-app.view-focus #classic-toolbar,
    #tm-app.view-focus #map-status {
      display: none;
    }
    #tm-app.view-focus #focus-dock {
      display: flex;
    }
    #map-stage {
      position: relative;
      min-width: 0;
      height: 100%;
      overflow: hidden;
      background: linear-gradient(135deg, #0a1220 0%, #111d34 52%, #0a1220 100%);
    }
    #map-stage::before,
    #map-stage::after,
    #map-stage .aurora {
      content: "";
      position: absolute;
      inset: -22%;
      pointer-events: none;
      filter: blur(64px);
      opacity: 0.42;
      mix-blend-mode: screen;
    }
    #map-stage::before {
      background: radial-gradient(circle at 24% 24%, rgba(0, 115, 255, 0.42), transparent 30%);
      animation: auroraDrift 18s ease-in-out infinite alternate;
    }
    #map-stage::after {
      background: radial-gradient(circle at 78% 22%, rgba(255, 91, 31, 0.28), transparent 28%);
      animation: auroraDrift 24s ease-in-out infinite alternate-reverse;
    }
    #map-stage .aurora {
      background: radial-gradient(circle at 56% 78%, rgba(139, 92, 246, 0.28), transparent 32%);
      animation: auroraPulse 20s ease-in-out infinite;
    }
    @keyframes auroraDrift {
      0% { transform: translate3d(-8%, -4%, 0) scale(1); }
      50% { transform: translate3d(8%, 7%, 0) scale(1.08); }
      100% { transform: translate3d(-2%, 10%, 0) scale(0.96); }
    }
    @keyframes auroraPulse {
      0%, 100% { transform: translate3d(0, 0, 0) scale(1); opacity: 0.26; }
      50% { transform: translate3d(4%, -6%, 0) scale(1.14); opacity: 0.46; }
    }
    #cy {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      z-index: 1;
    }
    .glass {
      backdrop-filter: blur(14px);
      background: linear-gradient(180deg, rgba(8, 15, 28, 0.82), rgba(17, 28, 48, 0.62));
      border: 1px solid rgba(148, 163, 184, 0.14);
      box-shadow: 0 16px 40px rgba(2, 6, 23, 0.36);
    }
    #classic-toolbar {
      position: absolute;
      top: 14px;
      left: 14px;
      right: 230px;
      z-index: 8;
      border-radius: 18px;
      padding: 12px 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
    }
    .toolbar-group {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .toolbar-meta {
      color: #8ea2bf;
      font-size: 12px;
      font-weight: 600;
      white-space: nowrap;
    }
    .toolbar-btn,
    .side-btn,
    .dock-btn {
      border: 1px solid rgba(148, 163, 184, 0.22);
      border-radius: 12px;
      padding: 9px 12px;
      background: linear-gradient(135deg, rgba(100, 116, 139, 0.12), rgba(30, 41, 59, 0.18));
      color: #cbd5e1;
      font-size: 12px;
      font-weight: 700;
      cursor: pointer;
      transition: all 180ms ease;
    }
    .toolbar-btn:hover,
    .side-btn:hover,
    .dock-btn:hover {
      transform: translateY(-1px);
      border-color: rgba(59, 130, 246, 0.55);
      color: #ffffff;
      background: linear-gradient(135deg, rgba(59, 130, 246, 0.24), rgba(37, 99, 235, 0.16));
    }
    .toolbar-btn.active,
    .side-btn.active,
    .dock-btn.active {
      border-color: rgba(56, 189, 248, 0.85);
      color: #ffffff;
      background: linear-gradient(135deg, rgba(34, 211, 238, 0.72), rgba(14, 116, 144, 0.82));
      box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.15), 0 0 18px rgba(34, 211, 238, 0.28);
    }
    .toolbar-btn.danger,
    .side-btn.danger,
    .dock-btn.danger {
      border-color: rgba(239, 68, 68, 0.34);
      color: #fca5a5;
      background: linear-gradient(135deg, rgba(127, 29, 29, 0.28), rgba(127, 29, 29, 0.18));
    }
    .toolbar-btn.danger:hover,
    .side-btn.danger:hover,
    .dock-btn.danger:hover {
      border-color: rgba(248, 113, 113, 0.8);
      color: #fff;
      background: linear-gradient(135deg, rgba(220, 38, 38, 0.6), rgba(153, 27, 27, 0.48));
    }
    .count-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 18px;
      margin-left: 6px;
      padding: 1px 6px;
      border-radius: 999px;
      background: rgba(255,255,255,0.12);
      color: inherit;
      font-size: 10px;
      font-weight: 800;
    }
    #view-bar {
      position: absolute;
      top: 14px;
      right: 14px;
      z-index: 10;
      border-radius: 999px;
      padding: 5px 6px;
      display: flex;
      align-items: center;
      gap: 3px;
    }
    .vb-btn {
      border: 1px solid transparent;
      border-radius: 999px;
      padding: 6px 14px;
      background: transparent;
      color: #8ea2bf;
      font-size: 11px;
      font-weight: 700;
      cursor: pointer;
      transition: all 180ms ease;
      white-space: nowrap;
    }
    .vb-btn:hover {
      color: #fff;
      background: rgba(255,255,255,0.08);
    }
    .vb-btn.active {
      color: #fff;
      background: rgba(56,189,248,0.22);
      border-color: rgba(56,189,248,0.5);
    }
    .toolbar-btn.accent,
    .side-btn.accent,
    .dock-btn.accent {
      border-color: rgba(255,91,31,0.34);
      color: #ff8c42;
      background: linear-gradient(135deg, rgba(255,91,31,0.14), rgba(255,91,31,0.08));
    }
    .toolbar-btn.accent:hover,
    .side-btn.accent:hover,
    .dock-btn.accent:hover {
      border-color: rgba(255,91,31,0.8);
      color: #fff;
      background: linear-gradient(135deg, rgba(255,91,31,0.36), rgba(255,91,31,0.22));
    }
    #map-status {
      position: absolute;
      left: 14px;
      bottom: 14px;
      z-index: 7;
      width: min(360px, calc(100% - 28px));
      border-radius: 18px;
      padding: 14px;
    }
    .status-title,
    .section-title,
    .sidebar-kicker {
      margin: 0 0 10px;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: #7f93ae;
    }
    .status-row,
    .context-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 10px;
    }
    .status-chip,
    .context-chip {
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid rgba(148, 163, 184, 0.16);
      background: rgba(15, 23, 42, 0.55);
      color: #d8e3f0;
      font-size: 11px;
      font-weight: 700;
    }
    .selection-card {
      border-radius: 14px;
      padding: 12px;
      background: rgba(11, 18, 32, 0.72);
      border: 1px solid rgba(148, 163, 184, 0.12);
      color: #b9c6d8;
      min-height: 118px;
    }
    .selection-card strong {
      display: block;
      color: #f1f5f9;
      font-size: 14px;
      margin-bottom: 6px;
    }
    .selection-card .selection-type {
      display: inline-flex;
      align-items: center;
      padding: 4px 8px;
      border-radius: 999px;
      background: rgba(59, 130, 246, 0.14);
      color: #7dd3fc;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 10px;
    }
    .selection-card .selection-text {
      font-size: 12px;
      line-height: 1.55;
      color: #cbd5e1;
    }
    #focus-dock {
      position: absolute;
      top: 16px;
      left: 50%;
      transform: translateX(-50%);
      z-index: 8;
      display: none;
      align-items: center;
      gap: 10px;
      padding: 10px 12px;
      border-radius: 999px;
    }
    #studio-sidebar {
      position: relative;
      z-index: 9;
      height: 100%;
      min-width: 0;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      border-left: 1px solid rgba(148, 163, 184, 0.08);
      background: linear-gradient(180deg, rgba(9, 16, 30, 0.95), rgba(14, 26, 46, 0.9));
    }
    .sidebar-header {
      padding: 18px 16px 14px;
      border-bottom: 1px solid rgba(148, 163, 184, 0.08);
    }
    .sidebar-header h1 {
      margin: 0;
      font-size: 20px;
      font-weight: 800;
      color: #f1f5f9;
    }
    .sidebar-header p {
      margin: 6px 0 0;
      color: #93a5bd;
      font-size: 12px;
      line-height: 1.5;
    }
    .sidebar-content {
      flex: 1;
      overflow-y: auto;
      padding: 14px 16px 18px;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }
    .sidebar-content::-webkit-scrollbar {
      width: 7px;
    }
    .sidebar-content::-webkit-scrollbar-thumb {
      background: rgba(148, 163, 184, 0.28);
      border-radius: 999px;
    }
    .sidebar-card {
      border-radius: 16px;
      padding: 14px;
      background: linear-gradient(180deg, rgba(15, 23, 42, 0.72), rgba(15, 23, 42, 0.5));
      border: 1px solid rgba(148, 163, 184, 0.12);
    }
    .side-btn {
      width: 100%;
      text-align: left;
      margin-bottom: 8px;
    }
    .side-btn:last-child {
      margin-bottom: 0;
    }
    .stat-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .stat-card {
      border-radius: 14px;
      padding: 12px;
      background: rgba(8, 15, 28, 0.68);
      border: 1px solid rgba(148, 163, 184, 0.1);
    }
    .stat-card .value {
      display: block;
      font-size: 24px;
      font-weight: 900;
      line-height: 1;
      margin-bottom: 6px;
      color: #f8fafc;
    }
    .stat-card .label {
      color: #8ea2bf;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    #tooltip {
      position: fixed;
      display: none;
      pointer-events: none;
      z-index: 20;
      max-width: 340px;
      padding: 14px 16px;
      border-radius: 14px;
      background: rgba(10, 16, 28, 0.96);
      border: 1px solid rgba(148, 163, 184, 0.22);
      color: #e2e8f0;
      box-shadow: 0 18px 44px rgba(2, 6, 23, 0.54);
    }
    #tooltip .tt-label {
      font-size: 14px;
      font-weight: 800;
      color: #7dd3fc;
      margin-bottom: 5px;
    }
    #tooltip .tt-type {
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: #8ea2bf;
      margin-bottom: 8px;
    }
    #tooltip .tt-content {
      font-size: 12px;
      line-height: 1.55;
      color: #dbe4ef;
    }
    #tooltip .tt-badge {
      display: inline-flex;
      align-items: center;
      margin-top: 8px;
      padding: 3px 8px;
      border-radius: 999px;
      background: rgba(59, 130, 246, 0.16);
      color: #93c5fd;
      font-size: 10px;
      font-weight: 800;
    }
    #detail-panel {
      position: absolute;
      left: 14px;
      right: 14px;
      bottom: 14px;
      z-index: 12;
      display: none;
      border-radius: 18px;
      padding: 16px 18px;
    }
    #tm-app.view-studio #detail-panel {
      right: 348px;
    }
    #dp-close {
      float: right;
      border: none;
      background: none;
      color: #8ea2bf;
      cursor: pointer;
      font-size: 18px;
      line-height: 1;
    }
    #dp-close:hover {
      color: #ffffff;
    }
    #dp-label {
      color: #f8fafc;
      font-size: 15px;
      font-weight: 800;
      margin-bottom: 6px;
    }
    #dp-type {
      display: inline-flex;
      align-items: center;
      padding: 4px 8px;
      border-radius: 999px;
      background: rgba(56, 189, 248, 0.16);
      color: #67e8f9;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      margin-bottom: 10px;
    }
    #dp-content {
      color: #dce7f5;
      font-size: 12px;
      line-height: 1.6;
      white-space: pre-wrap;
    }
    @media (max-width: 860px) {
      #tm-app.view-studio {
        grid-template-columns: 1fr;
      }
      #studio-sidebar {
        display: none;
      }
      #tm-app.view-studio #classic-toolbar {
        display: flex;
      }
    }
  </style>
</head>
<body>
  <div id="tm-app" class="view-__INITIAL_VIEW__">
    <div id="map-stage">
      <div class="aurora"></div>
      <div id="empty-overlay" style="position:absolute;inset:0;z-index:5;display:flex;align-items:center;justify-content:center;pointer-events:none;">
        <div style="text-align:center;opacity:0.85;">
          <div style="font-size:2.8rem;margin-bottom:10px;">&#x1f9e0;</div>
          <div style="font-size:1.05rem;font-weight:700;color:#94a3b8;margin-bottom:6px;">Thought Map</div>
          <div style="font-size:0.82rem;color:#64748b;max-width:320px;line-height:1.5;">Enter a question below to start mapping, or select signals from the panels to queue them as nodes.</div>
        </div>
      </div>

      <div id="view-bar" class="glass">
        <button class="vb-btn" data-view="classic" onclick="setView('classic')">Classic</button>
        <button class="vb-btn" data-view="studio" onclick="setView('studio')">Studio</button>
        <button class="vb-btn" data-view="focus" onclick="setView('focus')">Focus</button>
      </div>

      <div id="classic-toolbar" class="glass">
        <div class="toolbar-group">
          <button class="toolbar-btn accent" type="button" onclick="startNewThought()">+ New Thought</button>
          <button class="toolbar-btn" type="button" onclick="startGenieThoughts()" style="border-color:rgba(255,91,31,0.4);color:#ff8c42;">Start Genie</button>
          <button class="toolbar-btn" type="button" onclick="resetView()">Reset View</button>
          <button class="toolbar-btn" type="button" onclick="zoomIn()">+</button>
          <button class="toolbar-btn" type="button" onclick="zoomOut()">-</button>
          <button class="toolbar-btn" id="focusBtn" type="button" onclick="toggleFocus()">Smart Focus</button>
          <button class="toolbar-btn danger" type="button" onclick="deleteSelectedNode()" id="deleteBtn" style="display:none;">Remove Node</button>
          <button class="toolbar-btn danger" type="button" onclick="clearAllNodes()" id="clearAllBtn" style="display:none;">Clear All</button>
          <button class="toolbar-btn" type="button" onclick="elaborateNode()" id="elaborateBtn" style="display:none;border-color:rgba(34,211,238,0.5);color:#22d3ee;">Elaborate</button>
        </div>
        <div class="toolbar-group">
          <button class="toolbar-btn active" type="button" data-filter="all" onclick="setFilter('all')">All <span class="count-badge" data-count="all"></span></button>
          <button class="toolbar-btn" type="button" data-filter="step" onclick="setFilter('step')">Steps <span class="count-badge" data-count="step"></span></button>
          <button class="toolbar-btn" type="button" data-filter="branch" onclick="setFilter('branch')">Branches <span class="count-badge" data-count="branch"></span></button>
          <button class="toolbar-btn" type="button" data-filter="conclusion" onclick="setFilter('conclusion')">End <span class="count-badge" data-count="conclusion"></span></button>
          <button class="toolbar-btn" type="button" data-filter="queued" onclick="setFilter('queued')">Queued <span class="count-badge" data-count="queued"></span></button>
          <button class="toolbar-btn" type="button" data-filter="human" onclick="setFilter('human')">Notes <span class="count-badge" data-count="human"></span></button>
        </div>
        <div class="toolbar-meta" id="toolbar-meta"></div>
      </div>

      <div id="focus-dock" class="glass">
        <button class="dock-btn accent" type="button" onclick="startNewThought()">+ New</button>
        <button class="dock-btn" type="button" onclick="resetView()">Reset</button>
        <button class="dock-btn" id="focusDockBtn" type="button" onclick="toggleFocus()">Focus</button>
        <button class="dock-btn danger" type="button" onclick="deleteSelectedNode()" id="deleteDockBtn" style="display:none;">Remove</button>
      </div>

      <div id="map-status" class="glass">
        <div class="status-title">Current Selection</div>
        <div class="status-row" id="context-row"></div>
        <div class="selection-card" id="selection-card">
          <strong>Nothing selected</strong>
          <div class="selection-type">Map state</div>
          <div class="selection-text">Tap a node to pin it. The active node will stay highlighted until you tap the canvas background or hit Refresh.</div>
        </div>
      </div>

      <div id="cy"></div>

      <div id="tooltip">
        <div class="tt-label" id="tt-label"></div>
        <div class="tt-type" id="tt-type"></div>
        <div class="tt-content" id="tt-content"></div>
        <div class="tt-badge" id="tt-badge" style="display:none"></div>
      </div>

      <div id="detail-panel" class="glass">
        <button id="dp-close" type="button" onclick="closeDetailPanel()">&times;</button>
        <div id="dp-label"></div>
        <div id="dp-type"></div>
        <div id="dp-content"></div>
      </div>
    </div>

    <aside id="studio-sidebar">
      <div class="sidebar-header">
        <h1>Financial Genie</h1>
        <p>Thought-map studio view with live status, filters, and pinned-node detail.</p>
      </div>
      <div class="sidebar-content">
        <div class="sidebar-card">
          <div class="section-title">Actions</div>
          <button class="side-btn accent" type="button" onclick="startNewThought()">+ New Thought</button>
          <button class="side-btn" type="button" onclick="startGenieThoughts()" style="border-color:rgba(255,91,31,0.4);color:#ff8c42;">Start Genie Thoughts</button>
          <button class="side-btn" type="button" onclick="resetView()">Reset view</button>
          <button class="side-btn" id="focusSideBtn" type="button" onclick="toggleFocus()">Smart Focus</button>
          <button class="side-btn danger" type="button" onclick="deleteSelectedNode()" id="deleteSideBtn" style="display:none;">Remove Selected Node</button>
          <button class="side-btn danger" type="button" onclick="clearAllNodes()">Clear All Thoughts</button>
          <button class="side-btn" type="button" onclick="elaborateNode()" id="elaborateSideBtn" style="display:none;border-color:rgba(34,211,238,0.5);color:#22d3ee;">Elaborate Selected</button>
        </div>

        <div class="sidebar-card">
          <div class="section-title">Layers</div>
          <button class="side-btn active" type="button" data-filter="all" onclick="setFilter('all')">All nodes <span class="count-badge" data-count="all"></span></button>
          <button class="side-btn" type="button" data-filter="step" onclick="setFilter('step')">Reasoning steps <span class="count-badge" data-count="step"></span></button>
          <button class="side-btn" type="button" data-filter="branch" onclick="setFilter('branch')">Branches <span class="count-badge" data-count="branch"></span></button>
          <button class="side-btn" type="button" data-filter="conclusion" onclick="setFilter('conclusion')">Conclusions <span class="count-badge" data-count="conclusion"></span></button>
          <button class="side-btn" type="button" data-filter="queued" onclick="setFilter('queued')">Queued prompts <span class="count-badge" data-count="queued"></span></button>
          <button class="side-btn" type="button" data-filter="human" onclick="setFilter('human')">Your notes <span class="count-badge" data-count="human"></span></button>
        </div>

        <div class="sidebar-card">
          <div class="section-title">Map State</div>
          <div class="stat-grid">
            <div class="stat-card"><span class="value" id="stat-nodes"></span><span class="label">Nodes</span></div>
            <div class="stat-card"><span class="value" id="stat-links"></span><span class="label">Links</span></div>
            <div class="stat-card"><span class="value" id="stat-depth"></span><span class="label">Depth</span></div>
            <div class="stat-card"><span class="value" id="stat-filter"></span><span class="label">Active Lens</span></div>
          </div>
        </div>

        <div class="sidebar-card">
          <div class="section-title">Current Selection</div>
          <div class="selection-card" id="selection-card-side">
            <strong>Nothing selected</strong>
            <div class="selection-type">Map state</div>
            <div class="selection-text">Tap a node to lock it in. Selection stays highlighted until you clear it.</div>
          </div>
        </div>

        <div class="sidebar-card">
          <div class="section-title">Context</div>
          <div class="context-row" id="context-row-side"></div>
        </div>
      </div>
    </aside>
  </div>

  <script>
    const elements = __ELEMENTS_JSON__;
    const meta = __META_JSON__;
    const initialView = "__INITIAL_VIEW__";
    const root = document.getElementById("tm-app");
    const filterLabels = {
      all: "All nodes",
      step: "Steps",
      branch: "Branches",
      conclusion: "Conclusions",
      queued: "Queued",
      human: "Notes",
    };
    let currentFilter = "all";
    let focusActive = false;
    let activeNode = null;

    const cy = cytoscape({
      container: document.getElementById("cy"),
      elements: [],
      style: [
        {
          selector: "node",
          style: {
            "background-color": "data(color)",
            "label": "data(label)",
            "color": "#f8fafc",
            "font-size": "11px",
            "font-weight": "700",
            "text-valign": "center",
            "text-halign": "center",
            "text-wrap": "wrap",
            "text-max-width": "88px",
            "width": "82px",
            "height": "82px",
            "border-width": 2,
            "border-color": "rgba(255,255,255,0.18)",
            "overlay-opacity": 0,
            "transition-property": "opacity, background-color, border-color, width, height, underlay-opacity",
            "transition-duration": "0.22s"
          }
        },
        { selector: "node[type='branch']", style: { "shape": "diamond", "width": "74px", "height": "74px" } },
        { selector: "node[type='conclusion']", style: { "shape": "round-rectangle", "width": "102px", "height": "58px" } },
        {
          selector: "node[type='human']",
          style: {
            "shape": "round-rectangle",
            "width": "92px",
            "border-width": 3,
            "border-style": "dashed",
            "border-color": "#8b5cf6"
          }
        },
        {
          selector: "node[type='queued']",
          style: {
            "shape": "round-rectangle",
            "width": "92px",
            "height": "60px",
            "border-width": 3,
            "border-style": "dashed",
            "border-color": "#ff5b1f",
            "background-color": "rgba(255,91,31,0.18)",
            "font-size": "10px",
            "color": "#ffb38f"
          }
        },
        { selector: "node[type='root']", style: { "width": "92px", "height": "92px", "font-size": "12px" } },
        {
          selector: "node:selected",
          style: {
            "border-width": 5,
            "border-color": "#38bdf8",
            "underlay-color": "#38bdf8",
            "underlay-opacity": 0.2,
            "underlay-padding": 16
          }
        },
        { selector: ".dimmed", style: { "opacity": 0.12 } },
        {
          selector: ".focused",
          style: {
            "border-width": 4,
            "border-color": "#22d3ee",
            "underlay-color": "#22d3ee",
            "underlay-opacity": 0.12,
            "underlay-padding": 10
          }
        },
        {
          selector: "edge",
          style: {
            "width": 2,
            "line-color": "rgba(99,179,237,0.45)",
            "target-arrow-color": "rgba(99,179,237,0.6)",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            "arrow-scale": 0.9,
            "label": "",
            "font-size": "8px",
            "color": "#8ea2bf",
            "text-rotation": "autorotate",
            "text-margin-y": -8,
            "opacity": 0.75,
            "line-style": "dashed",
            "line-dash-pattern": [8, 10],
            "line-dash-offset": 0,
            "transition-property": "opacity, line-color, width",
            "transition-duration": "0.4s"
          }
        },
        { selector: "edge.dimmed", style: { "opacity": 0.08 } },
        { selector: "edge.focused", style: { "width": 3.5, "line-color": "#22d3ee", "target-arrow-color": "#22d3ee" } }
      ],
      layout: { name: "breadthfirst", directed: true, spacingFactor: 1.68, padding: 32 },
      userZoomingEnabled: true,
      userPanningEnabled: true,
      minZoom: 0.15,
      maxZoom: 3
    });

    function relayout() {
      cy.layout({
        name: "breadthfirst",
        directed: true,
        spacingFactor: root.classList.contains("view-focus") ? 1.82 : 1.68,
        padding: 32,
        animate: true,
        animationDuration: 320
      }).run();
    }

    function fitMap() {
      const visibleNodes = cy.nodes(":visible");
      if (visibleNodes.length) {
        cy.fit(visibleNodes, 28);
      }
    }

    function zoomIn() {
      cy.zoom(Math.min(cy.zoom() * 1.24, 3));
    }

    function zoomOut() {
      cy.zoom(Math.max(cy.zoom() * 0.78, 0.2));
    }

    function closeDetailPanel() {
      document.getElementById("detail-panel").style.display = "none";
    }

    function renderContext() {
      const chips = [
        meta.context.company,
        meta.context.year,
        meta.context.quarter,
        meta.context.depth
      ].map(value => `<span class="context-chip">${value}</span>`).join("");
      document.getElementById("context-row").innerHTML = chips;
      document.getElementById("context-row-side").innerHTML = chips;
      document.getElementById("toolbar-meta").textContent = `${meta.nodeCount} nodes · ${meta.edgeCount} links`;
      document.getElementById("stat-nodes").textContent = meta.nodeCount;
      document.getElementById("stat-links").textContent = meta.edgeCount;
      document.getElementById("stat-depth").textContent = meta.context.depth;
      document.getElementById("stat-filter").textContent = filterLabels[currentFilter];
    }

    function updateCountBadges() {
      document.querySelectorAll("[data-count]").forEach((el) => {
        const key = el.dataset.count;
        el.textContent = meta.counts[key] || 0;
      });
    }

    function updateFilterButtons() {
      document.querySelectorAll("[data-filter]").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.filter === currentFilter);
      });
      document.getElementById("stat-filter").textContent = filterLabels[currentFilter];
    }

    function updateFocusButtons() {
      ["focusBtn", "focusSideBtn", "focusDockBtn"].forEach((id) => {
        const el = document.getElementById(id);
        if (el) {
          el.classList.toggle("active", focusActive);
        }
      });
    }

    function renderSelection(targetData) {
      const defaultHtml = `
        <strong>Nothing selected</strong>
        <div class="selection-type">Map state</div>
        <div class="selection-text">Tap a node to pin it. The active node will stay highlighted until you tap the canvas background or hit Refresh.</div>
      `;

      if (!targetData) {
        document.getElementById("selection-card").innerHTML = defaultHtml;
        document.getElementById("selection-card-side").innerHTML = defaultHtml;
        return;
      }

      const typeLabel = `${String(targetData.type || "").toUpperCase()}${targetData.signalCategory ? " · " + targetData.signalCategory : ""}`;
      const bodyHtml = `
        <strong>${targetData.fullLabel || targetData.label || "Node"}</strong>
        <div class="selection-type">${typeLabel}</div>
        <div class="selection-text">${targetData.fullContent || targetData.content || ""}</div>
      `;
      document.getElementById("selection-card").innerHTML = bodyHtml;
      document.getElementById("selection-card-side").innerHTML = bodyHtml;
    }

    function clearSelection() {
      activeNode = null;
      cy.nodes().unselect();
      renderSelection(null);
      closeDetailPanel();
    }

    function setFilter(type) {
      currentFilter = type;
      cy.elements().removeClass("dimmed focused");
      focusActive = false;
      updateFocusButtons();
      if (type === "all") {
        cy.nodes().style("display", "element");
        cy.edges().style("display", "element");
      } else if (type === "step") {
        cy.nodes().style("display", "none");
        cy.edges().style("display", "none");
        const matched = cy.nodes("[type='step'], [type='root']");
        matched.style("display", "element");
        matched.connectedEdges().style("display", "element");
        matched.connectedEdges().connectedNodes().style("display", "element");
      } else {
        cy.nodes().style("display", "none");
        cy.edges().style("display", "none");
        const matched = cy.nodes(`[type='${type}']`);
        if (type !== "root") {
          cy.nodes("[type='root']").style("display", "element");
        }
        matched.style("display", "element");
        matched.connectedEdges().style("display", "element");
        matched.connectedEdges().connectedNodes().style("display", "element");
      }
      updateFilterButtons();
      fitMap();
      if (activeNode && activeNode.style("display") === "none") {
        clearSelection();
      }
    }

    function resetView() {
      currentFilter = "all";
      focusActive = false;
      updateFocusButtons();
      cy.elements().removeClass("dimmed focused");
      cy.nodes().style("display", "element");
      cy.edges().style("display", "element");
      clearSelection();
      document.getElementById("tooltip").style.display = "none";
      toggleDeleteButtons(false);
      relayout();
      updateFilterButtons();
      setTimeout(function() { fitMap(); }, 340);
    }

    function setView(v) {
      root.classList.remove("view-classic", "view-studio", "view-focus");
      root.classList.add("view-" + v);
      document.querySelectorAll(".vb-btn[data-view]").forEach(function(b) {
        b.classList.toggle("active", b.dataset.view === v);
      });
      setTimeout(function() { fitMap(); }, 200);
    }

    function startNewThought() {
      var text = prompt("Enter a new thought or question:");
      if (!text || !text.trim()) return;
      text = text.trim();
      toggleEmptyOverlay(false);
      var nodeId = "user_" + Date.now();
      var label = text.length > 30 ? text.substring(0, 30) + "..." : text;
      cy.add({
        data: {
          id: nodeId,
          label: label,
          fullLabel: text.length > 60 ? text.substring(0, 60) + "..." : text,
          content: text.length > 150 ? text.substring(0, 150) + "..." : text,
          fullContent: text,
          type: "queued",
          color: "#ff5b1f",
          depth: 0,
          signalCategory: "",
          sourceType: "user_input"
        }
      });
      meta.nodeCount += 1;
      meta.counts.all += 1;
      meta.counts.queued = (meta.counts.queued || 0) + 1;
      updateCountBadges();
      renderContext();
      relayout();
      setTimeout(function() { fitMap(); }, 360);
      try {
        window.parent.postMessage({type: "tm_new_thought", text: text, nodeId: nodeId}, "*");
      } catch(e) {}
    }

    function deleteSelectedNode() {
      if (!activeNode) return;
      var nodeId = activeNode.data("id");
      // Remove connected edges first
      activeNode.connectedEdges().remove();
      // Remove the node from Cytoscape
      activeNode.remove();
      activeNode = null;
      clearSelection();
      updateCountBadges();
      toggleDeleteButtons(false);
      // Post message to parent Streamlit to remove from session state
      try {
        window.parent.postMessage({type: "tm_delete_node", nodeId: nodeId}, "*");
      } catch(e) {}
    }

    function toggleDeleteButtons(show) {
      var btns = document.querySelectorAll("#deleteBtn, #deleteDockBtn, #deleteSideBtn");
      btns.forEach(function(b) { b.style.display = show ? "" : "none"; });
      var ebBtns = document.querySelectorAll("#elaborateBtn, #elaborateSideBtn");
      ebBtns.forEach(function(b) { b.style.display = show ? "" : "none"; });
      var clrBtn = document.getElementById("clearAllBtn");
      if (clrBtn) clrBtn.style.display = cy.nodes().length > 0 ? "" : "none";
    }

    function clearAllNodes() {
      if (!confirm("Clear all thoughts from the map?")) return;
      cy.elements().remove();
      activeNode = null;
      clearSelection();
      updateCountBadges();
      toggleDeleteButtons(false);
      toggleEmptyOverlay(true);
      try { window.parent.postMessage({type: "tm_clear_all"}, "*"); } catch(e) {}
    }

    function startGenieThoughts() {
      try {
        // Scroll the parent page down to the chat input area
        var chatInput = window.parent.document.querySelector('[data-testid="stChatInput"] textarea, [data-testid="stTextArea"] textarea, [data-testid="stChatMessageInput"] textarea');
        if (chatInput) {
          chatInput.scrollIntoView({behavior: "smooth", block: "center"});
          setTimeout(function() { chatInput.focus(); }, 400);
        } else {
          // Fallback: scroll to bottom of page
          window.parent.scrollTo({top: window.parent.document.body.scrollHeight, behavior: "smooth"});
        }
      } catch(e) {
        // Cross-origin fallback
        try { window.parent.postMessage({type: "tm_start_genie"}, "*"); } catch(e2) {}
      }
    }

    function elaborateNode() {
      if (!activeNode) return;
      var text = activeNode.data("fullContent") || activeNode.data("content") || activeNode.data("label");
      try {
        // Find the chat input in the parent Streamlit page and pre-fill it
        var chatInput = window.parent.document.querySelector('[data-testid="stChatInput"] textarea, [data-testid="stTextArea"] textarea');
        if (chatInput) {
          var elaboratePrompt = "Please elaborate further on: " + text;
          // Set the value using native input setter to trigger React state
          var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
          nativeSetter.call(chatInput, elaboratePrompt);
          chatInput.dispatchEvent(new Event("input", {bubbles: true}));
          chatInput.scrollIntoView({behavior: "smooth", block: "center"});
          setTimeout(function() { chatInput.focus(); }, 300);
        } else {
          window.parent.scrollTo({top: window.parent.document.body.scrollHeight, behavior: "smooth"});
        }
      } catch(e) {
        try { window.parent.postMessage({type: "tm_elaborate", nodeId: activeNode.data("id"), text: text}, "*"); } catch(e2) {}
      }
    }

    function toggleEmptyOverlay(show) {
      var overlay = document.getElementById("empty-overlay");
      if (overlay) overlay.style.display = show ? "flex" : "none";
    }

    function toggleFocus() {
      focusActive = !focusActive;
      updateFocusButtons();
      cy.elements().removeClass("dimmed focused");
      if (!focusActive) {
        return;
      }

      const conclusions = cy.nodes("[type='conclusion']:visible");
      if (conclusions.length === 0) {
        const important = cy.nodes("[type='root']:visible, [type='queued']:visible");
        cy.elements(":visible").addClass("dimmed");
        important.removeClass("dimmed").addClass("focused");
        important.connectedEdges(":visible").removeClass("dimmed").addClass("focused");
        return;
      }

      let pathNodes = cy.collection();
      let pathEdges = cy.collection();
      conclusions.forEach((conclusion) => {
        let current = conclusion;
        pathNodes = pathNodes.union(current);
        while (true) {
          const incoming = current.incomers("edge:visible");
          if (incoming.length === 0) break;
          const edge = incoming[0];
          pathEdges = pathEdges.union(edge);
          current = edge.source();
          pathNodes = pathNodes.union(current);
        }
      });
      cy.elements(":visible").addClass("dimmed");
      pathNodes.removeClass("dimmed").addClass("focused");
      pathEdges.removeClass("dimmed").addClass("focused");
    }

    function showDetailPanel(targetData) {
      document.getElementById("dp-label").textContent = targetData.fullLabel || targetData.label || "Node";
      document.getElementById("dp-type").textContent = `${String(targetData.type || "").toUpperCase()}${targetData.signalCategory ? " · " + targetData.signalCategory : ""}`;
      document.getElementById("dp-content").textContent = targetData.fullContent || targetData.content || "";
      document.getElementById("detail-panel").style.display = "block";
    }

    root.classList.remove("view-classic", "view-studio", "view-focus");
    root.classList.add("view-" + initialView);
    document.querySelectorAll(".vb-btn[data-view]").forEach(function(b) {
      b.classList.toggle("active", b.dataset.view === initialView);
    });
    cy.add(elements);
    toggleEmptyOverlay(elements.length === 0);
    if (elements.length > 0) relayout();
    const allNodes = cy.nodes();
    const allEdges = cy.edges();
    allNodes.style("opacity", 0);
    allEdges.style("opacity", 0);
    allNodes.forEach((node, index) => {
      setTimeout(() => {
        node.animate({ style: { opacity: 1 } }, { duration: 460, easing: "ease-out-cubic" });
        const originalBorder = node.style("border-color");
        node.style({ "border-width": 5, "border-color": node.data("color") || "#38bdf8" });
        setTimeout(() => {
          node.animate({ style: { "border-width": 2, "border-color": originalBorder } }, { duration: 720 });
        }, 360);
        node.connectedEdges().forEach((edge) => {
          const sourceVisible = parseFloat(edge.source().style("opacity")) > 0.5;
          const targetVisible = parseFloat(edge.target().style("opacity")) > 0.5;
          if (sourceVisible && targetVisible) {
            edge.animate({ style: { opacity: 1 } }, { duration: 320 });
          }
        });
      }, 220 + index * 220);
    });
    setTimeout(() => fitMap(), 280 + allNodes.length * 220 + 180);

    // Edge pulse animation — subtle glow on edges after load
    setTimeout(() => {
      cy.edges().forEach((edge, i) => {
        setTimeout(() => {
          edge.animate(
            { style: { "width": 3.5, "line-color": "rgba(56,189,248,0.6)", "target-arrow-color": "rgba(56,189,248,0.7)" } },
            { duration: 400, easing: "ease-out-cubic", complete: () => {
              edge.animate(
                { style: { "width": 2, "line-color": "rgba(99,179,237,0.45)", "target-arrow-color": "rgba(99,179,237,0.6)" } },
                { duration: 600, easing: "ease-in-out-cubic" }
              );
            }}
          );
        }, i * 120);
      });
    }, 280 + allNodes.length * 220 + 400);

    cy.on("mouseover", "edge", (evt) => {
      const edge = evt.target;
      const label = edge.data("edgeLabel");
      if (label) {
        edge.style("label", label);
      }
    });
    cy.on("mouseout", "edge", (evt) => {
      evt.target.style("label", "");
    });

    const tooltip = document.getElementById("tooltip");
    cy.on("mouseover", "node", (evt) => {
      const node = evt.target;
      const targetData = node.data();
      document.getElementById("tt-label").textContent = targetData.fullLabel || targetData.label || "";
      document.getElementById("tt-type").textContent = `${String(targetData.type || "").toUpperCase()}${targetData.signalCategory ? " · " + targetData.signalCategory : ""}`;
      document.getElementById("tt-content").textContent = targetData.content || "";
      const badge = document.getElementById("tt-badge");
      const children = node.outgoers("node").length;
      if (children > 0) {
        badge.textContent = `${children} connected`;
        badge.style.display = "inline-flex";
      } else {
        badge.style.display = "none";
      }
      tooltip.style.display = "block";
    });
    cy.on("mousemove", (evt) => {
      if (tooltip.style.display === "block") {
        tooltip.style.left = `${evt.originalEvent.clientX + 16}px`;
        tooltip.style.top = `${evt.originalEvent.clientY - 10}px`;
      }
    });
    cy.on("mouseout", "node", () => {
      tooltip.style.display = "none";
    });
    cy.on("tap", "node", (evt) => {
      activeNode = evt.target;
      activeNode.select();
      const targetData = activeNode.data();
      renderSelection(targetData);
      tooltip.style.display = "none";
      toggleDeleteButtons(true);
    });
    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        tooltip.style.display = "none";
        clearSelection();
        toggleDeleteButtons(false);
      }
    });

    updateCountBadges();
    updateFilterButtons();
    updateFocusButtons();
    renderContext();
    renderSelection(null);

    // ── Continuous flowing animation ──
    // Animate edge dash offsets for flowing line effect
    let _dashOffset = 0;
    let _floatPhase = 0;
    const _nodePhases = new Map();

    function _animLoop(ts) {
      _dashOffset = (ts * 0.025) % 200;
      _floatPhase = ts * 0.001;

      // Flowing dashed edges
      cy.edges().forEach(function(edge) {
        edge.style("line-dash-offset", -_dashOffset);
      });

      // Gentle node float (subtle Y oscillation)
      cy.nodes().forEach(function(node, idx) {
        if (!_nodePhases.has(node.id())) {
          _nodePhases.set(node.id(), { offset: Math.random() * Math.PI * 2, amp: 2 + Math.random() * 4 });
        }
        var p = _nodePhases.get(node.id());
        var dy = Math.sin(_floatPhase * 0.4 + p.offset) * p.amp;
        var pos = node.position();
        if (!node._baseY) node._baseY = pos.y;
        node.position("y", node._baseY + dy);
      });

      requestAnimationFrame(_animLoop);
    }
    // Start after layout settles
    setTimeout(function() {
      // Capture base positions after layout
      cy.nodes().forEach(function(node) {
        node._baseY = node.position("y");
      });
      requestAnimationFrame(_animLoop);
    }, 280 + allNodes.length * 220 + 600);
  </script>
</body>
</html>
"""

    html = (
        html_template
        .replace("__ELEMENTS_JSON__", elements_json)
        .replace("__META_JSON__", meta_json)
        .replace("__INITIAL_VIEW__", view_mode if view_mode in {"classic", "studio", "focus"} else "classic")
    )

    components.html(html, height=height, scrolling=False)


def render_thought_map_dashboard():
    """Render a status dashboard below the thought map showing current state."""
    tm = _get_map()
    if not tm["nodes"]:
        return

    type_counts = {}
    for n in tm["nodes"].values():
        t = n["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    queued = type_counts.get("queued", 0)
    steps = type_counts.get("step", 0) + type_counts.get("root", 0)
    branches = type_counts.get("branch", 0)
    conclusions = type_counts.get("conclusion", 0)
    human = type_counts.get("human", 0)
    total = len(tm["nodes"])
    edges = len(tm["edges"])

    # Build status cards with INLINE styles (st.markdown strips class attributes)
    _stat_base = (
        "background:rgba(15,23,42,0.6);border-radius:6px;"
        "padding:6px 12px;min-width:60px;text-align:center;display:inline-block;"
    )
    _num_base = "display:block;font-size:1.3rem;font-weight:800;"
    _lbl_base = "display:block;font-size:0.65rem;color:#64748B;text-transform:uppercase;letter-spacing:0.06em;"

    cards = []
    if queued:
        cards.append(
            f"<div style='{_stat_base}border-left:3px solid #ff5b1f;'>"
            f"<span style='{_num_base}color:#ff5b1f;'>{queued}</span>"
            f"<span style='{_lbl_base}'>Queued</span></div>")
    if steps:
        cards.append(
            f"<div style='{_stat_base}border-left:3px solid #0073FF;'>"
            f"<span style='{_num_base}color:#0073FF;'>{steps}</span>"
            f"<span style='{_lbl_base}'>Steps</span></div>")
    if branches:
        cards.append(
            f"<div style='{_stat_base}border-left:3px solid #F59E0B;'>"
            f"<span style='{_num_base}color:#F59E0B;'>{branches}</span>"
            f"<span style='{_lbl_base}'>Branches</span></div>")
    if conclusions:
        cards.append(
            f"<div style='{_stat_base}border-left:3px solid #10B981;'>"
            f"<span style='{_num_base}color:#10B981;'>{conclusions}</span>"
            f"<span style='{_lbl_base}'>Conclusions</span></div>")
    if human:
        cards.append(
            f"<div style='{_stat_base}border-left:3px solid #8B5CF6;'>"
            f"<span style='{_num_base}color:#8B5CF6;'>{human}</span>"
            f"<span style='{_lbl_base}'>Notes</span></div>")
    cards.append(
        f"<div style='{_stat_base}border-left:3px solid #475569;'>"
        f"<span style='{_num_base}color:#94A3B8;'>{edges}</span>"
        f"<span style='{_lbl_base}'>Links</span></div>")

    # Latest activity
    latest_nodes = sorted(tm["nodes"].values(), key=lambda n: n.get("created_at", ""), reverse=True)[:3]
    activity_items = []
    for n in latest_nodes:
        _type_colors = {"root": "#0073FF", "step": "#0073FF", "branch": "#F59E0B",
                        "conclusion": "#10B981", "human": "#8B5CF6", "queued": "#ff5b1f"}
        _tc = _type_colors.get(n["type"], "#475569")
        safe_label = html.escape(str(n.get("label", ""))[:40])
        safe_type = html.escape(str(n.get("type", "")))
        activity_items.append(
            f"<div style='display:flex;align-items:center;gap:6px;padding:2px 0;font-size:0.8rem;color:#CBD5E1;'>"
            f"<span style='width:8px;height:8px;border-radius:50%;background:{_tc};flex-shrink:0;display:inline-block;'></span>"
            f"<span style='flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'>{safe_label}</span>"
            f"<span style='font-size:0.6rem;color:#475569;text-transform:uppercase;background:rgba(255,255,255,0.06);"
            f"border-radius:4px;padding:1px 5px;'>{safe_type}</span>"
            f"</div>"
        )
    activity_html = "".join(activity_items)

    st.markdown(
        f"<div style='display:flex;gap:10px;align-items:flex-start;margin-top:8px;flex-wrap:wrap;'>"
        f"  <div style='display:flex;gap:8px;flex-wrap:wrap;'>{''.join(cards)}</div>"
        f"  <div style='flex:1;background:rgba(15,23,42,0.6);border-radius:6px;padding:8px 12px;min-width:180px;'>"
        f"    <div style='font-size:0.7rem;color:#64748B;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px;'>Latest Activity</div>"
        f"    {activity_html}"
        f"  </div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_thought_map_controls():
    """Render annotation/elaboration/export controls below the thought map."""
    # Style controls for dark background — buttons, inputs, captions
    st.markdown("""<style>
    /* Thought map controls — readable on dark bg */
    [data-testid="stForm"] [data-testid="stTextInput"] input {
        background: rgba(15,23,42,0.7) !important;
        color: #e2e8f0 !important;
        border: 1px solid rgba(148,163,184,0.2) !important;
        border-radius: 8px !important;
        -webkit-text-fill-color: #e2e8f0 !important;
    }
    [data-testid="stForm"] [data-testid="stTextInput"] input::placeholder {
        color: #64748b !important;
        -webkit-text-fill-color: #64748b !important;
        opacity: 1 !important;
    }
    [data-testid="stForm"] button[data-testid="stBaseButton-secondaryFormSubmit"],
    [data-testid="stForm"] button[kind="secondaryFormSubmit"] {
        background: rgba(255,91,31,0.15) !important;
        color: #ff8c42 !important;
        border: 1px solid rgba(255,91,31,0.3) !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        background-image: none !important;
    }
    [data-testid="stForm"] button[data-testid="stBaseButton-secondaryFormSubmit"]:hover,
    [data-testid="stForm"] button[kind="secondaryFormSubmit"]:hover {
        background: rgba(255,91,31,0.25) !important;
        border-color: #ff5b1f !important;
        color: #ffffff !important;
        background-image: none !important;
    }
    [data-testid="stForm"] button p,
    [data-testid="stForm"] button span {
        color: inherit !important;
    }
    [data-testid="stCaptionContainer"] p {
        color: #64748b !important;
    }
    </style>""", unsafe_allow_html=True)
    tm = _get_map()
    reasoning_candidates = [node for node in tm["nodes"].values() if is_reasoning_node(node)]

    col1, col2, col3, col4, col5 = st.columns([2.2, 1.0, 1.2, 1.0, 0.7])

    with col1:
        with st.form("tm_annotation_form", clear_on_submit=True):
            annotation = st.text_input(
                "Add your own thought node",
                placeholder="e.g. 'But what about subscriber growth offsetting this?'",
                key="tm_annotation_input",
                label_visibility="collapsed",
            )
            st.caption("Press Enter or click Add to Map.")
            add_note = st.form_submit_button("+ Add to Map", use_container_width=True)
        if add_note and annotation.strip():
            human_node = {
                "id": str(uuid.uuid4())[:8],
                "type": "human",
                "label": "Your note",
                "content": annotation.strip(),
                "parent_id": None,
                "children": [],
                "depth": 0,
                "collapsed": False,
                "created_at": datetime.now().isoformat(),
                "source_message_index": -1,
                "meta": {"prompt_consumed": False},
            }
            tm["nodes"][human_node["id"]] = human_node
            tm["root_ids"].append(human_node["id"])
            st.session_state["thought_map"] = tm
            st.rerun()

    with col2:
        if st.button(
            "Elaborate Last Node",
            key="tm_elaborate_btn",
            use_container_width=True,
            disabled=not reasoning_candidates,
        ):
            last_node = max(reasoning_candidates, key=lambda node: node.get("created_at", ""))
            from utils.thought_map import add_queued_node as _aq
            _aq(
                "Please elaborate further on this reasoning step:\n\n"
                f"**{last_node['label']}**\n{last_node['content']}\n\n"
                "Go deeper — use the [STEP N] format for your reasoning.",
                source_type="elaboration",
            )
            st.session_state["pending_elaboration_node_id"] = last_node["id"]
            st.rerun()

    with col3:
        if tm["nodes"]:
            _exp_fmt = st.selectbox(
                "Export format",
                ["Markdown", "JSON"],
                key="tm_export_format",
                label_visibility="collapsed",
            )
            if _exp_fmt == "JSON":
                _data = json.dumps(tm, indent=2, default=str)
                _fname = f"thought_map_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
                _mime = "application/json"
            else:
                _data = _map_to_markdown(tm)
                _fname = f"thought_map_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
                _mime = "text/markdown"
            st.download_button(
                f"Export Map ({_exp_fmt})",
                data=_data,
                file_name=_fname,
                mime=_mime,
                key="tm_export_btn",
            )

    with col4:
        _node_options = {
            nid: f"{n.get('label', '?')[:28]} ({n.get('type', '?')})"
            for nid, n in tm["nodes"].items()
        }
        if _node_options:
            _sel_remove = st.selectbox(
                "Remove node",
                options=list(_node_options.keys()),
                format_func=lambda x: _node_options.get(x, x),
                key="tm_remove_select",
                label_visibility="collapsed",
            )
            if st.button("Remove", key="tm_remove_btn", use_container_width=True):
                remove_node_from_map(_sel_remove)
                st.rerun()

    with col5:
        if tm["nodes"]:
            if st.button("Clear All", key="tm_clear_all_btn", use_container_width=True):
                st.session_state["thought_map"] = _empty_map()
                st.rerun()


def clear_thought_map():
    """Clear all nodes and edges from the thought map."""
    st.session_state["thought_map"] = _empty_map()


def _map_to_markdown(tm: dict) -> str:
    lines = ["# Genie Thought Map\n", f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n"]

    type_icons = {
        "root": "🔵",
        "step": "➡️",
        "branch": "🔀",
        "conclusion": "✅",
        "human": "💬",
    }

    def render_node(node_id: str, indent: int):
        node = tm["nodes"].get(node_id)
        if not node:
            return
        prefix = "  " * indent
        icon = type_icons.get(node["type"], "•")
        lines.append(f"{prefix}{icon} **{node['label']}**")
        lines.append(f"{prefix}  > {node['content']}\n")
        for child_id in node.get("children", []):
            render_node(child_id, indent + 1)

    for root_id in tm.get("root_ids", []):
        render_node(root_id, 0)

    return "\n".join(lines)
