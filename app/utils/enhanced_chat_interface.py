"""Enhanced Genie chat UI wired to OpenAI + Thought Map."""

import streamlit as st

from utils.genie_ai import (
    build_genie_messages,
    build_query_transcript_context,
    stream_genie_response,
)
from utils.thought_map import add_nodes_to_map, parse_response_to_nodes


def _estimate_token_usage(history: list[dict]) -> int:
    """
    Rough token estimate for warning purposes.
    Uses ~4 chars/token heuristic.
    """
    total_chars = 0
    for message in history:
        total_chars += len(str(message.get("content", "")))
    return total_chars // 4


def render_enhanced_chat_interface(dashboard_state: dict = None, on_new_response=None):
    """
    Full Genie chat interface with OpenAI streaming and thought-map integration.
    """
    st.markdown("<div id='genie-chat-section'></div>", unsafe_allow_html=True)
    st.markdown(
        "<h3 style='margin-bottom:0.5rem;'>🧞 Ask the Genie</h3>"
        "<p style='color:#64748B; font-size:0.9rem; margin-bottom:1.5rem;'>"
        "Ask anything about the data — company performance, advertising trends, "
        "transcript quotes, macro context, or competitive analysis.</p>",
        unsafe_allow_html=True,
    )

    if "genie_history" not in st.session_state:
        st.session_state["genie_history"] = []

    history = st.session_state.get("genie_history", [])
    for message in history:
        role = message.get("role", "assistant")
        content = message.get("content", "")
        avatar = "🧞" if role == "assistant" else "👤"
        with st.chat_message(role, avatar=avatar):
            st.markdown(content)

    prefill = st.session_state.pop("prefill_message", None)
    user_input = st.chat_input(
        "Ask about revenue trends, ad market share, transcript quotes...",
        key="genie_chat_input",
    )

    if prefill and not user_input:
        user_input = prefill

    if user_input:
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)

        st.session_state["genie_history"].append({
            "role": "user",
            "content": user_input,
        })

        runtime_state = dict(dashboard_state or {})
        transcript_context = build_query_transcript_context(user_input, runtime_state)
        if transcript_context:
            runtime_state["matched_transcript_context"] = transcript_context

        messages = build_genie_messages(
            conversation_history=st.session_state["genie_history"][:-1],
            dashboard_state=runtime_state,
            user_message=user_input,
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
            st.warning("⚠️ Conversation is getting long. Consider clearing if responses slow down.")

        col1, col2 = st.columns([1, 4])
        with col1:
            history_text = "\n\n".join([
                f"**{m.get('role', '').upper()}:** {m.get('content', '')}"
                for m in history
            ])
            st.download_button(
                "⬇ Export Chat",
                data=history_text,
                file_name="genie_conversation.md",
                mime="text/markdown",
                key="export_chat_btn",
            )


__all__ = ["render_enhanced_chat_interface"]
