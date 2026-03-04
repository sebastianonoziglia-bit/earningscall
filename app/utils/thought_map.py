import json
import re
import uuid
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components


def _empty_map() -> dict:
    return {"nodes": {}, "edges": [], "root_ids": [], "version": 1}


def _get_map() -> dict:
    if "thought_map" not in st.session_state:
        st.session_state["thought_map"] = _empty_map()
    return st.session_state["thought_map"]


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
}


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


def render_thought_map(height: int = 520):
    """Render thought map with Cytoscape.js."""
    tm = _get_map()

    if not tm["nodes"]:
        st.markdown(
            "<div style='padding:32px; text-align:center; color:#64748B; "
            "border:1px dashed rgba(100,116,139,0.3); border-radius:12px;'>"
            "💭 <strong>The thought map will grow here as Genie reasons through your questions.</strong><br/>"
            "<span style='font-size:0.85rem;'>Ask Genie something complex to see the first nodes appear.</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    cy_nodes = []
    for node in tm["nodes"].values():
        color = NODE_COLORS.get(node["type"], "#64748B")
        cy_nodes.append(
            {
                "data": {
                    "id": node["id"],
                    "label": node["label"][:30] + ("…" if len(node["label"]) > 30 else ""),
                    "fullLabel": node["label"],
                    "content": node["content"][:150] + ("…" if len(node["content"]) > 150 else ""),
                    "type": node["type"],
                    "color": color,
                    "depth": node["depth"],
                }
            }
        )

    cy_edges = [
        {"data": {"id": f"e_{edge['from']}_{edge['to']}", "source": edge["from"], "target": edge["to"]}}
        for edge in tm["edges"]
    ]

    elements_json = json.dumps(cy_nodes + cy_edges)
    node_count = len(tm["nodes"])
    edge_count = len(tm["edges"])

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.26.0/cytoscape.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0B1220; font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif; overflow: hidden; }}
  #cy {{ width: 100%; height: {height - 44}px; }}
  #bar {{
    height: 44px; background: #111827; border-bottom: 1px solid rgba(148,163,184,0.15);
    display: flex; align-items: center; padding: 0 14px; gap: 8px;
  }}
  .btn {{
    background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15);
    color: #CBD5E1; border-radius: 6px; padding: 4px 10px; cursor: pointer;
    font-size: 0.75rem; font-weight: 600; letter-spacing: 0.02em;
    transition: background 0.15s;
  }}
  .btn:hover {{ background: rgba(0,115,255,0.25); border-color: #0073FF; color:#fff; }}
  #meta {{ margin-left: auto; font-size: 0.72rem; color: #475569; font-weight: 600; }}
  #tooltip {{
    position: fixed; display: none; pointer-events: none; z-index: 1000;
    background: #1E293B; border: 1px solid rgba(148,163,184,0.25);
    border-radius: 10px; padding: 12px 14px; max-width: 300px;
    font-size: 0.82rem; color: #E2E8F0;
    box-shadow: 0 8px 28px rgba(0,0,0,0.45);
  }}
  #tooltip .tt-label {{ font-weight: 800; color: #60A5FA; margin-bottom: 6px; font-size: 0.88rem; }}
  #tooltip .tt-type {{ font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.08em; color: #94A3B8; margin-bottom: 8px; }}
  #tooltip .tt-content {{ line-height: 1.5; color: #CBD5E1; }}
  .legend {{ display: flex; gap: 14px; align-items: center; }}
  .leg-dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 4px; }}
  .leg-item {{ font-size: 0.7rem; color: #64748B; display: flex; align-items: center; }}
</style>
</head>
<body>
<div id="bar">
  <button class="btn" onclick="cy.fit(cy.nodes(), 30)">⊡ Fit all</button>
  <button class="btn" onclick="cy.zoom(Math.min(cy.zoom()*1.3, 3))">＋</button>
  <button class="btn" onclick="cy.zoom(Math.max(cy.zoom()*0.75, 0.2))">－</button>
  <button class="btn" onclick="relayout()">⟳ Re-layout</button>
  <div class="legend">
    <span class="leg-item"><span class="leg-dot" style="background:#0073FF"></span>Step</span>
    <span class="leg-item"><span class="leg-dot" style="background:#F59E0B"></span>Branch</span>
    <span class="leg-item"><span class="leg-dot" style="background:#10B981"></span>Conclusion</span>
    <span class="leg-item"><span class="leg-dot" style="background:#8B5CF6"></span>Your note</span>
  </div>
  <div id="meta">{node_count} nodes · {edge_count} connections</div>
</div>
<div id="cy"></div>
<div id="tooltip"><div class="tt-label" id="tt-label"></div><div class="tt-type" id="tt-type"></div><div class="tt-content" id="tt-content"></div></div>

<script>
const elements = {elements_json};

const cy = cytoscape({{
  container: document.getElementById('cy'),
  elements: elements,
  style: [
    {{
      selector: 'node',
      style: {{
        'background-color': 'data(color)',
        'label': 'data(label)',
        'color': '#F8FAFC',
        'font-size': '11px',
        'font-weight': '700',
        'text-valign': 'center',
        'text-halign': 'center',
        'text-wrap': 'wrap',
        'text-max-width': '80px',
        'width': '80px',
        'height': '80px',
        'border-width': 2,
        'border-color': 'rgba(255,255,255,0.18)',
        'transition-property': 'background-color, border-color, width, height',
        'transition-duration': '0.18s',
        'overlay-padding': 8,
      }}
    }},
    {{ selector: 'node[type="branch"]', style: {{ 'shape': 'diamond', 'width': '72px', 'height': '72px' }} }},
    {{ selector: 'node[type="conclusion"]', style: {{ 'shape': 'round-rectangle', 'width': '100px', 'height': '56px' }} }},
    {{
      selector: 'node[type="human"]',
      style: {{
        'border-width': 3, 'border-color': '#8B5CF6', 'border-style': 'dashed',
        'shape': 'round-rectangle', 'width': '90px',
      }}
    }},
    {{ selector: 'node[type="root"]', style: {{ 'width': '90px', 'height': '90px', 'font-size': '12px' }} }},
    {{ selector: 'node:selected', style: {{ 'border-width': 4, 'border-color': '#00C2FF', 'width': '92px', 'height': '92px' }} }},
    {{
      selector: 'edge',
      style: {{
        'width': 2,
        'line-color': 'rgba(100,116,139,0.4)',
        'target-arrow-color': 'rgba(100,116,139,0.6)',
        'target-arrow-shape': 'triangle',
        'curve-style': 'bezier',
        'arrow-scale': 0.9,
      }}
    }},
  ],
  layout: {{ name: 'breadthfirst', directed: true, spacingFactor: 1.65, padding: 28 }},
  userZoomingEnabled: true,
  userPanningEnabled: true,
  minZoom: 0.15,
  maxZoom: 3,
}});

function relayout() {{
  cy.layout({{ name: 'breadthfirst', directed: true, spacingFactor: 1.65, padding: 28 }}).run();
}}

const tooltip = document.getElementById('tooltip');
cy.on('mouseover', 'node', (evt) => {{
  const n = evt.target;
  document.getElementById('tt-label').textContent = n.data('fullLabel');
  document.getElementById('tt-type').textContent = n.data('type').toUpperCase();
  document.getElementById('tt-content').textContent = n.data('content');
  tooltip.style.display = 'block';
}});
cy.on('mousemove', (evt) => {{
  if (tooltip.style.display === 'block') {{
    tooltip.style.left = (evt.originalEvent.clientX + 16) + 'px';
    tooltip.style.top = (evt.originalEvent.clientY - 10) + 'px';
  }}
}});
cy.on('mouseout', 'node', () => tooltip.style.display = 'none');
cy.on('tap', 'node', (evt) => {{
  const n = evt.target;
  tooltip.style.left = (evt.renderedPosition.x + 16) + 'px';
  tooltip.style.top = (evt.renderedPosition.y - 10) + 'px';
  tooltip.style.display = 'block';
}});
cy.on('tap', (evt) => {{ if (evt.target === cy) tooltip.style.display = 'none'; }});
</script>
</body>
</html>"""

    components.html(html, height=height, scrolling=False)


def render_thought_map_controls():
    """Render annotation/elaboration/export controls below the thought map."""
    tm = _get_map()

    col1, col2, col3, col4 = st.columns([2.5, 1.2, 1.2, 1.2])

    with col1:
        annotation = st.text_input(
            "💬 Add your own thought node",
            placeholder="e.g. 'But what about subscriber growth offsetting this?'",
            key="tm_annotation_input",
            label_visibility="collapsed",
        )
        if st.button("＋ Add to Map", key="tm_add_node_btn") and annotation.strip():
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
            }
            tm["nodes"][human_node["id"]] = human_node
            tm["root_ids"].append(human_node["id"])
            st.session_state["thought_map"] = tm
            st.rerun()

    with col2:
        if st.button("🔍 Elaborate Last Node", key="tm_elaborate_btn"):
            if tm["nodes"]:
                candidates = [node for node in tm["nodes"].values() if node["type"] != "human"]
                if candidates:
                    last_node = max(candidates, key=lambda node: node["created_at"])
                    prompt = (
                        "Please elaborate further on this reasoning step:\n\n"
                        f"**{last_node['label']}**\n{last_node['content']}\n\n"
                        "Go deeper — use the [STEP N] format for your reasoning."
                    )
                    st.session_state["prefill_message"] = prompt
                    st.session_state["pending_elaboration_node_id"] = last_node["id"]
                    st.rerun()

    with col3:
        if tm["nodes"]:
            st.download_button(
                "⬇ Export JSON",
                data=json.dumps(tm, indent=2, default=str),
                file_name=f"thought_map_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json",
                key="tm_export_json_btn",
            )

    with col4:
        if tm["nodes"]:
            st.download_button(
                "⬇ Export Markdown",
                data=_map_to_markdown(tm),
                file_name=f"thought_map_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
                mime="text/markdown",
                key="tm_export_md_btn",
            )


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
