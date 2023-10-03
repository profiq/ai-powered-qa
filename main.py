import asyncio
import json
import logging
import shutil

import openai

from langchain_modules.toolkit import PlayWrightBrowserToolkit
from langchain_modules.tools import *
from langchain_modules.tools.playwright.utils import create_async_playwright_browser
from langchain.chat_models import ChatOpenAI
from langchain.docstore.document import Document
from langchain.document_transformers import Html2TextTransformer
from langchain.embeddings import OpenAIEmbeddings
from langchain.schema.messages import ChatMessage, FunctionMessage, SystemMessage
from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
    Language,
)
from langchain.tools.playwright.utils import aget_current_page
from langchain.vectorstores import FAISS


from dotenv import load_dotenv

from utils import amark_invisible_elements, strip_html_to_structure

load_dotenv()  # load environment variables from .env file

import os

# Things to improve:

#   - Implement functionality that in function get_messages_for_gpt will add the current webpage as a context.
#     Think of a way how to summarize the chat history or just keep the last x messages

#   - Have this code with the playwright tools in one repo

#   - Divide the playwright tools from langchain into two functionalities: Execute the code, update chat history vs code generation

#   - Save the user initial prompt in the messages, so GPT knows what the final goal is
#   - Implement functionality that will allow user to edit the function call before it is executed
#   - Refactor the conversation loop

#   - Sync with lang_play.py script


# example taken from here https://platform.openai.com/docs/guides/gpt/function-calling
# how to define a tool: https://python.langchain.com/docs/modules/agents/tools/custom_tools

# We follow 4 steps in the user-agent loop:
#   - Step 1: send the conversation and available functions to GPT
#   - Step 2: check if GPT wanted to call a function
#   - Step 3: call the function\
#   - Step 4: send the info on the function call and function response to GPT

available_functions = {
    "click_element": ClickTool,
    "click_by_text": ClickByTextTool,
    "iframe_click": IframeClickTool,
    "iframe_click_by_text": IframeClickByTextTool,
    "iframe_expect_hidden": IframeExpectHiddenTool,
    "iframe_upload": IframeUploadTool,
    "current_page": CurrentWebPageTool,
    "expect_test_id": ExpectTestIdTool,
    "expect_text": ExpectTextTool,
    "expect_title": ExpectTitleTool,
    "extract_hyperlinks": ExtractHyperlinksTool,
    "extract_text": ExtractTextTool,
    "fill_element": FillTextTool,
    "get_elements": GetElementsTool,
    "navigate_browser": NavigateTool,
    "navigate_back": NavigateBackTool,
    "take_screenshot": TakeScreenshotTool,
    "press_key": PressTool,
    "wait": WaitTool,
}


