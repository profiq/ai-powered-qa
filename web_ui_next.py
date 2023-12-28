import streamlit as st

from ai_powered_qa.components.agent import Agent


def on_commit(interaction):
    st.session_state["user_message_content"] = None
    interaction.agent_response.content = st.session_state["agent_message_content"]
    agent.commit_interaction(interaction=interaction)


agent_name = st.text_input("Agent name", value="test_agent")


@st.cache_resource
def get_agent(agent_name):
    return Agent(agent_name=agent_name)


agent = get_agent(agent_name)


system_message_key = "agent_system_message"
if not system_message_key in st.session_state:
    st.session_state[system_message_key] = agent.system_message
agent.system_message = st.text_input("System message", key="agent_system_message")


for message in agent.history:
    with st.chat_message(message["role"]):
        st.write(message["content"])


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

st.session_state["agent_message_content"] = interaction.agent_response.content

with st.chat_message("assistant"):
    with st.form("agent_message"):
        st.text_area(
            "Content",
            key="agent_message_content",
        )
        st.form_submit_button(
            "Commit agent completion",
            on_click=on_commit,
            args=(interaction,),
        )
