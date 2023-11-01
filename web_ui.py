import asyncio
import datetime
import json
import os

import streamlit as st
from dotenv import load_dotenv
from langchain.tools.convert_to_openai import format_tool_to_openai_function
from streamlit.errors import DuplicateWidgetID

import components.context_message
from components.constants import llm_models, function_call_defaults
from components.function_caller import get_browser, get_tools, call_function

from chat_model import ProfiqDevAIConfig, ChatCompletionInputs, ProfiqDevAI
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

load_dotenv()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "browser" not in st.session_state:
    st.session_state.browser = None
if "loop" not in st.session_state:
    st.session_state.loop = asyncio.get_event_loop()
if "user_message_content" not in st.session_state:
    st.session_state.user_message_content = ""
if "ai_message_content" not in st.session_state:
    st.session_state.ai_message_content = ""
if "ai_message_function_name" not in st.session_state:
    st.session_state.ai_message_function_name = ""
if "ai_message_function_arguments" not in st.session_state:
    st.session_state.ai_message_function_arguments = ""


def load_conversation_history(conversation_history_path):
    try:
        with open(conversation_history_path, "r"
                  ) as f:
            conversation_history = json.load(f)
            return conversation_history
    except FileNotFoundError:
        os.makedirs(os.path.dirname(conversation_history_path), exist_ok=True)
        return []


async def on_submit(response):
    if st.session_state.user_message_content:
        st.session_state.messages.append(
            {
                "role": "user",
                "content": st.session_state.user_message_content,
            }
        )
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": st.session_state.ai_message_content,
            "additional_kwargs": {
                "function_call": {
                    "name": st.session_state.ai_message_function_name,
                    "arguments": st.session_state.ai_message_function_arguments,
                }
            }
            if st.session_state.ai_message_function_name
            else {},
        }
    )
    if st.session_state.ai_message_function_name:
        function_response = await call_function(browser=st.session_state.browser, json_function=response)

        st.session_state.messages.append(
            {
                "role": "function",
                "name": st.session_state.ai_message_function_name,
                "content": function_response,
            }
        )

    # history = json.dumps(st.session_state.messages, indent=4)

    # with open(conversation_history_path, "w") as f:
    #     f.write(json.dumps(history))
    st.session_state.user_message_content = ""
    st.session_state.ai_message_content = ""
    st.session_state.ai_message_function_name = ""
    st.session_state.ai_message_function_arguments = ""


def run_on_submit(response):
    # reset the options, unpredictable behaviour otherwise
    st.session_state.function_call_option = function_call_defaults[0]
    st.session_state.gpt_model = llm_models[0]
    asyncio.set_event_loop(st.session_state.loop)
    return st.session_state.loop.run_until_complete(on_submit(response))


def save_conversation_history(project_name: str, test_case: str):
    path = f"conversation_history/{project_name}/{test_case}"
    start_time = datetime.datetime.now().strftime("%Y_%m_%d-%H:%M:%S")
    file_path = os.path.join(path, f"{test_case}_history_{start_time}.json")

    if not os.path.exists(path):
        os.makedirs(path)

    with open(file_path, "w") as f:
        f.write(json.dumps(st.session_state.messages, indent=4))


@st.cache_data
def get_function_call_options(functions):
    options = function_call_defaults
    options.extend([func["name"] for func in functions])

    return options


@st.cache_resource
def setup_llm(project_name, test_case):
    return ProfiqDevAI(
        config=ProfiqDevAIConfig(
            project_name=project_name,
            test_case=test_case,
            x_last_messages=10,
        ))


