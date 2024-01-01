import json
import streamlit as st

from ai_powered_qa.components.agent import Agent
from ai_powered_qa.components.agent_store import AgentStore
from ai_powered_qa.custom_plugins.playwright_plugin import PlaywrightPlugin

SYSTEM_MESSAGE_KEY = "agent_system_message"


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

    agent.commit_interaction(interaction=interaction)


agent_name = st.text_input("Agent name", value="test_agent")


@st.cache_resource
def get_agent_store():
    return AgentStore("agents")


agent_store = get_agent_store()


@st.cache_resource
def get_agent(agent_name):
    new_agent = agent_store.load_agent(
        agent_name, default_kwargs={"plugins": {"PlaywrightPlugin": PlaywrightPlugin()}}
    )
    st.session_state[SYSTEM_MESSAGE_KEY] = new_agent.system_message
    return new_agent


agent = get_agent(agent_name)

st.write(agent)

agent.system_message = st.text_input("System message", key="agent_system_message")

st.write(agent.model_dump())

agent_store.save_agent(agent)


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

# User message
if last_message is None or last_message["role"] == "assistant":
    with st.chat_message("user"):
        user_message_content = st.text_area(
            "User message content",
            key="user_message_content",
            label_visibility="collapsed",
        )
        if not user_message_content:
            st.stop()


interaction = agent.generate_interaction(user_message_content)

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
