"""Enhanced Genie chat UI wired to OpenAI + Thought Map."""

import html
import json
from datetime import datetime
from io import BytesIO

import streamlit as st

from utils.genie_ai import (
    build_genie_messages,
    build_query_transcript_context,
    clean_thought_markers,
    stream_genie_response,
)
from utils.thought_map import (
    add_nodes_to_map,
    consume_pending_human_notes,
    get_pending_human_notes,
    get_queued_nodes,
    parse_response_to_nodes,
    promote_queued_nodes,
)

# Check fpdf availability once at module level
try:
    from fpdf import FPDF as _FPDF  # noqa: F401
    _HAS_FPDF = True
except ImportError:
    _HAS_FPDF = False


def _estimate_token_usage(history: list[dict]) -> int:
    total_chars = 0
    for message in history:
        total_chars += len(str(message.get("content", "")))
    return total_chars // 4


def _format_note_lines(notes: list[str]) -> str:
    cleaned = [str(note).strip() for note in notes if str(note).strip()]
    return "\n".join(f"- {note}" for note in cleaned)


# ── PDF generation ──────────────────────────────────────────────────────────

def _build_chat_pdf(history: list[dict]) -> bytes:
    """Build a styled PDF of the Genie chat dialogue. Requires fpdf2."""
    from fpdf import FPDF

    class _PDF(FPDF):
        def header(self):
            self.set_font("Helvetica", "B", 14)
            self.set_text_color(15, 23, 42)
            self.cell(0, 10, "Genie Conversation Export", align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_font("Helvetica", "", 8)
            self.set_text_color(100, 116, 139)
            self.cell(0, 5, datetime.now().strftime("%Y-%m-%d %H:%M"), align="C", new_x="LMARGIN", new_y="NEXT")
            self.ln(4)

        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(148, 163, 184)
            self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    pdf = _PDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    page_w = pdf.w - pdf.l_margin - pdf.r_margin
    bubble_w = page_w * 0.78
    gutter = 4

    for msg in history:
        role = msg.get("role", "assistant")
        raw = msg.get("content", "")
        text = clean_thought_markers(raw) if role == "assistant" else raw
        text = text.replace("**", "").replace("__", "")
        # Sanitise characters unsupported by Helvetica (Latin-1 only)
        _replacements = {
            "\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
            "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u2022": "*",
            "\u2011": "-", "\u00a0": " ", "\u200b": "", "\u2009": " ",
            "\u25cf": "*", "\u25cb": "o", "\u25a0": "#", "\u25a1": "o",
            "\u2192": "->", "\u2190": "<-", "\u2191": "^", "\u2193": "v",
            "\u2605": "*", "\u2606": "*", "\u2713": "v", "\u2717": "x",
        }
        for _uc, _asc in _replacements.items():
            text = text.replace(_uc, _asc)
        # Strip any remaining non-Latin-1 characters
        text = text.encode("latin-1", errors="replace").decode("latin-1")
        is_user = role == "user"

        pdf.set_font("Helvetica", "B", 8)
        if is_user:
            pdf.set_text_color(99, 102, 241)
            pdf.set_x(pdf.w - pdf.r_margin - bubble_w - gutter)
            pdf.cell(bubble_w, 5, "You", align="R", new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.set_text_color(255, 91, 31)
            pdf.set_x(pdf.l_margin + gutter)
            pdf.cell(bubble_w, 5, "Genie", align="L", new_x="LMARGIN", new_y="NEXT")

        y_before = pdf.get_y()
        x_start = (pdf.w - pdf.r_margin - bubble_w - gutter) if is_user else (pdf.l_margin + gutter)

        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(30, 41, 59)
        pdf.set_x(x_start + 4)
        text_h = pdf.multi_cell(bubble_w - 8, 4.5, text, align="L", dry_run=True, output="HEIGHT")
        needed = text_h + 8

        if pdf.get_y() + needed > pdf.h - 20:
            pdf.add_page()
            y_before = pdf.get_y()

        if is_user:
            pdf.set_fill_color(238, 242, 255)
        else:
            pdf.set_fill_color(255, 247, 237)
        pdf.rect(x_start, y_before, bubble_w, needed, style="F")

        pdf.set_xy(x_start + 4, y_before + 4)
        pdf.multi_cell(bubble_w - 8, 4.5, text, align="L")
        pdf.ln(6)

    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()


def _build_chat_markdown(history: list[dict]) -> str:
    lines = [
        "# Genie Conversation Export\n",
        f"*{datetime.now().strftime('%Y-%m-%d %H:%M')}*\n",
    ]
    for msg in history:
        role = msg.get("role", "assistant")
        content = msg.get("content", "")
        if role == "user":
            lines.append(f"### You\n{content}\n")
        else:
            lines.append(f"### Genie\n{clean_thought_markers(content)}\n")
    return "\n".join(lines)


# ── Main render ─────────────────────────────────────────────────────────────

def render_enhanced_chat_interface(dashboard_state: dict = None, on_new_response=None):
    st.markdown("<div id='genie-chat-section'></div>", unsafe_allow_html=True)
    st.markdown(
        "<h3 style='margin-bottom:0.5rem;'>Ask the Genie</h3>"
        "<p style='color:#64748B; font-size:0.9rem; margin-bottom:1rem;'>"
        "Select questions & signals above to queue them on the map, "
        "then press <b style='color:#ff5b1f;'>Start Genie Thoughts</b> — "
        "or type your own question below.</p>",
        unsafe_allow_html=True,
    )

    if "genie_history" not in st.session_state:
        st.session_state["genie_history"] = []

    # ── Handle prefill_message from other pages (e.g. Earnings) ──
    _external_prefill = st.session_state.pop("prefill_message", None)
    if _external_prefill:
        from utils.thought_map import add_queued_node
        add_queued_node(_external_prefill, source_type="cross-page")

    # ── Show queued items count ──
    queued = get_queued_nodes()
    pending_notes = get_pending_human_notes()
    if queued:
        _items_html = ""
        for q in queued[:4]:
            _txt = html.escape(str(q.get("content", ""))[:120])
            _items_html += (
                f"<div style='background:rgba(255,91,31,0.05);border:1px solid rgba(255,91,31,0.2);"
                f"border-radius:8px;padding:6px 10px;margin-top:6px;font-size:0.82rem;"
                f"color:#1e293b;line-height:1.4;'>{_txt}</div>"
            )
        _more = f"<div style='color:#64748B;font-size:0.75rem;margin-top:4px;'>+{len(queued) - 4} more queued</div>" if len(queued) > 4 else ""
        st.markdown(
            f"<div style='background:rgba(255,91,31,0.06);border:1px solid rgba(255,91,31,0.25);"
            f"border-radius:12px;padding:10px 14px;margin-bottom:0.8rem;'>"
            f"<strong style='color:#ff8c42;font-size:0.9rem;'>"
            f"&#x1F7E0; {len(queued)} queued on map</strong>"
            f"{_items_html}{_more}</div>",
            unsafe_allow_html=True,
        )
    if pending_notes:
        _note_items_html = ""
        for note in pending_notes[:3]:
            _txt = html.escape(str(note.get("content", ""))[:120])
            _note_items_html += (
                f"<div style='background:rgba(255,255,255,0.06);border:1px solid rgba(139,92,246,0.2);"
                f"border-radius:8px;padding:6px 10px;margin-top:6px;font-size:0.82rem;"
                f"color:#CBD5E1;line-height:1.4;'>{_txt}</div>"
            )
        _note_more = (
            f"<div style='color:#64748B;font-size:0.75rem;margin-top:4px;'>"
            f"+{len(pending_notes) - 3} more pending note{'s' if len(pending_notes) - 3 != 1 else ''}</div>"
        ) if len(pending_notes) > 3 else ""
        st.markdown(
            f"<div style='background:rgba(139,92,246,0.06);border:1px solid rgba(139,92,246,0.24);"
            f"border-radius:12px;padding:10px 14px;margin-bottom:0.8rem;'>"
            f"<strong style='color:#c4b5fd;font-size:0.9rem;'>"
            f"&#x1F4AC; {len(pending_notes)} note{'s' if len(pending_notes) != 1 else ''} waiting for Genie</strong>"
            f"{_note_items_html}{_note_more}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("""<style>
    .genie-start-btn div[data-testid="stButton"] > button {
        background: linear-gradient(135deg, #ff5b1f 0%, #ff8c42 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        font-size: 0.95rem !important;
        font-weight: 700 !important;
        padding: 0.6rem 1.5rem !important;
        letter-spacing: 0.02em !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 3px 12px rgba(255,91,31,0.25) !important;
        background-image: none !important;
    }
    .genie-start-btn div[data-testid="stButton"] > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(255,91,31,0.35) !important;
        background-image: none !important;
    }
    .genie-start-btn div[data-testid="stButton"] > button:active,
    .genie-start-btn div[data-testid="stButton"] > button:focus {
        background: linear-gradient(135deg, #ff5b1f 0%, #ff8c42 100%) !important;
        background-image: none !important;
    }
    /* Chat input — white bg, dark text, visible placeholder */
    div[data-testid="stChatInput"] textarea,
    div[data-testid="stChatInput"] input,
    [data-testid="stChatInput"] textarea,
    [data-testid="stChatInput"] input,
    [data-testid="stChatInputTextArea"] textarea {
        color: #1e293b !important;
        background-color: #ffffff !important;
        -webkit-text-fill-color: #1e293b !important;
        caret-color: #1e293b !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 10px !important;
    }
    div[data-testid="stChatInput"] textarea::placeholder,
    div[data-testid="stChatInput"] input::placeholder,
    [data-testid="stChatInput"] textarea::placeholder,
    [data-testid="stChatInput"] input::placeholder,
    [data-testid="stChatInputTextArea"] textarea::placeholder {
        color: #94a3b8 !important;
        opacity: 1 !important;
        -webkit-text-fill-color: #94a3b8 !important;
    }
    /* Chat input container background */
    [data-testid="stChatInput"],
    [data-testid="stBottom"] > div {
        background-color: transparent !important;
    }
    </style>""", unsafe_allow_html=True)

    # ── CTA + unified export ──
    _cta_col, _export_col = st.columns([3, 1])
    with _cta_col:
        st.markdown('<div class="genie-start-btn">', unsafe_allow_html=True)
        _pending_prompt_count = len(queued) + len(pending_notes)
        _btn_label = f"Start Genie Thoughts ({_pending_prompt_count})" if _pending_prompt_count else "Start Genie Thoughts"
        _start_clicked = st.button(
            _btn_label,
            key="start_genie_thoughts_btn",
            use_container_width=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)
    with _export_col:
        history = st.session_state.get("genie_history", [])
        if history:
            # Build format list — only include PDF if fpdf2 is available
            _formats = ["Markdown", "JSON"]
            if _HAS_FPDF:
                _formats.insert(0, "PDF")
            _fmt = st.selectbox(
                "Export format",
                _formats,
                key="chat_export_format",
                label_visibility="collapsed",
            )
            if _fmt == "PDF":
                _data = _build_chat_pdf(history)
                _fname = f"genie_chat_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                _mime = "application/pdf"
            elif _fmt == "Markdown":
                _data = _build_chat_markdown(history)
                _fname = f"genie_chat_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
                _mime = "text/markdown"
            else:
                _data = json.dumps(history, indent=2, default=str)
                _fname = f"genie_chat_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
                _mime = "application/json"
            st.download_button(
                f"Export Chat ({_fmt})",
                data=_data,
                file_name=_fname,
                mime=_mime,
                key="export_chat_btn",
            )

    # Display conversation history
    for message in history:
        role = message.get("role", "assistant")
        content = message.get("content", "")
        avatar = "🧞" if role == "assistant" else "👤"
        with st.chat_message(role, avatar=avatar):
            st.markdown(clean_thought_markers(content) if role == "assistant" else content)

    user_input = st.chat_input(
        "Ask about revenue trends, ad market share, transcript quotes...",
        key="genie_chat_input",
    )

    # "Start Genie Thoughts" collects queued map nodes into a combined prompt
    _consumed_thought_map_notes: list[str] = []
    _notes_injected_into_user_input = False
    if _start_clicked and (queued or pending_notes):
        queued_texts = promote_queued_nodes() if queued else []
        _consumed_thought_map_notes = consume_pending_human_notes() if pending_notes else []
        _combined_prompt = ""
        if len(queued_texts) == 1:
            _combined_prompt = queued_texts[0]
        elif len(queued_texts) > 1:
            _combined_prompt = (
                "I've selected these topics to reason about together:\n\n"
                + "\n".join(f"- {t}" for t in queued_texts)
                + "\n\nPlease analyze each point and connect them where relevant."
            )
        if _consumed_thought_map_notes:
            _notes_block = _format_note_lines(_consumed_thought_map_notes)
            if _combined_prompt:
                user_input = (
                    f"{_combined_prompt}\n\n"
                    "Also incorporate these explicit thought map notes:\n"
                    f"{_notes_block}"
                )
            else:
                user_input = (
                    "Please reason through these explicit thought map notes and use them in the answer:\n\n"
                    f"{_notes_block}"
                )
            _notes_injected_into_user_input = True
        else:
            user_input = _combined_prompt

    if user_input:
        if not _consumed_thought_map_notes:
            _consumed_thought_map_notes = consume_pending_human_notes()

        effective_user_input = str(user_input).strip()
        if _consumed_thought_map_notes and not _notes_injected_into_user_input:
            effective_user_input = (
                f"{effective_user_input}\n\n"
                "Also incorporate these explicit thought map notes:\n"
                f"{_format_note_lines(_consumed_thought_map_notes)}"
            ).strip()

        with st.chat_message("user", avatar="👤"):
            st.markdown(effective_user_input)

        st.session_state["genie_history"].append({
            "role": "user",
            "content": effective_user_input,
        })

        runtime_state = dict(dashboard_state or {})
        if _consumed_thought_map_notes:
            runtime_state["thought_map_user_notes"] = _consumed_thought_map_notes
        transcript_context = build_query_transcript_context(effective_user_input, runtime_state)
        if transcript_context:
            runtime_state["matched_transcript_context"] = transcript_context

        messages = build_genie_messages(
            conversation_history=st.session_state["genie_history"][:-1],
            dashboard_state=runtime_state,
            user_message=effective_user_input,
        )

        msg_index = len(st.session_state["genie_history"]) - 1
        response = stream_genie_response(messages)

        st.session_state["genie_history"].append({
            "role": "assistant",
            "content": response,
        })

        parent_node_id = st.session_state.pop("pending_elaboration_node_id", None)
        new_nodes = parse_response_to_nodes(response, msg_index)
        add_nodes_to_map(new_nodes, parent_node_id=parent_node_id)

        if on_new_response:
            on_new_response(response, msg_index)

        st.rerun()

    history = st.session_state.get("genie_history", [])
    if history:
        approx_tokens = _estimate_token_usage(history)
        if approx_tokens >= 120000:
            st.warning("Conversation is getting long. Consider clearing if responses slow down.")


__all__ = ["render_enhanced_chat_interface"]
