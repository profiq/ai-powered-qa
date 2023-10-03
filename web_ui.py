import asyncio

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

from dotenv import load_dotenv

load_dotenv()

import json
import streamlit as st

from langchain_modules.toolkit import PlayWrightBrowserToolkit
from langchain.tools.playwright.utils import (
    create_async_playwright_browser,
    aget_current_page,
)
from utils import amark_invisible_elements, strip_html_to_structure

from langchain.chat_models import ChatOpenAI
from langchain.schema.messages import (
    AIMessage,
    ChatMessage,
    FunctionMessage,
    HumanMessage,
    SystemMessage,
)
from langchain.tools.convert_to_openai import format_tool_to_openai_function

project_name = st.text_input("Project name")

test_case = st.text_input("Test case name")

if "messages" not in st.session_state:
    st.session_state.messages = []


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


if not (project_name and test_case):
    st.stop()

conversation_history = load_conversation_history(project_name, test_case)

with st.chat_message("system"):
    system_message = st.text_area(
        "System message",
        "You are a QA engineer controlling a browser. Your goal is to plan and go through a test scenario with the user.",
        key="system_message",
        label_visibility="collapsed",
    )

prompt_messages = [SystemMessage(content=system_message)]

for message in st.session_state.messages[-10:]:
    if message["role"] == "function":
        prompt_messages.append(FunctionMessage(**message))
        with st.chat_message("function"):
            st.subheader(message["name"])
            st.write(message["content"])
    elif message["role"] == "assistant":
        prompt_messages.append(AIMessage(**message))
        with st.chat_message("system"):
            st.write(message["content"])
            function_call = message.get("function_call", None)
            if function_call:
                with st.status(function_call["name"], state="complete"):
                    st.write(function_call["arguments"])
    elif message["role"] == "user":
        prompt_messages.append(HumanMessage(**message))
        with st.chat_message("user"):
            st.write(message["content"])

last_message = None
if st.session_state.messages:
    last_message = st.session_state.messages[-1]

if (
    last_message == None
    or last_message["role"] == "assistant"
    and not last_message.get("function_call", None)
):
    with st.chat_message("user"):
        user_prompt = st.text_area(
            "Prompt",
            "Let's write a test for a chat app. We should test a user can send a message.",
            key="prompt",
            label_visibility="collapsed",
        )
        next_message = {
            "role": "user",
            "content": user_prompt,
        }

        prompt_messages.append(HumanMessage(**next_message))


@st.cache_resource
def get_llm():
    async_browser = create_async_playwright_browser(headless=False)
    toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=async_browser)
    tools = toolkit.get_tools()
    llm = ChatOpenAI(
        model="gpt-3.5-turbo-16k",
        streaming=True,
        temperature=0,
    )
    return llm, tools, async_browser


llm, tools, async_browser = get_llm()


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


if "browser" not in st.session_state:
    st.session_state.browser = None
if "loop" not in st.session_state:
    st.session_state.loop = asyncio.get_event_loop()


async def get_browser():
    from playwright.async_api import async_playwright

    browser = await async_playwright().start()
    async_browser = await browser.chromium.launch(headless=False)
    return async_browser


async def main():
    if st.session_state.browser is None:
        st.session_state.browser = await get_browser()

    async_browser = st.session_state.browser

    context_message = await get_context_message(async_browser)

    with st.chat_message("system"):
        st.write(context_message.content)

    prompt_messages.append(context_message)

    # convert tools from langchain to openai functions
    functions = [format_tool_to_openai_function(t) for t in tools]

    response = llm(
        prompt_messages,
        functions=functions,
    )

    message = {
        "role": "assistant",
        "content": response.content,
        "function_call": response.additional_kwargs.get("function_call", None),
    }

    with st.chat_message("system"):
        st.write(message["content"])
        function_call = message["function_call"]
        if function_call:
            with st.status(function_call["name"], state="complete"):
                st.write(function_call["arguments"])

    def on_submit():
        if len(st.session_state.messages) > 0:
            st.session_state.messages.pop()
        st.session_state.messages.extend(
            [
                next_message,
                {
                    "role": "assistant",
                    "content": st.session_state.ai_message,
                },
            ]
        )

    with st.form("ai_message_form"):
        st.text_area(
            "AI message",
            message["content"],
            key="ai_message",
            label_visibility="collapsed",
        )
        st.form_submit_button("Submit", on_click=on_submit)


if __name__ == "__main__":
    asyncio.set_event_loop(st.session_state.loop)
    st.session_state.loop.run_until_complete(main())
