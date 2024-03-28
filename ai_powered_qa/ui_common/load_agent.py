import streamlit as st

from ai_powered_qa.components.agent import Agent, AVAILABLE_MODELS
from ai_powered_qa.components.agent_store import AgentStore
from ai_powered_qa.custom_plugins.playwright_plugin.base import PlaywrightPlugin
from ai_powered_qa.custom_plugins.playwright_plugin.html_paging import (
    PlaywrightPluginHtmlPaging,
)
from ai_powered_qa.custom_plugins.playwright_plugin.only_visible import (
    PlaywrightPluginOnlyVisible,
)
from ai_powered_qa.custom_plugins.playwright_plugin.only_keyboard import (
    PlaywrightPluginOnlyKeyboard,
)
from ai_powered_qa.ui_common.constants import (
    AGENT_INSTANCE_KEY,
    AGENT_MODEL_KEY,
    AGENT_NAME_KEY,
    HISTORY_NAME_KEY,
    SYSTEM_MESSAGE_KEY,
    USER_MESSAGE_CONTENT_KEY,
)
from .load_history import reset_history

NAME_TO_PLUGIN_CLASS = {
    "PlaywrightPlugin": PlaywrightPlugin,
    "PlaywrightPluginHtmlPaging": PlaywrightPluginHtmlPaging,
    "PlaywrightPluginOnlyVisible": PlaywrightPluginOnlyVisible,
    "PlaywrightPluginOnlyKeyboard": PlaywrightPluginOnlyKeyboard,
}


def clear_agent_state(agent_store: AgentStore):
    agent = st.session_state[AGENT_INSTANCE_KEY]
    if agent:
        reset_history(agent, agent_store)
    st.session_state.pop(AGENT_INSTANCE_KEY, None)
    st.session_state[HISTORY_NAME_KEY] = ""
    st.session_state[USER_MESSAGE_CONTENT_KEY] = ""


def load_agent(default_kwargs: dict) -> tuple[Agent, AgentStore]:
    agent_store = AgentStore(
        "agents",
        name_to_plugin_class=NAME_TO_PLUGIN_CLASS,
    )

    sidebar = st.sidebar

    agent_name = sidebar.text_input(
        "Agent name",
        value="test_agent",
        key=AGENT_NAME_KEY,
        # Remove the cached instance of the agent, so it gets reloaded
        on_change=clear_agent_state,
        args=(agent_store,),
    )

    sidebar.button("Reload agent", on_click=clear_agent_state, args=(agent_store,))

    if not "agent_instance" in st.session_state:
        _agent = agent_store.load_agent(
            agent_name,
            default_kwargs=default_kwargs,
        )
        st.session_state[AGENT_INSTANCE_KEY] = _agent
        st.session_state[AGENT_MODEL_KEY] = _agent.model
        st.session_state[SYSTEM_MESSAGE_KEY] = _agent.system_message

    agent = st.session_state[AGENT_INSTANCE_KEY]

    agent.model = sidebar.selectbox("Model", AVAILABLE_MODELS, key=AGENT_MODEL_KEY)
    agent.system_message = sidebar.text_area("System message", key=SYSTEM_MESSAGE_KEY)

    agent_store.save_agent(agent)

    return agent, agent_store