class GPT:
    def __init__(self, functions, toolkit):
        self.messages = []
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo-16k",
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            streaming=True,
            temperature=0,
        )
        self.system_message = SystemMessage(
            content="You are a QA engineer controlling a browser. Your goal is to plan and go through a test scenario with the user. Ask the user for data input or instructions when you are not certain about what to do. "
        )
        self.functions = functions
        self.toolkit = toolkit

    def get_prompt(self):
        prompt_input = input("Please enter a prompt or type quit.\n")
        if prompt_input.lower() in [""]:
            return False
        elif prompt_input == "quit":
            return False
        else:
            new_message = ChatMessage(role="user", content=prompt_input)
            self.messages.append(new_message)
            return new_message

    async def ask_gpt(self):
        messages_gpt = await self._get_messages_for_gpt()
        response = self._gpt_api_request(messages_gpt)

        # tokens = response["usage"]
        # logging.info(f"gpt context window: {messages_gpt}")
        # logging.info(f"Tokens used so far (response): {tokens}\n")

        new_message = ChatMessage(
            role="assistant",
            content=response.content,
            additional_kwargs=response.additional_kwargs,
        )

        self.messages.append(new_message)
        return new_message

    async def call_function(self, function_call):
        print(
            f"Assistant wants to call function:\n"
            f"  {function_call['name'].strip()} "
            f"with arguments: {function_call['arguments'].strip()}\n"
        )
        user_loop_input = input(
            "Call function (press enter), edit function call (e) or abort function call "
            "and enter new prompt (p) or quit (quit)?\n"
        )
        print("user_loop_input", user_loop_input)
        if user_loop_input == "e":
            # TODO editing not working yet
            return False

        elif user_loop_input == "":
            # call the function
            function_name = function_call["name"]
            function_to_call = available_functions[function_name]
            function_args = json.loads(function_call["arguments"])
            function_tool = function_to_call(async_browser=async_browser)
            function_response = await function_tool._arun(**function_args)

            new_message = FunctionMessage(
                name=function_call["name"],
                content=function_response,
            )

            self.messages.append(new_message)
            return new_message

        elif user_loop_input == "quit":
            return False

        elif user_loop_input == "p":
            # abort function call and enter new prompt with abort message
            abort_message = f"Call aborted by user. Reason:"
            new_prompt = input("Function call cancelled. Enter new prompt.\n")
            new_message = FunctionMessage(
                name=function_call["name"],
                content=abort_message + new_prompt,
            )
            self.messages.append(new_message)
            return new_message
        else:
            print("Please enter e, press enter, p or quit.")
            return False

    async def take_step(self):
        if len(self.messages) == 0:
            return self.get_prompt()

        last_message = self.messages[-1]

        role = "function"
        if isinstance(last_message, ChatMessage):
            role = last_message.role

        print(role)

        if role == "assistant":
            function_call = last_message.additional_kwargs.get("function_call")
            if function_call:
                return await self.call_function(function_call)
            else:
                return self.get_prompt()

        if role == "user" or role == "function":
            return await self.ask_gpt()

        return False

    async def user_agent_loop(self):
        self._write_test_header()
        conversation_running = True

        while conversation_running:
            result = await self.take_step()
            self._write_conversation_history()
            if result == False:
                return
            else:
                self._log_message(result)
                continue
            prompt_input = input("Please enter a prompt or type quit.\n")
            if prompt_input.lower() in [""]:
                continue
            elif prompt_input == "quit":
                conversation_running = False
            else:
                gpt_response = await self.ask_gpt(
                    ChatMessage(role="user", content=prompt_input)
                )
                self._write_conversation_history()
                function_call_loop = True
                while function_call_loop:
                    if gpt_response.get("function_call"):
                        # gpt wants to call a function, first validate with user what to do
                        validating_loop = True
                        while validating_loop:
                            print(
                                f"Assistant wants to call function:\n"
                                f"  {gpt_response['function_call']['name'].strip()} "
                                f"with arguments: {gpt_response['function_call']['arguments'].strip()}\n"
                            )
                            user_loop_input = input(
                                "Call function (press enter), edit function call (e) or abort function call "
                                "and enter new prompt (p) or quit (quit)?\n"
                            )
                            if user_loop_input == "e":
                                # TODO editing not working yet
                                continue
                                edited_function_call = input("Enter function call:\n")
                                if edited_function_call == "":
                                    edited_function_call = gpt_response[
                                        "function_call"
                                    ]["name"]
                                # edited_function_arguments = input("Enter function arguments:\n")
                                self._get_available_arguments()
                                if edited_function_arguments == "":
                                    edited_function_arguments = gpt_response[
                                        "function_call"
                                    ]["arguments"]

                                if not self._validate_function_call(
                                    edited_function_call, edited_function_arguments
                                ):
                                    print(
                                        "Function call is not valid. Please try again."
                                    )
                                    continue
                                gpt_response["function_call"][
                                    "name"
                                ] = edited_function_call
                                gpt_response["function_call"][
                                    "arguments"
                                ] = edited_function_arguments

                            elif user_loop_input == "":
                                # call the function
                                validating_loop = False
                                function_name = gpt_response["function_call"]["name"]
                                function_to_call = available_functions[function_name]
                                function_args = json.loads(
                                    gpt_response["function_call"]["arguments"]
                                )
                                function_tool = function_to_call(
                                    async_browser=async_browser
                                )
                                function_response = await function_tool._arun(
                                    **function_args
                                )

                                gpt_response = await self.ask_gpt(
                                    self._construct_message(
                                        role="function",
                                        name=function_name,
                                        content=function_response,
                                    )
                                )
                                self._write_conversation_history()

                            elif user_loop_input == "quit":
                                validating_loop = False
                                function_call_loop = False
                                conversation_running = False
                                break

                            elif user_loop_input == "p":
                                # abort function call and enter new prompt with abort message
                                abort_message = (
                                    f"I don't want to call function {gpt_response['function_call']['name']} "
                                    f"with parameters {gpt_response['function_call']['arguments']}. Instead "
                                )
                                new_prompt = input(
                                    "Function call cancelled. Enter new prompt.\n"
                                )
                                gpt_response = await self.ask_gpt(
                                    self._construct_message(
                                        role="user", content=abort_message + new_prompt
                                    )
                                )
                                validating_loop = False
                            else:
                                print("Please enter e, press enter, p or quit.")
                    else:
                        # no function call, print response and ask for new prompt
                        print(gpt_response)
                        function_call_loop = False
                        break

        file_path = f"tests/{'example'}.spec.ts"
        shutil.move("tempfile", file_path)

        return file_path

    async def _get_messages_for_gpt(self):
        # add system and context messages to the conversation
        page = await aget_current_page(self.toolkit.async_browser)

        # html2text = Html2TextTransformer()
        # docs_transformed = html2text.transform_documents(
        #     [Document(page_content=html_content)]
        # )
        # print(docs_transformed)

        # html_splitter = RecursiveCharacterTextSplitter.from_language(
        #     language=Language.HTML, chunk_size=300, chunk_overlap=0
        # )
        # html_docs = html_splitter.create_documents([html_content])
        # html_docs
        # embeddings = OpenAIEmbeddings()
        # db = FAISS.from_documents(html_docs, embeddings)
        # retriever = db.as_retriever()
        # response = self.llm(
        #     messages=[
        #         ChatMessage(
        #             role="system",
        #             content=(
        #                 f"Given the recent conversation with the user:\n"
        #                 f"==BEGIN_CONVERSATION==\n"
        #             ),
        #         ),
        #         *self.messages[-10:1],
        #         ChatMessage(
        #             role="system",
        #             content=(
        #                 f"==END_CONVERSATION==\n"
        #                 f"In a single sentence, describe an element on the page that should be relevant to the current situation."
        #             ),
        #         ),
        #     ],
        # )
        # print(response)
        # docs = retriever.get_relevant_documents(response.content)
        # print(docs)

        # print(html_content)

        await amark_invisible_elements(page)

        html_content = await page.content()
        stripped_html = strip_html_to_structure(html_content)

        # print(stripped_html)

        # response = self.llm(
        #     messages=[
        #         ChatMessage(
        #             role="user",
        #             content=(
        #                 f"In plain english, describe what can be seen on the following HTML page:\n"
        #                 f"Make sure to include details that will be usefull for writing an automated test on the page.\n"
        #                 f"```\n"
        #                 f"{stripped_html}\n"
        #                 f"```\n"
        #             ),
        #         ),
        #     ]
        # )

        # print(response)

        context_message = ChatMessage(
            role="system",
            content=(
                f"Here is the current state of the browser:\n"
                f"```\n"
                # f"{[doc.page_content for doc in docs]}\n"
                # f"{response.content}\n"
                f"{stripped_html}\n"
                f"```\n"
            ),
        )

        messages = [self.system_message, *self.messages[-10:], context_message]
        return messages

    def _gpt_api_request(self, messages_gpt):
        response = self.llm(
            messages_gpt,
            functions=[dict(format_tool_to_openai_function(t)) for t in tools],
        )
        return response

    def _validate_function_call(self, function_call_name, function_call_arguments):
        if function_call_name not in available_functions:
            return False
        return True

    def _construct_message(self, **kwargs):
        return {k: v for k, v in kwargs.items()}

    def _write_conversation_history(self):
        with open("conversation_history.log", "w") as f:
            for message in self.messages:
                f.write(json.dumps(message.to_json(), indent=4))

    def _get_available_arguments(self, function_call):
        for function in self.functions:
            if function["name"] == function_call:
                return function["parameters"]["properties"]
        else:
            return None

    def _write_test_header(self):
        with open("tempfile", "w") as f:
            f.write("import { test, expect } from '@playwright/test';\n\n")
            f.write(f"test('{'My example test name'}', async ({{ page }}) => {{\n")

    def _log_message(self, message):
        role = "function"
        if isinstance(message, ChatMessage):
            role = message.role
        print(f"{role.upper()}: {message.content}")

    def _write_test_footer(self):
        with open("tempfile", "a") as f:
            f.write("});\n\n")


if __name__ == "__main__":
    logging.basicConfig(
        filename="token_usage.log", encoding="utf-8", level=logging.INFO
    )

    open("token_usage.log", "w").close()
    open("conversation_history.log", "w").close()

    # Initialize the playwright toolkit / tools
    async_browser = create_async_playwright_browser(headless=False)
    toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=async_browser)
    tools = toolkit.get_tools()
    # convert tools from langchain to openai functions
    functions = [format_tool_to_openai_function(t) for t in tools]

    gpt = GPT(functions=functions, toolkit=toolkit)
    print("Starting user-agent loop...\n")
    loop = asyncio.get_event_loop()
    test_file = loop.run_until_complete(gpt.user_agent_loop())
    print("Generated playwright typescript code: \n")
    with open(test_file, "r") as f:
        print(f.read())
