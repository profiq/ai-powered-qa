import json
import os

import streamlit as st

from ai_powered_qa.components.chat_model import ProfiqDevAIConfig, ProfiqDevAI, ChatCompletionInputs
from ai_powered_qa.components.constants import llm_models, function_call_defaults
from ai_powered_qa.components.function_caller import *
from ai_powered_qa.components.json_utils import (
    get_assistant_message,
    get_function_message,
    load_conversation_history,
    browse_by_json,
    save_conversation_history,
    get_user_message,
)

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


async def on_submit(function_call):
    st.session_state.messages.append(get_assistant_message(st))
    if st.session_state.ai_message_function_name:
        st.session_state.messages.append(await get_function_message(st, function_call))

    st.session_state.user_message_content = ""
    st.session_state.ai_message_content = ""
    st.session_state.ai_message_function_name = ""
    st.session_state.ai_message_function_arguments = ""


def run_on_submit(function_call):
    # reset the options, unpredictable behaviour otherwise
    st.session_state.function_call_option = function_call_defaults[0]
    st.session_state.gpt_model = llm_models[0]
    asyncio.set_event_loop(st.session_state.loop)
    return st.session_state.loop.run_until_complete(on_submit(function_call))


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
        )
    )


def get_prefill_options(project: str):
    options = ["None"]
    try:
        return options + os.listdir(f"projects/{project}/")
    except FileNotFoundError:
        return options


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

    # System message
    with st.chat_message("system"):
        system_message = st.text_area(
            label="System message",
            value="You are a QA engineer controlling a browser. "
            "Your goal is to plan and go through a test scenario with the user",
            key="system_message",
            label_visibility="collapsed",
        )

    # Prefill
    prefill_box = st.selectbox(
        label="Project pre-fill options", options=get_prefill_options(project_name)
    )

    if st.button(label="Pre-fill admin login"):
        loaded_conversation = load_conversation_history(
            f"projects/{project_name}/{prefill_box}"
        )
        await browse_by_json(
            playwright_instance=st.session_state.browser, messages=loaded_conversation
        )
        st.session_state.messages += (
            loaded_conversation
            if loaded_conversation not in st.session_state.messages
            else []
        )
        options=get_prefill_options(project_name)

    # Write conversation history
    for key, message in enumerate(st.session_state.messages):
        # This loop is only for writing the conversation history and for modifying previous messages.
        # Use unique keys to avoid DuplicateWidgetID error
        if message["role"] == "function":
            with st.chat_message("function"):
                st.write(f"**{message['name']}**")
                st.write(message["content"])
        elif message["role"] == "assistant":
            with st.chat_message("assistant"):
                if message["content"]:
                    message["content"] = st.text_area(
                        label="Assistant Message",
                        value=message["content"],
                        key=f"assistant_{key}",
                    )
                function_call = message["additional_kwargs"].get("function_call", None)
                if function_call:
                    with st.status(function_call["name"], state="complete"):
                        st.text_area(
                            label="function_call",
                            value=function_call["arguments"],
                            label_visibility="collapsed",
                            key=f"function_call_{key}",
                        )
        elif message["role"] == "user":
            with st.chat_message("user"):
                message["content"] = st.text_area(
                    label="User Message", value=message["content"], key=f"user_{key}"
                )

    # Check last message
    last_message = None
    if st.session_state.messages:
        last_message = st.session_state.messages[-1]

    # User message
    if last_message is None or last_message["role"] == "assistant":
        st.button(
            "Save conversation history",
            on_click=save_conversation_history,
            args=(project_name, test_case, st.session_state.messages),
        )
        with st.chat_message("user"):
            user_message_content = st.text_area(
                "User message content",
                key="user_message_content",
                label_visibility="collapsed",
            )
            if user_message_content:
                # append the user message instantly to the conversation
                st.session_state.messages.append(get_user_message(st))
            else:
                st.stop()

    # Context message
    context_message = await get_context_message(browser=async_browser)

    with st.chat_message("system"):
        context_message = st.text_area(label="Context message", value=context_message)

    functions = get_function_list()

    # Rerun LLM with new parameters
    col1, col2 = st.columns(2)
    with col1:
        function_call_option = st.selectbox(
            "Force function call?",
            get_function_call_options(functions),
            help="'auto' leaves the decision to the model, "
            "'none' forces a generated message, or choose a specific function.",
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

    # auto-save before llm part
    save_conversation_history(
        project_name, test_case, st.session_state.messages, autosave=True
    )

    llm = setup_llm(project_name, test_case)

    # Call LLM
    try:
        response, token_counter = llm.chat_completion(
            ChatCompletionInputs(
                gpt_model=gpt_model,
                conversation_history=json.dumps(st.session_state.messages),
                functions=json.dumps(functions),
                function_call=function_call_option,
                system_messages=json.dumps([system_message]),
                context_messages=json.dumps([context_message]),
            )
        )

        st.write(token_counter)

        st.session_state.ai_message_content = response.choices[0].message.content
        function_call = response.choices[0].message.function_call
        if function_call:
            st.session_state.ai_message_function_name = function_call.name
            st.session_state.ai_message_function_arguments = function_call.arguments
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
                function_call = response.choices[0].message.function_call if not None else {}
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
