import asyncio
import datetime
import json
import os

import streamlit as st
from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from langchain.schema.messages import (
    AIMessage,
    FunctionMessage,
    HumanMessage,
    SystemMessage,
)
from langchain.tools.convert_to_openai import format_tool_to_openai_function
from langchain.tools.playwright.utils import (
    aget_current_page,
)
from openai import InvalidRequestError
from streamlit.errors import DuplicateWidgetID

from langchain_modules.toolkit import PlayWrightBrowserToolkit
from logging_handler import LoggingHandler
from utils import amark_invisible_elements, strip_html_to_structure

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
        with open(
            f"projects/{project_name}/{test_case}/conversation_history.json", "r"
        ) as f:
            st.session_state.messages = json.load(f)
            return st.session_state.messages
    except:
        return []


@st.cache_resource
def get_llm(project_name, test_case):

    async_browser = st.session_state.browser
    toolkit = PlayWrightBrowserToolkit.from_browser(
        async_browser=async_browser)
    tools = toolkit.get_tools()
    llm = ChatOpenAI(
        model="gpt-3.5-turbo",
        streaming=False,
        temperature=0,
        callbacks=[LoggingHandler(project_name, test_case)]
    )
    return llm, tools


async def get_context_message(browser):
    page = await aget_current_page(browser)
    await amark_invisible_elements(page)

    html_content = await page.content()
    stripped_html = strip_html_to_structure(html_content)

    context_message = SystemMessage(
        content=(
            f"Here is the current state of the browser:\n"
            f"```\n"
            f"{stripped_html}\n"
            f"```\n"
        ),
    )
    return context_message


async def get_browser():
    from playwright.async_api import async_playwright

    browser = await async_playwright().start()
    async_browser = await browser.chromium.launch(headless=False)
    return async_browser


async def on_submit(name_to_tool_map):
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
        tool = name_to_tool_map[st.session_state.ai_message_function_name]
        function_arguments = json.loads(
            st.session_state.ai_message_function_arguments)
        function_response = await tool._arun(
            **function_arguments,
        )
        st.session_state.messages.append(
            {
                "role": "function",
                "name": st.session_state.ai_message_function_name,
                "content": function_response,
            }
        )
    st.session_state.user_message_content = ""
    st.session_state.ai_message_content = ""
    st.session_state.ai_message_function_name = ""
    st.session_state.ai_message_function_arguments = ""


def run_on_submit(name_to_tool_map):
    asyncio.set_event_loop(st.session_state.loop)
    return st.session_state.loop.run_until_complete(on_submit(name_to_tool_map))


def save_conversation_history(project_name: str, test_case: str):
    path = f"conversation_history/{project_name}/{test_case}"
    start_time = datetime.datetime.now().strftime("%Y_%m_%d-%H:%M:%S")
    file_path = os.path.join(path, f"{test_case}_history_{start_time}.json")

    if not os.path.exists(path):
        os.makedirs(path)

    with open(file_path, 'w') as f:
        f.write(json.dumps(st.session_state.messages, indent=4))


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
            value="You are a QA engineer controlling a browser. Your goal is to plan and go through a test scenario with the user.",
            key="system_message",
            label_visibility="collapsed",
        )

    # History for prompt
    prompt_messages = [SystemMessage(content=system_message)]
    for message in st.session_state.messages[-10:]:
        if message["role"] == "function":
            prompt_messages.append(FunctionMessage(**message))
            with st.chat_message("function"):
                st.subheader(message["name"])
                st.write(message["content"])
        elif message["role"] == "assistant":
            with st.chat_message("system"):
                if message["content"] != "":
                    try:
                        message["content"] = st.text_area(label="Assistant Message", value=message["content"])
                    except DuplicateWidgetID:
                        st.write(message["content"])
                function_call = message.get("function_call", None)
                if function_call:
                    with st.status(function_call["name"], state="complete"):
                        message["function_call"]["arguments"] = st.text_area(label="function_call", value=function_call["arguments"], label_visibility="collapsed")
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
        with st.form("user_message"):
            st.form_submit_button(
                "Save conversation history",
                on_click=save_conversation_history,
                args=(project_name, test_case),
            )
        with st.chat_message("user"):
            user_message_content = st.text_area(
                "User message content",
                "Let's write a test for a chat app. We should test a user can send a message.",
                key="user_message_content",
                label_visibility="collapsed",
            )
            if user_message_content:
                prompt_messages.append(HumanMessage(
                    content=user_message_content))
            else:
                st.stop()

    # TODO: Force function call

    # Context message

    context_message = await get_context_message(async_browser)
    with st.chat_message("system"):
        context_message.content = st.text_area(label="Context message", value=context_message.content)
    prompt_messages.append(context_message)

    # Call LLM

    llm, tools = get_llm(project_name, test_case)

    functions = [format_tool_to_openai_function(t) for t in tools]
    name_to_tool_map = {tool.name: tool for tool in tools}

    def get_response(messages: list):
        try:
            res = llm(messages, functions=functions)

            functions_tokens = int(llm.get_num_tokens(str(functions))/2)    # function tokens are counted twice for some reason
            messages_tokens = llm.get_num_tokens_from_messages(messages)
            total_tokens = functions_tokens + messages_tokens
            with st.chat_message("system"):
                st.write(f"Messages tokens: {str(messages_tokens)}\n\nFunctions tokens: {str(functions_tokens)}\n\nTotal tokens: {str(total_tokens)}")

            return res
        except InvalidRequestError as e:
            with (st.chat_message("assistant")):
                st.write(e._message)

    try:
        response = get_response(messages=prompt_messages)

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
                    "AI message content",
                    key="ai_message_content",
                    label_visibility="collapsed",
                )
                function_call = response.additional_kwargs.get("function_call", {})
                st.text_input(
                    "AI message function name",
                    key="ai_message_function_name",
                    label_visibility="collapsed",
                )
                st.text_area(
                    "AI message function arguments",
                    key="ai_message_function_arguments",
                    label_visibility="collapsed",
                )
                st.form_submit_button(
                    "Commit agent completion",
                    on_click=lambda: run_on_submit(name_to_tool_map),
                )
    except AttributeError:
        pass

if __name__ == "__main__":
    asyncio.set_event_loop(st.session_state.loop)
    st.session_state.loop.run_until_complete(main())
