import json

import streamlit as st

from ai_powered_qa.components.agent_store import AgentStore
from ai_powered_qa.components.agent import AVAILABLE_MODELS
from ai_powered_qa.custom_plugins.playwright_plugin.base import PlaywrightPlugin
from ai_powered_qa.custom_plugins.playwright_plugin.html_paging import (
    PlaywrightPluginHtmlPaging,
)
from ai_powered_qa.custom_plugins.playwright_plugin.only_visible import (
    PlaywrightPluginOnlyVisible,
)

DEFAULT_PLAYWRIGHT_PLUGIN = "PlaywrightPluginOnlyVisible"

SYSTEM_MESSAGE_KEY = "agent_system_message"
HISTORY_NAME_KEY = "history_name"
AGENT_NAME_KEY = "agent_name"
AGENT_MODEL_KEY = "agent_model"
TOOL_CALL_KEY = "tool_call"


NAME_TO_PLUGIN_CLASS = {
    "PlaywrightPlugin": PlaywrightPlugin,
    "PlaywrightPluginHtmlPaging": PlaywrightPluginHtmlPaging,
    "PlaywrightPluginOnlyVisible": PlaywrightPluginOnlyVisible,
}

agent_store = AgentStore("agents", name_to_plugin_class=NAME_TO_PLUGIN_CLASS)


sidebar = st.sidebar


def load_agent():
    _agent_name = st.session_state[AGENT_NAME_KEY]
    _agent = agent_store.load_agent(
        _agent_name,
        default_kwargs={
            "plugins": {
                DEFAULT_PLAYWRIGHT_PLUGIN: NAME_TO_PLUGIN_CLASS[
                    DEFAULT_PLAYWRIGHT_PLUGIN
                ]()
            }
        },
    )
    st.session_state["agent_instance"] = _agent
    st.session_state[AGENT_MODEL_KEY] = _agent.model
    st.session_state[SYSTEM_MESSAGE_KEY] = _agent.system_message


agent_name = sidebar.text_input(
    "Agent name", value="test_agent", key=AGENT_NAME_KEY, on_change=load_agent
)

if not "agent_instance" in st.session_state:
    load_agent()

agent = st.session_state["agent_instance"]


def on_commit(interaction):
    # Clear the user message content
    st.session_state["user_message_content"] = None
    # Use the agent message content that could be modified by the user
    interaction.agent_response.content = st.session_state["agent_message_content"]
    # and clear it from state
    st.session_state["agent_message_content"] = None

    # Use the tool calls that could be modified by the user and clear them from state
    if interaction.agent_response.tool_calls:
        for tool_call in interaction.agent_response.tool_calls:
            tool_call.function.name = st.session_state[f"{tool_call.id}_name"]
            del st.session_state[f"{tool_call.id}_name"]
            tool_call.function.arguments = st.session_state[f"{tool_call.id}_arguments"]
            del st.session_state[f"{tool_call.id}_arguments"]

    agent_store.save_interaction(
        agent, agent.commit_interaction(interaction=interaction)
    )
    agent_store.save_history(agent)

    # Reset agent model after commit to save money
    #  (you need to explicitly request the more expensive models)
    st.session_state[AGENT_MODEL_KEY] = AVAILABLE_MODELS[0]
    # Reset tool call back to 'auto' (not often you want the same tool call again)
    st.session_state[TOOL_CALL_KEY] = "auto"


agent.model = sidebar.selectbox("Model", AVAILABLE_MODELS, key=AGENT_MODEL_KEY)
agent.system_message = sidebar.text_area("System message", key=SYSTEM_MESSAGE_KEY)
generate_empty = sidebar.checkbox(
    "Generate interaction even if user message is empty", False
)
agent_store.save_agent(agent)


def load_history():
    if HISTORY_NAME_KEY not in st.session_state:
        return

    history_name = st.session_state[HISTORY_NAME_KEY]
    if not history_name:
        return

    history = agent_store.load_history(agent, history_name)
    agent.reset_history(history, history_name)


history_name = st.text_input(
    "History name", key=HISTORY_NAME_KEY, on_change=load_history
)

if not history_name:
    st.stop()


def on_clear_history():
    history_name = st.session_state[HISTORY_NAME_KEY]
    agent.reset_history([], history_name)
    agent_store.save_history(agent)


if len(agent.history) > 0:
    st.button("Clear history", on_click=on_clear_history)

for message in agent.history:
    with st.chat_message(message["role"]):
        if message["content"]:
            st.write(message["content"])
        if "tool_calls" in message:
            for tool_call in message["tool_calls"]:
                with st.status(tool_call["function"]["name"], state="complete"):
                    st.write(json.loads(tool_call["function"]["arguments"]))


last_message = None
if agent.history:
    last_message = agent.history[-1]

user_message_content = None

available_tools = agent.get_tools_from_plugins()
available_tool_names = [tool["function"]["name"] for tool in available_tools]

tool_call = st.selectbox(
    "Tool call",
    ["auto", "none"] + available_tool_names,
    key=TOOL_CALL_KEY,
)

# User message
if last_message is None or last_message["role"] == "assistant":
    with st.chat_message("user"):
        user_message_content = st.text_area(
            "User message content",
            key="user_message_content",
            label_visibility="collapsed",
        )
        if not user_message_content and not generate_empty:
            st.stop()

try:
    interaction = agent.generate_interaction(
        user_message_content, tool_choice=tool_call
    )
except Exception as e:
    st.write(e)
    st.stop()

context_message = (
    interaction.request_params["messages"][-2]
    if interaction.user_prompt
    else interaction.request_params["messages"][-1]
)


with st.chat_message("user"):
    st.write("**Cotext message**")
    st.write(context_message["content"])
    st.image(agent.plugins[DEFAULT_PLAYWRIGHT_PLUGIN].buffer)

agent_store.save_interaction(agent, interaction)

agent_response = interaction.agent_response.model_dump()

st.session_state["agent_message_content"] = agent_response["content"]
tool_calls = (
    {
        tool_call["id"]: tool_call["function"]
        for tool_call in agent_response["tool_calls"]
    }
    if agent_response["tool_calls"]
    else {}
)
st.session_state["agent_tool_calls"] = tool_calls
for tool_id, tool_info in tool_calls.items():
    st.session_state[f"{tool_id}_name"] = tool_info["name"]
    st.session_state[f"{tool_id}_arguments"] = tool_info["arguments"]

with st.chat_message("assistant"):
    with st.form("agent_message"):
        st.text_area(
            "Content",
            key="agent_message_content",
        )
        for tool_id, tool_info in tool_calls.items():
            st.text_input(
                f"{tool_info['name']} arguments",
                key=f"{tool_id}_arguments",
            )
        st.form_submit_button(
            "Commit agent completion",
            on_click=on_commit,
            args=(interaction,),
        )
