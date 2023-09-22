import argparse
import asyncio
import openai
import json
import logging
import shutil
import os
import sys


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




# Uncomment this if you have forked langchain
# expected the langchain to be in the same folder as this repo

# import_path = os.path.join(os.path.dirname(sys.path[0]), 'langchain/libs/langchain/')
# sys.path.append(import_path)

from langchain.tools import format_tool_to_openai_function
from langchain.tools.playwright.utils import create_async_playwright_browser
from langchain.agents.agent_toolkits import PlayWrightBrowserToolkit
from langchain.tools.playwright.click import ClickTool
from langchain.tools.playwright.click_by_text import ClickByTextTool
from langchain.tools.playwright.iframe_click import IframeClickTool
from langchain.tools.playwright.iframe_click_by_text import IframeClickByTextTool
from langchain.tools.playwright.iframe_expect_hidden import IframeExpectHiddenTool
from langchain.tools.playwright.iframe_upload import IframeUploadTool
from langchain.tools.playwright.current_page import CurrentWebPageTool
from langchain.tools.playwright.expect_test_id import ExpectTestIdTool
from langchain.tools.playwright.expect_text import ExpectTextTool
from langchain.tools.playwright.expect_title import ExpectTitleTool
from langchain.tools.playwright.extract_hyperlinks import ExtractHyperlinksTool
from langchain.tools.playwright.extract_text import ExtractTextTool
from langchain.tools.playwright.fill import FillTool
from langchain.tools.playwright.get_elements import GetElementsTool
from langchain.tools.playwright.navigate import NavigateTool
from langchain.tools.playwright.navigate_back import NavigateBackTool
from langchain.tools.playwright.take_screenshot import TakeScreenshotTool

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
    "fill_element": FillTool,
    "get_elements": GetElementsTool,
    "navigate_browser": NavigateTool,
    "navigate_back": NavigateBackTool,
    "take_screenshot": TakeScreenshotTool,
}


class GPT:

    def __init__(self, functions):
        self.messages = []
        self.system_messages = "You are helping me to automate UI testing."
        self.functions = functions

    async def ask_gpt(self, message):
        self.messages.append(message)
        self._log_message(message)
        messages_gpt = self._get_messages_for_gpt()
        response = self._gpt_api_request(messages_gpt)
        response_message = response["choices"][0]["message"]

        tokens = response["usage"]
        logging.info(f"gpt context window: {messages_gpt}")
        logging.info(f"Tokens used so far (response): {tokens}\n")

        self.messages.append(response_message)
        self._write_conversation_history()
        return response_message

    async def user_agent_loop(self):
        self._write_test_header()
        conversation_running = True

        while conversation_running:
            prompt_input = input("Please enter a prompt or type quit.\n")
            if prompt_input.lower() in ['']:
                continue
            elif prompt_input == 'quit':
                conversation_running = False
            else:
                gpt_response = await self.ask_gpt(self._construct_message(role="user", content=prompt_input))
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
                                f"with arguments: {gpt_response['function_call']['arguments'].strip()}\n")
                            user_loop_input = input(
                                "Call function (press enter), edit function call (e) or abort function call "
                                "and enter new prompt (p) or quit (quit)?\n")
                            if user_loop_input == 'e':
                                # TODO editing not working yet
                                continue
                                edited_function_call = input(
                                    "Enter function call:\n")
                                if edited_function_call == '':
                                    edited_function_call = gpt_response['function_call']['name']
                                # edited_function_arguments = input("Enter function arguments:\n")
                                self._get_available_arguments()
                                if edited_function_arguments == '':
                                    edited_function_arguments = gpt_response['function_call']['arguments']

                                if not self._validate_function_call(edited_function_call, edited_function_arguments):
                                    print(
                                        "Function call is not valid. Please try again.")
                                    continue
                                gpt_response['function_call']['name'] = edited_function_call
                                gpt_response['function_call']['arguments'] = edited_function_arguments

                            elif user_loop_input == '':
                                # call the function
                                validating_loop = False
                                function_name = gpt_response["function_call"]["name"]
                                function_to_call = available_functions[function_name]
                                function_args = json.loads(
                                    gpt_response["function_call"]["arguments"])
                                function_tool = function_to_call(
                                    async_browser=async_browser)
                                function_response = await function_tool._arun(**function_args)

                                gpt_response = await self.ask_gpt(
                                    self._construct_message(role="function", name=function_name, content=function_response))
                                self._write_conversation_history()

                            elif user_loop_input == 'quit':
                                validating_loop = False
                                function_call_loop = False
                                conversation_running = False
                                break

                            elif user_loop_input == 'p':
                                # abort function call and enter new prompt with abort message
                                abort_message = f"I don't want to call function {gpt_response['function_call']['name']} " \
                                    f"with parameters {gpt_response['function_call']['arguments']}. Instead "
                                new_prompt = input(
                                    "Function call cancelled. Enter new prompt.\n")
                                gpt_response = await self.ask_gpt(
                                    self._construct_message(role="user", content=abort_message + new_prompt))
                                validating_loop = False
                            else:
                                print("Please enter e, press enter, p or quit.")
                    else:
                        # no function call, print response and ask for new prompt
                        print(gpt_response)
                        function_call_loop = False
                        break

        file_path = f"tests/{'example'}.spec.ts"
        shutil.move('tempfile', file_path)

        return file_path

    def _get_messages_for_gpt(self):
        # add system and context messages to the conversation
        messages = [
            {"role": "system", "content": self.system_messages}, *self.messages[-10:]]
        return messages

    def _gpt_api_request(self, messages_gpt):
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-0613",
            messages=messages_gpt,
            functions=self.functions,
            function_call="auto",  # auto is default, but we'll be explicit
            temperature=0
        )
        return response

    def _validate_function_call(self, function_call_name, function_call_arguments):
        if function_call_name not in available_functions:
            return False
        return True

    def _construct_message(self, **kwargs):
        return {k: v for k, v in kwargs.items()}

    def _write_conversation_history(self):
        with open('conversation_history.log', 'w') as f:
            f.write(json.dumps(self.messages, indent=4))

    def _get_available_arguments(self, function_call):
        for function in self.functions:
            if function['name'] == function_call:
                return function['parameters']['properties']
        else:
            return None

    def _write_test_header(self):
        with open('tempfile', 'w') as f:
            f.write("import { test, expect } from '@playwright/test';\n\n")
            f.write(
                f"test('{'My example test name'}', async ({{ page }}) => {{\n")

    def _log_message(self, message):
        print(f"{message['role'].upper()}: {message['content']}")

    def _write_test_footer(self):
        with open('tempfile', 'a') as f:
            f.write("});\n\n")


if __name__ == "__main__":
    logging.basicConfig(filename='token_usage.log',
                        encoding='utf-8', level=logging.INFO)
    parser = argparse.ArgumentParser(
        description='Generate playwright typescript code from test specification')
    parser.add_argument()
    args = parser.parse_args()

    open('token_usage.log', 'w').close()
    open('conversation_history.log', 'w').close()

   # Initialize the playwright toolkit / tools
    async_browser = create_async_playwright_browser(headless=False)
    toolkit = PlayWrightBrowserToolkit.from_browser(
        async_browser=async_browser)
    tools = toolkit.get_tools()
    # convert tools from langchain to openai functions
    functions = [format_tool_to_openai_function(t) for t in tools]

    gpt = GPT(functions=functions)
    loop = asyncio.get_event_loop()
    test_file = loop.run_until_complete(
        gpt.user_agent_loop())
    print("Generated playwright typescript code: \n")
    with open(test_file, 'r') as f:
        print(f.read())
