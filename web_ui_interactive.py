import json
from PIL import Image
from io import BytesIO


import numpy as np
from openai.types.chat.chat_completion_message import ChatCompletionMessageToolCall
import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates


from ai_powered_qa.components.agent_store import AgentStore
from ai_powered_qa.components.agent import AVAILABLE_MODELS
from ai_powered_qa.components.utils import generate_short_id
from ai_powered_qa.custom_plugins.playwright_plugin import PlaywrightPlugin
from ai_powered_qa.custom_plugins.planning_plugin import PlanningPlugin
from ai_powered_qa.ui_common.constants import (
    AGENT_MODEL_KEY,
    AGENT_TOOL_CALLS_KEY,
    INTERACTION_INSTANCE_KEY,
    TOOL_CALL_KEY,
    USER_MESSAGE_CONTENT_KEY,
)
from ai_powered_qa.ui_common.load_agent import load_agent
from ai_powered_qa.ui_common.load_history import load_history

# HTML style tag with custom styles
st.write(
    """
    <style>
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

agent, agent_store = load_agent(
    default_kwargs={"plugins": {"PlaywrightPlugin": PlaywrightPlugin()}}
)

history_name = load_history(agent, agent_store)

st.write(st.session_state)


def on_commit(value):
    st.session_state[USER_MESSAGE_CONTENT_KEY] = None
    del st.session_state[INTERACTION_INSTANCE_KEY]
    # Reset agent model after commit to save money
    #  (you need to explicitly request the more expensive models)
    st.session_state[AGENT_MODEL_KEY] = AVAILABLE_MODELS[0]
    # Reset tool call back to 'auto' (not often you want the same tool call again)
    st.session_state[TOOL_CALL_KEY] = "auto"
    # TODO: clear tool calls
    agent.commit_interaction(interaction=value)


# def on_commit(interaction):
#     # Clear the user message content
#     st.session_state["user_message_content"] = None
#     # Use the agent message content that could be modified by the user
#     interaction.agent_response.content = st.session_state["agent_message_content"]
#     # and clear it from state
#     st.session_state["agent_message_content"] = None

#     # Use the tool calls that could be modified by the user and clear them from state
#     if interaction.agent_response.tool_calls:
#         for tool_call in interaction.agent_response.tool_calls:
#             tool_call.function.name = st.session_state[f"{tool_call.id}_name"]
#             del st.session_state[f"{tool_call.id}_name"]
#             tool_call.function.arguments = st.session_state[f"{tool_call.id}_arguments"]
#             del st.session_state[f"{tool_call.id}_arguments"]

#     agent_store.save_interaction(
#         agent, agent.commit_interaction(interaction=interaction)
#     )
#     agent_store.save_history(agent)

#     # Reset agent model after commit to save money
#     #  (you need to explicitly request the more expensive models)
#     st.session_state[AGENT_MODEL_KEY] = AVAILABLE_MODELS[0]
#     # Reset tool call back to 'auto' (not often you want the same tool call again)
#     st.session_state[TOOL_CALL_KEY] = "auto"


if not history_name:
    st.stop()

available_tools = agent.get_tools_from_plugins()
available_tool_names = [tool["function"]["name"] for tool in available_tools]


def generate_interaction():
    user_message_content = st.session_state[USER_MESSAGE_CONTENT_KEY]

    tool_call = st.session_state[TOOL_CALL_KEY]

    _interaction = agent.generate_interaction(
        user_message_content, tool_choice=tool_call
    )
    st.session_state[INTERACTION_INSTANCE_KEY] = _interaction
    agent_store.save_interaction(agent, _interaction)


# Set default values for the tool call and user message content
if TOOL_CALL_KEY not in st.session_state:
    st.session_state[TOOL_CALL_KEY] = "auto"
if USER_MESSAGE_CONTENT_KEY not in st.session_state:
    st.session_state[USER_MESSAGE_CONTENT_KEY] = ""

# Generate interaction if not in session state
if INTERACTION_INSTANCE_KEY not in st.session_state:
    try:
        generate_interaction()
    except Exception as e:
        st.write(e)
        st.stop()

interaction = st.session_state[INTERACTION_INSTANCE_KEY]

interaction_messages = len(interaction.request_params["messages"])

agent_messages = agent.history

st.write(len(agent_messages), interaction_messages)

for i, message in enumerate(agent_messages):
    # TODO: this depends on whether or not the user prompt is present
    if i == len(agent_messages) - interaction_messages + 2:
        st.text("*Interaction messages*")
    with st.chat_message(message["role"]):
        if message["content"]:
            st.write(message["content"])
        if "tool_calls" in message:
            for tool_call in message["tool_calls"]:
                with st.status(tool_call["function"]["name"], state="complete"):
                    st.write(json.loads(tool_call["function"]["arguments"]))


# TODO: test flipping the order of user_prompt vs context_message
context_message = (
    interaction.request_params["messages"][-2]
    if interaction.user_prompt
    else interaction.request_params["messages"][-1]
)


with st.chat_message("user"):
    st.write("**Context message**")
    st.write(context_message["content"])

playwright_plugin = agent.plugins["PlaywrightPlugin"]
buffer = playwright_plugin.buffer
image = Image.open(BytesIO(buffer))
image_array = np.array(image)
width = 1024
coordinates = streamlit_image_coordinates(image_array, width=width)
if coordinates:
    # multiply the coordinates by the ratio of the actual width to the displayed width as integer
    ratio = image.width / width
    coordinates = {k: int(v * ratio) for k, v in coordinates.items()}
    selector = playwright_plugin.get_selector_for_coordinates(**coordinates)
    st.write(coordinates)
    st.session_state["selector"] = selector
    st.text_input("Selector", key="selector", disabled=True)

# Request params UI (will regenerate the interaction)
tool_call = st.selectbox(
    "Tool call",
    ["auto", "none"] + available_tool_names,
    key=TOOL_CALL_KEY,
    on_change=generate_interaction,
)

# TODO: Make this a chat input ?
with st.chat_message("user"):
    user_message_content = st.text_area(
        "User message content",
        key=USER_MESSAGE_CONTENT_KEY,
        label_visibility="collapsed",
        on_change=generate_interaction,
    )

st.button(
    "Regenerate interaction", use_container_width=True, on_click=generate_interaction
)
# END Request params UI

agent_response = interaction.agent_response.model_dump()

# TODO: get rid of the model_dump and iterate the actual response when building the UI
tool_calls = (
    {
        tool_call["id"]: tool_call["function"]
        for tool_call in agent_response["tool_calls"]
    }
    if agent_response["tool_calls"]
    else {}
)

tools = agent.get_tools_from_plugins()

tool_schemas = (
    {tool["function"]["name"]: tool["function"]["parameters"] for tool in tools}
    if tools
    else {}
)

with st.chat_message("assistant"):

    def update_agent_message_content():
        interaction.agent_response.content = st.session_state["agent_message_content"]

    st.session_state["agent_message_content"] = interaction.agent_response.content
    st.text_area(
        "Content",
        key="agent_message_content",
        on_change=update_agent_message_content,
    )

    def update_tool_call(tool_id, param_name):
        param_value = st.session_state[f"{tool_id}_{param_name}"]
        for tool_call in interaction.agent_response.tool_calls:
            if tool_call.id == tool_id:
                original_arguments = json.loads(tool_call.function.arguments)
                original_arguments[param_name] = param_value
                tool_call.function.arguments = json.dumps(original_arguments)

    for tool_id, tool_info in tool_calls.items():
        # st.session_state[f"{tool_id}_name"] = tool_info["name"]
        # st.session_state[f"{tool_id}_arguments"] = tool_info["arguments"]

        tool_name = tool_info["name"]
        st.write(f"**{tool_name}** (id: {tool_id})")

        tool_schema = tool_schemas[tool_name]

        assert tool_schema["type"] == "object"

        arguments = json.loads(tool_info["arguments"])

        for param_name, param_schema in tool_schema["properties"].items():
            st.session_state[f"{tool_id}_{param_name}"] = arguments.get(
                param_name, param_schema.get("default", "")
            )
            st.text_area(
                param_name,
                key=f"{tool_id}_{param_name}",
                on_change=update_tool_call,
                args=(tool_id, param_name),
            )

        # TODO: move definitions to the top of the page
        def remove_tool_call():
            interaction.agent_response.tool_calls = [
                tool_call
                for tool_call in interaction.agent_response.tool_calls
                if tool_call.id != tool_id
            ]

        st.button("Remove", on_click=remove_tool_call, key=f"{tool_id}_remove")

        # st.text_input(
        #     "Arguments",
        #     key=f"{tool_id}_arguments",
        #     on_change=update_tool_call,
        #     args=(tool_id,),
        # )

    with st.form("new_tool_call"):

        def add_tool_call():
            tool_call_id = f"call_{generate_short_id()}"
            tool_call = st.session_state["new_tool_call"]
            if not interaction.agent_response.tool_calls:
                interaction.agent_response.tool_calls = []
            interaction.agent_response.tool_calls.append(
                ChatCompletionMessageToolCall(
                    **{
                        "id": tool_call_id,
                        "function": {
                            "name": tool_call,
                            "arguments": "",
                        },
                        "type": "function",
                    }
                )
            )

        st.selectbox(
            "Add tool call",
            available_tool_names,
            key="new_tool_call",
        )
        st.form_submit_button(
            "Add",
            on_click=add_tool_call,
        )

    st.button("Commit", on_click=on_commit, args=(interaction,))
