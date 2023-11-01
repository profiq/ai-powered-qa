import asyncio
import datetime
import json
import os

import streamlit as st
from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from langchain.schema.messages import (AIMessage, FunctionMessage, HumanMessage, SystemMessage)
from langchain.tools.convert_to_openai import format_tool_to_openai_function
from langchain.tools.playwright.utils import (aget_current_page)
from openai import InvalidRequestError

from langchain_modules.toolkit import PlayWrightBrowserToolkit
from logging_handler import LoggingHandler
from utils import amark_invisible_elements, strip_html_to_structure


class WebLLM:
    # def __init__(self, loop):
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

    @staticmethod
    @st.cache_data
    def load_conversation_history(project_name, test_case):
        try:
            with open(f"projects/{project_name}/{test_case}/conversation_history.json", "r") as f:
                st.session_state.messages = json.load(f)
                return st.session_state.messages
        except:
            return []

    @staticmethod
    @st.cache_resource
    def get_llm(project_name, test_case):
        async_browser = st.session_state.browser
        toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=async_browser)
        tools = toolkit.get_tools()
        llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            streaming=False,
            temperature=0,
            callbacks=[LoggingHandler(project_name, test_case)]
        )
        return llm, tools

    @staticmethod
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

    @staticmethod
    async def get_browser():
        from playwright.async_api import async_playwright

        browser = await async_playwright().start()
        async_browser = await browser.chromium.launch(headless=False)
        return async_browser

    async def on_submit(self, name_to_tool_map):
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

            function_arguments = json.loads(st.session_state.ai_message_function_arguments)
            function_response = await tool._arun(**function_arguments)
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

    def run_on_submit(self, name_to_tool_map):
        asyncio.set_event_loop(st.session_state.loop)
        return st.session_state.loop.run_until_complete(self.on_submit(name_to_tool_map))

    @staticmethod
    def save_conversation_history(project_name: str, test_case: str):
        path = f"conversation_history/{project_name}/{test_case}"
        start_time = datetime.datetime.now().strftime("%Y_%m_%d-%H:%M:%S")
        file_path = os.path.join(path, f"{test_case}_history_{start_time}.json")

        if not os.path.exists(path):
            os.makedirs(path)

        with open(file_path, 'w') as f:
            f.write(json.dumps(st.session_state.messages, indent=4))

    def get_response(self, llm, prompt_messages, functions):
        # new_prompt:  list[SystemMessage | FunctionMessage | AIMessage | HumanMessage] = []
        prompt_messages = prompt_messages
        try:
            response = llm(prompt_messages, functions=functions)
            # with st.chat_message("assistant"):
                # st.write(f"Prompt tokens: {llm.get_num_tokens(str(prompt_messages))}")
                # st.write(llm.get_num_tokens_from_messages(prompt_messages))
                # st.write(llm.get_num_tokens_from_messages(functions))
            return response, prompt_messages
        except InvalidRequestError as e:
            st.write(e._message)
            new_prompt: prompt_messages = []
            #
            # st.write(f"Prompt tokens: {llm.get_num_tokens(str(prompt_messages))}")
            # st.write(llm.get_num_tokens_from_messages(str(prompt_messages)))
            # st.write(llm.get_num_tokens_from_messages(str(functions)))
            self.edit_messages(prompt_messages, llm, functions)
            # st.button("Delete last message",
            #           on_click=prompt_messages.pop)
            # prompt_messages.pop()
            # return get_response(llm, prompt_messages, functions)
            # return edit_messages(prompt_messages, llm, functions)
            # st.text_area(label="msg", value=json.dumps(str(prompt_messages[0])))
            # tokens = 0
            # for pm in prompt_messages:
            #     # tokens += llm.get_num_tokens(str(pm))
            #     tokens += llm.get_num_tokens(pm.content)
            #     tokens += llm.get_num_tokens(str(pm.additional_kwargs))
            #     try:
            #         tokens += llm.get_num_tokens(str(pm.example))
            #     except Exception:
            #         pass
                # st.text_area(label="msg", value=pm)

            # st.write(f"Tokens: {tokens}")

            # new_prompt.append(st.text_area(label=f"Message , tokens: {llm.get_num_tokens(str(prompt_messages.content))}",
            #                                value=prompt_messages, ))
            # for msg in prompt_messages:
            #     pass
            #     # new_prompt.append(st.text_input(label=f"{msg.name} , tokens: {llm.get_num_tokens(str(msg.))}", value=msg))

            return self.get_response(llm, new_prompt, functions)

    def edit_messages(self, prompt_messages, llm, functions):
        new_prompt = prompt_messages
        with st.chat_message("assistant"):
            with st.form("message_edit"):
                for message in new_prompt:
                    message.content = st.text_area(label=f"{message.type}, tokens: {llm.get_num_tokens(str(message))}",
                                                   value=message.content)
                return st.form_submit_button(label="Save messages", on_click=self.get_response,
                                             args=(llm, new_prompt, functions))

    def set_project(self):
        project_name = st.text_input("Project name")
        test_case = st.text_input("Test case name")
        if not (project_name and test_case):
            st.cache_resource.clear()  # reset cache
            st.cache_data.clear()
            st.stop()

        return project_name, test_case

    def show_user_message(self, prompt_messages, project_name, test_case):
        # Check last message
        last_message = None
        if st.session_state.messages:
            last_message = st.session_state.messages[-1]

        # User message
        if last_message == None or last_message["role"] == "assistant":
            with st.form("user_message"):
                st.form_submit_button(
                    "Save conversation history",
                    on_click=self.save_conversation_history,
                    args=(project_name, test_case),
                )
                # st.form_submit_button(
                #     "Edit messages",
                #     on_click=edit_messages,
                #     args=(prompt_messages, llm, functions)
                # )
            with st.chat_message("user"):
                user_message_content = st.text_area(
                    "User message content",
                    key="user_message_content",
                    label_visibility="collapsed",
                )
                if user_message_content:
                    prompt_messages.append(HumanMessage(
                        content=user_message_content))
                else:
                    st.stop()

    @staticmethod
    def show_prompt_history(system_message):
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
        return prompt_messages

    async def main(self):
        # Initialize browser
        if st.session_state.browser is None:
            st.session_state.browser = await self.get_browser()
        async_browser = st.session_state.browser

        # Get project and test case name
        project_name, test_case = self.set_project()

        # Load conversation file
        self.load_conversation_history(project_name, test_case)

        # System message
        with st.chat_message("system"):
            system_message = st.text_area(
                label="System message",
                value="You are a QA engineer controlling a browser. "
                      "Your goal is to plan and go through a test scenario with the user.",
                key="system_message",
                label_visibility="collapsed")

        # History for prompt
        prompt_messages = self.show_prompt_history(system_message)

        self.show_user_message(prompt_messages, project_name, test_case)

        # TODO: Force function call

        # Context message
        context_message = await self.get_context_message(async_browser)
        with st.chat_message("system"):
            st.write(context_message.content)
        prompt_messages.append(context_message)

        # Call LLM
        llm, tools = self.get_llm(project_name, test_case)

        functions = [format_tool_to_openai_function(t) for t in tools]
        name_to_tool_map = {tool.name: tool for tool in tools}

        # response, prompt_messages = self.get_response(llm, prompt_messages, functions)
        response = llm(prompt_messages, functions=functions)

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
                st.text_area(label="AI message content", key="ai_message_content")
                function_call = response.additional_kwargs.get("function_call", {})
                st.text_input(label="AI message function name", key="ai_message_function_name")
                st.text_area(label="AI message function arguments", key="ai_message_function_arguments")
                st.form_submit_button(label="Commit agent completioooon",
                                      on_click=lambda: self.run_on_submit(name_to_tool_map))


