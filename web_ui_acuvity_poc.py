import json
from time import sleep

import streamlit as st

from ai_powered_qa.components.agent_store import AgentStore
from ai_powered_qa.ui_common.constants import AGENT_INSTANCE_KEY
from ai_powered_qa.ui_common.load_agent import NAME_TO_PLUGIN_CLASS

st.title("Acuvity POC")

st.write(
    """
    <style>
        pre:has(code.language-html) {
            max-height: 500px;
        }
        iframe { 
            width: 1024px; 
            position: relative; 
            left: 50%; 
            transform: translateX(-50%); 
        }
    </style>
    """,
    unsafe_allow_html=True,
)

agent_store = AgentStore(
    "agents",
    name_to_plugin_class=NAME_TO_PLUGIN_CLASS,
)

agent_name = "acuvity_poc_agent"

playwright_plugin_name = "PlaywrightPluginOnlyVisible"

if not AGENT_INSTANCE_KEY in st.session_state:
    _agent = agent_store.load_agent(
        agent_name,
        default_kwargs={
            "model": "gpt-4o",
            "plugins": {
                playwright_plugin_name: NAME_TO_PLUGIN_CLASS[playwright_plugin_name](),
            },
        },
    )
    st.session_state[AGENT_INSTANCE_KEY] = _agent


agent = st.session_state[AGENT_INSTANCE_KEY]

website_url = st.text_input("Website URL", value="perplexity.ai")

test_scenario = st.text_area(
    "Test scenario",
    value="Verify that when you send a message you get a successful response",
)

if not st.button("Run test scenario"):
    st.stop()


interaction = agent.generate_interaction(
    f"Please go to {website_url} and execute this test scenario:\n{test_scenario}",
)

with st.chat_message("User"):
    st.write(interaction.user_prompt)

with st.chat_message("Assistant"):
    if interaction.agent_response.content:
        st.write(interaction.agent_response.content)
    if interaction.agent_response.tool_calls:
        for tool_call in interaction.agent_response.tool_calls:
            with st.status(tool_call.function.name, state="complete"):
                st.write(json.loads(tool_call.function.arguments))


max_iterations = 15
while (
    max_iterations > 0
    and interaction.agent_response.tool_calls
    and not any(
        tool_call.function.name == "finish"
        for tool_call in interaction.agent_response.tool_calls
    )
):
    max_iterations -= 1
    agent_store.save_interaction(
        agent, agent.commit_interaction(interaction=interaction)
    )

    agent_store.save_history(agent)

    for tool_call in interaction.tool_responses:
        with st.chat_message("Tool Call"):
            st.write(tool_call["content"])

    with st.spinner("Generating next interaction..."):
        sleep(5)
        interaction = agent.generate_interaction()

    with st.chat_message("Assistant"):
        if interaction.agent_response.content:
            st.write(interaction.agent_response.content)
        if interaction.agent_response.tool_calls:
            for tool_call in interaction.agent_response.tool_calls:
                with st.status(tool_call.function.name, state="complete"):
                    st.write(json.loads(tool_call.function.arguments))
