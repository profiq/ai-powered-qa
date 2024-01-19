import json

import streamlit as st

from ai_powered_qa.components.agent_store import AgentStore
from ai_powered_qa.components.agent import AVAILABLE_MODELS
from ai_powered_qa.custom_plugins.playwright_plugin import PlaywrightPlugin

SYSTEM_MESSAGE_KEY = "agent_system_message"
HISTORY_NAME_KEY = "history_name"


@st.cache_resource
def get_agent_store():
    return AgentStore(
        "agents",
        name_to_plugin_class={
            "PlaywrightPlugin": PlaywrightPlugin,
        },
    )


agent_store = get_agent_store()


@st.cache_resource
def get_agent(agent_name):
    new_agent = agent_store.load_agent(
        agent_name, default_kwargs={"plugins": {"PlaywrightPlugin": PlaywrightPlugin()}}
    )
    st.session_state[SYSTEM_MESSAGE_KEY] = new_agent.system_message
    return new_agent


sidebar = st.sidebar

agent_name = sidebar.text_input("Agent name", value="test_agent")
agent = get_agent(agent_name)


def on_commit(interaction):
    st.session_state["user_message_content"] = None
    interaction.agent_response.content = st.session_state["agent_message_content"]
    st.session_state["agent_message_content"] = None
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


agent.model = sidebar.selectbox("Model", AVAILABLE_MODELS)
agent.system_message = sidebar.text_area("System message", agent.system_message)
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
    st.text_area(
        "Context message", context_message["content"], height=200, disabled=True
    )
    st.image(agent.plugins["PlaywrightPlugin"].buffer)

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