if __name__ == "__main__":
    asyncio.set_event_loop(st.session_state.loop)
    st.session_state.loop.run_until_complete(WebLLM().main())


    # def get_response(messages: list, recurse: bool = False):
    #     try:
    #         res = llm(messages, functions=functions)
    #
    #         encoding = tiktoken.encoding_for_model(llm.model_name)
    #         functions_tokens = int(len(encoding.encode(str(functions))) / 2) - 2
    #         messages_tokens = llm.get_num_tokens_from_messages(messages) - 1
    #         total_tokens = functions_tokens + messages_tokens
    #         st.write(f"Messages' tokens: {str(messages_tokens)}   Functions tokens: {str(functions_tokens)}   Total tokens: {str(total_tokens)}")
    #
    #         return res
    #     except InvalidRequestError as e:
    #         if not recurse:
    #             with st.chat_message("assistant"):
    #
    #                 st.write(e._message)
    #                 edit_form = st.form("message_edit")
    #
    #                 for key, msg in enumerate(messages):
    #                     msg.content = edit_form.text_area(label=f"{msg.type}, tokens: {llm.get_num_tokens(str(msg))}", value=msg.content, key=key, )
    #
    #                 submit = edit_form.form_submit_button(label="Save messages")
    #
    #                 if submit:
    #                     return get_response(messages)
    #
    #         else:
    #             pass
    #
    # response = (get_response(messages=prompt_messages))