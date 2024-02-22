import streamlit as st
from ai_powered_qa.components.agent import AVAILABLE_MODELS

from ai_powered_qa.components.agent import Agent
from ai_powered_qa.components.agent_store import AgentStore
from ai_powered_qa.custom_plugins.playwright_plugin import PlaywrightPlugin
from ai_powered_qa.custom_plugins.planning_plugin import PlanningPlugin
from ai_powered_qa.ui_common.constants import (
    AGENT_INSTANCE_KEY,
    AGENT_MODEL_KEY,
    AGENT_NAME_KEY,
    SYSTEM_MESSAGE_KEY,
)


def load_agent(st: st, default_kwargs: dict) -> (Agent, AgentStore):
    agent_store = AgentStore(
        "agents",
        name_to_plugin_class={
            "PlaywrightPlugin": PlaywrightPlugin,
            "PlanningPlugin": PlanningPlugin,
        },
    )

    sidebar = st.sidebar

    agent_name = sidebar.text_input(
        "Agent name", value="test_agent", key=AGENT_NAME_KEY, on_change=load_agent
    )

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

    # TODO: Make generate_empty an Agent field
    generate_empty = sidebar.checkbox(
        "Generate interaction even if user message is empty", False
    )

    agent_store.save_agent(agent)

    return agent, agent_store
