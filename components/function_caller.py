import ast
import asyncio

from dotenv import load_dotenv
from playwright.async_api import Browser, async_playwright

from components.playwright_functions import *
from components.utils import amark_invisible_elements, strip_html_to_structure

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

load_dotenv()


async def get_browser() -> Browser:
    browser = await async_playwright().start()
    return await browser.chromium.launch(headless=False)


async def call_function(browser, json_function):
    available_functions = {tool.name: tool for tool in [NavigateFunction, ClickFunction, FillFunction]}
    print(json_function)
    function_to_call = available_functions[json_function.name]
    function_arguments = ast.literal_eval(json_function.arguments)
    function_response = await function_to_call(page=await get_current_page(browser), **function_arguments).arun()

    return function_response


def get_function_list():
    list_of_functions = []
    for function_cls in [NavigateFunction, ClickFunction, FillFunction]:
        function = {"name": function_cls.name,
                    "description": function_cls.description,
                    "parameters": function_cls.parameters}
        list_of_functions.append(function)
    return list_of_functions


async def get_current_page(browser: Browser) -> Page:
    if not browser.contexts:
        context = await browser.new_context()
        return await context.new_page()

    context = browser.contexts[0]

    if not context.pages:
        return await context.new_page()
    return context.pages[-1]


async def get_context_message(browser: Browser):
    page = await get_current_page(browser)
    await amark_invisible_elements(page)

    html_content = await page.content()
    stripped_html = strip_html_to_structure(html_content)

    context_message = f"Here is the current state of the browser:\n" \
                      f"```\n" \
                      f"{stripped_html}\n" \
                      f"```\n"
    return context_message
