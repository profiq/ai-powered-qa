import asyncio
import datetime
import json
import os

import streamlit as st
from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from langchain.schema.messages import AIMessage, FunctionMessage, HumanMessage, SystemMessage
from langchain.tools.convert_to_openai import format_tool_to_openai_function
from openai import InvalidRequestError
from streamlit.errors import DuplicateWidgetID

import components.context_message
from components.constants import llm_models, function_call_defaults
from components.function_caller import get_browser, get_tools
from components.logging_handler import LoggingHandler
from components.json_handler import get_user_message, get_function_message, get_assistant_message
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


@st.cache_data
def load_conversation_history(project_name, test_case):
    try:
        with open(f"projects/{project_name}/{test_case}/conversation_history.json", "r") as f:
            st.session_state.messages = json.load(f)
            return st.session_state.messages
    except:
        return []


@st.cache_resource
def get_llm(gpt_model, project_name, test_case):
    llm = ChatOpenAI(
        model=gpt_model,
        streaming=False,
        temperature=0,
        callbacks=[setup_logging_handler(project_name, test_case)],
    )
    return llm


@st.cache_resource
def setup_logging_handler(project_name, test_case):
    return LoggingHandler(project_name, test_case)


async def on_submit(response):
    if st.session_state.user_message_content:
        st.session_state.messages.append(get_user_message(st))

    st.session_state.messages.append(get_assistant_message(st))

    if st.session_state.ai_message_function_name:
        st.session_state.messages.append(await get_function_message(st, response))

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

    # Load conversation file
    load_conversation_history(project_name, test_case)

    # System message
    with st.chat_message("system"):
        system_message = st.text_area(
            label="System message",
            value="You are a QA engineer controlling a browser. "
                  "Your goal is to plan and go through a test scenario with the user.",
            key="system_message",
            label_visibility="collapsed",
        )

    # History for prompt
    prompt_messages = [SystemMessage(content=system_message)]
    for message in st.session_state.messages[-10:]:
        if message["role"] == "function":
            prompt_messages.append(FunctionMessage(**message))
            with st.chat_message("function"):
                st.write(f"**{message['name']}**")
                st.write(message["content"])
        elif message["role"] == "assistant":
            with st.chat_message("assistant"):
                if message["content"]:
                    try:
                        message["content"] = st.text_area(label="Assistant Message", value=message["content"])
                    except DuplicateWidgetID:
                        st.write(message["content"])
                function_call = message.get("function_call", None)
                if function_call:
                    with st.status(function_call["name"], state="complete"):
                        message["function_call"]["arguments"] = st.text_area(label="function_call",
                                                                             value=function_call["arguments"],
                                                                             label_visibility="collapsed")
                prompt_messages.append(AIMessage(**message))
        elif message["role"] == "user":
            with st.chat_message("user"):
                message["content"] = st.text_area(label="User Message", value=message["content"])
                prompt_messages.append(HumanMessage(**message))

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
                prompt_messages.append(HumanMessage(content=user_message_content))
            else:
                st.stop()

    # Context message

    context_message = await components.context_message.get_context_message(async_browser)
    with st.chat_message("system"):
        context_message.content = st.text_area(label="Context message", value=context_message.content)
    prompt_messages.append(context_message)

    tools = await get_tools(browser=st.session_state.browser)
    functions = [format_tool_to_openai_function(t) for t in tools]

    # Call LLM

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

    if function_call_option not in ["auto", "none"]:
        _function_call = {"name": function_call_option}
    else:
        _function_call = function_call_option

    st.write(
        "Response is generated with model ",
        gpt_model,
        " and function call option ",
        _function_call,
        ".",
    )
    llm = get_llm(gpt_model, project_name, test_case)

    def get_response(messages: list):
        try:
            response = llm(
                prompt_messages,
                functions=functions,
                function_call=_function_call,
            )

            functions_tokens = int(llm.get_num_tokens(str(functions))/2)  # function tokens are counted twice
            messages_tokens = llm.get_num_tokens_from_messages(messages)
            total_tokens = functions_tokens + messages_tokens

            st.write(f"Messages tokens: {str(messages_tokens)}  \n"
                     f"Functions tokens: {str(functions_tokens)}  \n"
                     f"Total tokens: {str(total_tokens)}")
            return response
        except InvalidRequestError as e:
            with (st.chat_message("assistant")):
                st.write(e._message)

    try:
        response = get_response(prompt_messages)

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
                function_call = response.additional_kwargs.get("function_call", {})
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

    except AttributeError:
        pass


if __name__ == "__main__":
    asyncio.set_event_loop(st.session_state.loop)
    st.session_state.loop.run_until_complete(main())