async def main():
    # Initialize browser
    if st.session_state.browser is None:
        st.session_state.browser = await get_browser()
    async_browser = st.session_state.browser

    # Get project and test case name
    project_name = st.text_input("Project name")
    test_case = st.text_input("Test case name")
    if not (project_name and test_case):
        st.cache_resource.clear()  # reset cache
        st.cache_data.clear()
        st.stop()

    # CONVERSATION_HISTORY = f"projects/{project_name}/{test_case}/conversation_history.json"

    # Load conversation file
    # st.session_state.messages = load_conversation_history(CONVERSATION_HISTORY)

    # System message
    with st.chat_message("system"):
        system_message = st.text_area(
            label="System message",
            value="You are a QA engineer controlling a browser. Your goal is to plan and go through a test scenario with the "
            "user.\nFollow these steps when answering the user.\n Step 1. Consider you have all information necessary, "
            "if not, ask the user. In the system messages you have a simplified html of the webpage. Please, "
            "look for relevant information (like text elemets, ids, errors, warnings, messages) and use this information to propose next steps.\n"
            "Step 2. Consider if the proposed step makes sense and think about next steps.\n "
            "Step 3. Propose the next step to the user.\n",
            key="system_message",
            label_visibility="collapsed",
        )

    # Write conversation history
    for message in st.session_state.messages:
        if message["role"] == "function":
            with st.chat_message("function"):
                st.write(f"**{message['name']}**")
                st.write(message["content"])
        elif message["role"] == "assistant":
            with st.chat_message("assistant"):
                if message["content"]:
                    try:
                        message["content"] = st.text_area(
                            label="Assistant Message", value=message["content"])
                    except DuplicateWidgetID:
                        st.write(message["content"])
                function_call = message.get("function_call", None)
                if function_call:
                    with st.status(function_call["name"], state="complete"):
                        message["function_call"]["arguments"] = st.text_area(label="function_call",
                                                                             value=function_call["arguments"],
                                                                             label_visibility="collapsed")
        elif message["role"] == "user":
            with st.chat_message("user"):
                message["content"] = st.text_area(
                    label="User Message", value=message["content"])

    # Check last message
    last_message = None
    if st.session_state.messages:
        last_message = st.session_state.messages[-1]

    # User message
    if last_message is None or last_message["role"] == "assistant":
        if last_message is not None:
            st.button(
                "Save conversation history",
                on_click=save_conversation_history,
                args=(project_name, test_case),
            )
        with st.chat_message("user"):
            user_message_content = st.text_area(
                "User message content",
                key="user_message_content",
                label_visibility="collapsed",
            )
            if user_message_content:
                last_message = {
                    "role": "user",
                    "content": st.session_state.user_message_content,
                }
            else:
                st.stop()

    # Context message

    context_message = await components.context_message.get_context_message(async_browser)
    with st.chat_message("system"):
        context_message = st.text_area(
            label="Context message", value=context_message)

    tools = await get_tools(browser=st.session_state.browser)
    functions = [format_tool_to_openai_function(t) for t in tools]

    # Get chatcompletion inputs
    col1, col2 = st.columns(2)
    with col1:
        function_call_option = st.selectbox(
            "Force function call?",
            get_function_call_options(functions),
            help="'auto' leaves the decision to the model,"
                 " 'none' forces a generated message, or choose a specific function.",
            index=0,
            key="function_call_option",
        )
    with col2:
        gpt_model = st.selectbox(
            "Change model?",
            llm_models,
            help="Change the llm. Be aware that gpt-4 is more expensive.",
            index=0,
            key="gpt_model",
        )

    st.write(
        "Response is generated with model ",
        gpt_model,
        " and function call option ",
        function_call_option,
        ".",
    )
    llm = setup_llm(project_name, test_case)
    # Call LLM
    # TODO functions dont work
    try:
        response, token_counter = llm.chat_completion(ChatCompletionInputs(
            gpt_model=gpt_model, conversation_history=json.dumps(st.session_state.messages), functions=functions,
            function_call=function_call_option, system_messages=json.dumps([
                system_message]),
            context_messages=json.dumps([context_message]), last_message=last_message))
        # I think the number of tokens is written in the langchain response. So perhaps we could use that.
        st.write(token_counter)

        st.session_state.ai_message_content = response.content
        function_call = response.additional_kwargs.get("function_call", None)
        if function_call:
            st.session_state.ai_message_function_name = function_call["name"]
            st.session_state.ai_message_function_arguments = function_call["arguments"]
        else:
            st.session_state.ai_message_function_name = ""
            st.session_state.ai_message_function_arguments = ""

        # AI message
        with st.chat_message("assistant"):
            with st.form("ai_message"):
                st.text_area(
                    "Content",
                    key="ai_message_content",
                )
                function_call = response.additional_kwargs.get(
                    "function_call", {})
                st.text_input(
                    "Function call",
                    key="ai_message_function_name",
                )
                st.text_area(
                    "Arguments",
                    key="ai_message_function_arguments",
                )
                st.form_submit_button(
                    "Commit agent completion",
                    on_click=lambda: run_on_submit(function_call),
                )

    except AttributeError as e:
        st.write(e)


if __name__ == "__main__":
    asyncio.set_event_loop(st.session_state.loop)
    st.session_state.loop.run_until_complete(main())
