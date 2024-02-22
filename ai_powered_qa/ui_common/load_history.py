import streamlit as st

from ai_powered_qa.ui_common.constants import HISTORY_NAME_KEY


def _on_change_history_name(st: st, agent, agent_store):
    if HISTORY_NAME_KEY not in st.session_state:
        return

    history_name = st.session_state[HISTORY_NAME_KEY]
    if not history_name:
        return

    history = agent_store.load_history(agent, history_name)
    agent.reset_history(history, history_name)


def _on_clear_history(st: st, agent, agent_store):
    history_name = st.session_state[HISTORY_NAME_KEY]
    agent.reset_history([], history_name)
    agent_store.save_history(agent)


def load_history(st: st, agent, agent_store):
    history_name = st.text_input(
        "History name",
        key=HISTORY_NAME_KEY,
        on_change=_on_change_history_name,
        args=(st, agent, agent_store),
    )

    if not history_name:
        return None

    if len(agent.history) > 0:
        st.button(
            "Clear history", on_click=_on_clear_history, args=(st, agent, agent_store)
        )

    return history_name
