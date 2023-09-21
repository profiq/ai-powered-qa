import argparse
import asyncio
import sys
import openai
import json
import os
import logging
import shutil
# from playwright_mine import expect_text, go_to_page, take_screenshot, params_to_pass
from test_specification.example import example_test
from langchain.tools import format_tool_to_openai_function

# Improve conversation managment.
# keep track of whole history. Done - we pass all messages to chatgpt
# Let GPT know about the result of function call. Done - we are testing with hardcoded status code and gpt reacts to it.
#                                                   We can add some if condition and gpt can try again or just print it.
# Start stop conversation
# adding context and system messages to conversation
# test how much we can send to the model (max 4k or 16k tokens for gpt 3.5)
# write a login pattern and let gpt decide what to do. Test it.
# Add a context and see if gpt can find if there is a text Seznam on the page. Test it.

# example taken from here https://platform.openai.com/docs/guides/gpt/function-calling

# truncate messages, do nejakeho maximalniho limitu
# moznosti pro vylepseni: aby sam navrhl loginy, convertor html, pridat do kontextu, co je pageobject, zkusit do 16k dat stranku a at vymysli jak se prihlasit
# nahled stranky do kontextu
# now working on adding tools to our agent
    # how to define a tool: https://python.langchain.com/docs/modules/agents/tools/custom_tools
    # now find how to use the tools in out agent
    # Using official langchain, but added some changes from our fork

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
        self.system_messages = "You are helping me to automate UI testing. Find page content in other system messages and you can use it to answer my questions."
        self.functions = functions
        available_functions = {}
        params_to_pass = {}

    async def run_conversation(self, step):
        self.messages.append({"role": "user", "content": step})
        print(f"user: {step}")
        # Step 1: send the conversation and available functions to GPT
        messages_gpt = self.get_messages_for_gpt()
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-0613",
            messages=messages_gpt,
            functions=self.functions,
            function_call="auto",  # auto is default, but we'll be explicit
            temperature=0
        )
        response_message = response["choices"][0]["message"]

        tokens = response["usage"]
        logging.info(f"gpt context window: {messages_gpt}")
        logging.info(f"Tokens used so far (response): {tokens}\n")

        self.messages.append(response_message)
        # Step 2: check if GPT wanted to call a function
        if response_message.get("function_call"):
            # Step 3: call the function
            # Note: the JSON response may not always be valid; be sure to handle errors

            function_name = response_message["function_call"]["name"]
            function_to_call = available_functions[function_name]
            function_args = json.loads(
                response_message["function_call"]["arguments"])
            function_tool = function_to_call(async_browser=async_browser)   
            function_response = await function_tool._arun(**function_args)

            # Step 4: send the info on the function call and function response to GPT
            # extend conversation with assistant's reply
            self.messages.append(
                {
                    "role": "function",
                    "name": function_name,
                    "content": function_response,
                }
            )
            messages_gpt = self.get_messages_for_gpt()
            second_response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo-0613",
                messages=messages_gpt,
                temperature=0
            )  # get a new response from GPT where it can see the function response

            tokens = second_response["usage"]
            logging.info(f"gpt context window:  {messages_gpt}")
            logging.info(f"Tokens used so far (second response): {tokens}\n")

            self.messages.append(second_response["choices"][0]["message"])
            print(f"assistant: {second_response['choices'][0]['message']}")
            print(
                f"Tool response {function_response}")
        else:
            print(f"assistant: {response_message}")

        # print("Messages:")
        # print(self.messages)
        # return self.messages

    async def generate_code(self, scenario, chat_mode=False):
        with open('tempfile', 'w') as f:
            f.write("import { test, expect } from '@playwright/test';\n\n")
            f.write(
                f"test('{'My example test name'}', async ({{ page }}) => {{\n")
        # append a system message to influence the AIs behaviour

        steps = scenario['steps'].splitlines()
        for step in steps:
            await self.run_conversation(step)
            if chat_mode is True:
                while True:
                    user_input = input(
                        "Press enter to continue with next step or press 'y' to add another prompt.")
                    if user_input.lower() not in ['y', '']:
                        print("Please enter 'y' or empty string")
                        continue
                    else:
                        if user_input == 'y':
                            new_step = input("Please enter new prompt: ")
                            await self.run_conversation(new_step)
                        elif user_input == '':
                            break

        with open('logfile', 'a') as f:
            f.write(json.dumps(self.messages, indent=4))
        # write footer
        with open('tempfile', 'a') as f:
            f.write("});\n\n")

        file_path = f"tests/{'example'}.spec.ts"
        shutil.move('tempfile', file_path)

        return file_path

    def get_messages_for_gpt(self):
        # add system and context messages to the conversation
        messages = [{"role": "system", "content": self.system_messages}, {"role": "system", "content": "This is the \
                                                                          page content. text: ['Seznam', 'ball']"},
                    *self.messages[-10:]]
        # , {"role": "system", "content": ""}]
        # *self.messages[-5:]]
        return messages


if __name__ == "__main__":
    logging.basicConfig(filename='token_usage.log',
                        encoding='utf-8', level=logging.INFO)
    open('token_usage.log', 'w').close()
    parser = argparse.ArgumentParser(
        description='Generate playwright typescript code from test specification')
    parser.add_argument(
        "-c", "--chat", help='Chat mode with agent. User can enter own real-time prompts',
        dest='chat_mode', action="store_true")
    args = parser.parse_args()
    open('logfile', 'w').close()

   # Initialize the playwright toolkit / tools
    async_browser = create_async_playwright_browser(headless=False)
    toolkit = PlayWrightBrowserToolkit.from_browser(
        async_browser=async_browser)
    tools = toolkit.get_tools()
    functions = [format_tool_to_openai_function(t) for t in tools]
    for f in functions:
        print(f['name'], f["parameters"]['title'])
        print('\n')
    

    
    # available_functions = {function['name'] : getattr(f"{function['name']}", function['parameters']['title'])() for function in functions}
    # print(available_functions)
    # from langchain.tools.playwright.click import ClickTool
    # available_functions['click_element']._arun() 
    # ClickTool(async_browser=async_browser)._arun()

    # gpt = GPT(functions=functions)
    # loop = asyncio.get_event_loop()
    # test_file = loop.run_until_complete(
    #     gpt.generate_code(example_test, args.chat_mode))
    # print("Generated playwright typescript code: \n")
    # with open(test_file, 'r') as f:
    #     print(f.read())

    # Why is there previous_webpage function? What does it mean???
