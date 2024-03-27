import streamlit as st

from ai_powered_qa.ui_common.constants import (
    HISTORY_NAME_KEY,
    INTERACTION_INSTANCE_KEY,
    USER_MESSAGE_CONTENT_KEY,
)


def _clear_interaction():
    st.session_state[USER_MESSAGE_CONTENT_KEY] = ""
    if INTERACTION_INSTANCE_KEY in st.session_state:
        del st.session_state[INTERACTION_INSTANCE_KEY]


def _on_change_history_name(agent, agent_store):
    _clear_interaction()
    if HISTORY_NAME_KEY not in st.session_state:
        return

    history_name = st.session_state[HISTORY_NAME_KEY]
    if not history_name:
        return

    history = agent_store.load_history(agent, history_name)
    agent.reset_history(history, history_name)


def reset_history(agent, agent_store):
    _on_change_history_name(agent, agent_store)


def _on_clear_history(agent, agent_store):
    _clear_interaction()
    history_name = st.session_state[HISTORY_NAME_KEY]
    agent.reset_history([], history_name)
    agent_store.save_history(agent)


def load_history(agent, agent_store):
    history_name = st.text_input(
        "History name",
        key=HISTORY_NAME_KEY,
        on_change=_on_change_history_name,
        args=(agent, agent_store),
    )

    if not history_name:
        return None

    if len(agent.history) > 0:
        st.button(
            "Clear history", on_click=_on_clear_history, args=(agent, agent_store)
        )

    return history_name
