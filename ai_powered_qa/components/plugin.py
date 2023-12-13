import inspect
import json
import random
from typing import Any
import docstring_parser
import playwright.sync_api

from abc import ABC
from pydantic import BaseModel, PrivateAttr


TYPE_MAP = {
    "int": "integer",
    "str": "string",
    "float": "number",
    "bool": "boolean",
}


def tool(method):
    """Decorator to mark a method as a tool."""
    method.__tool__ = True
    return method


class Plugin(BaseModel, ABC):
    name: str

    _tools: list = PrivateAttr(default_factory=list)
    # dict of "tool_name" : method that agent can call
    _callable_tools: dict[str, Any] = PrivateAttr(default_factory=dict)

    def __init__(self, **data):
        super().__init__(**data)
        # TODO should plugins have a system message, that would edit the agent system message?
        self._register_tools()

    @property
    def tools(self):
        return self._tools

    def set_tool_description(
        self, tool_name: str, description: str, argument: str | None = None
    ):
        for tool in self._tools:
            if tool["function"]["name"] == tool_name:
                tool_params = tool["function"]["parameters"]["properties"]
                if argument is not None and argument in tool_params:
                    tool_params[argument]["description"] = description
                else:
                    tool["function"]["description"] = description
                break

    def call_tool(self, tool_name: str, **kwargs):
        if tool_name not in self._callable_tools:
            return None
        return self._callable_tools[tool_name](**kwargs)

    def _register_tools(self):
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(method, "__tool__"):
                docstring = inspect.getdoc(method).strip()
                if docstring.startswith("{"):
                    tool_description = json.loads(docstring)
                else:
                    docstring_parsed = docstring_parser.parse(docstring)
                    # TODO find a docstring that can parse what parameters are required
                    tool_description = {
                        "type": "function",
                        "function": {
                            "name": f"{name}",
                            "description": docstring_parsed.short_description,
                            "parameters": {
                                "type": "object",
                                "properties": self._build_param_object(
                                    docstring_parsed.params
                                ),
                            },
                        },
                    }
                self._tools.append(tool_description)
                self._callable_tools[tool_description["function"]
                                     ["name"]] = method

    def _build_param_object(self, params):
        param_object = {}
        for param in params:
            param_object[param.arg_name] = {
                "type": TYPE_MAP.get(param.type_name, param.type_name),
                "description": param.description,
            }
        return param_object


class RandomNumberPlugin(Plugin):
    name: str = "RandomNumberPlugin"

    @tool
    def get_random_number(self, min_number: int = 0, max_number: int = 100):
        """
        Returns a random number in the specified range

        :param int min_number: The minimum number
        :param int max_number: The maximum number
        """
        return random.randint(min_number, max_number)

    @tool
    def get_random_normal(self, mean: float = 0, standard_deviation: float = 1):
        """
        {
            "type": "function",
            "function": {
                "name": "get_random_normal",
                "description": "Returns a random number from a normal distribution",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mean": {
                            "type": "number",
                            "description": "The mean of the normal distribution"
                        },
                        "standard_deviation": {
                            "type": "number",
                            "description": "The standard deviation of the normal distribution"
                        }
                    }
                }
            }
        }
        """
        return random.normalvariate(mean, standard_deviation)


class PlaywrightPlugin(Plugin):
    name: str = "PlaywrightPlugin"

    _playwright: playwright.sync_api.Playwright
    _browser: playwright.sync_api.Browser
    _page: playwright.sync_api.Page

    def __init__(self, **data):
        super().__init__(**data)
        self._playwright = playwright.sync_api.sync_playwright().start()
        self._browser = self._playwright.chromium.launch()
        self._page = self._browser.new_page()

    @tool
    def navigate_to_url(self, url: str):
        """
        Navigates to a URL

        :param str url: The URL to navigate to.
        """
        self._page = self.get_current_page(self._browser)
        try:
            response = self._page.goto(url)
        except Exception:
            return f"Unable to navigate to {url}"

        return f"Navigating to {url} returned status code {response.status if response else 'unknown'}"

    @tool
    def click_element(self, selector: str, index: int = 0, timeout: int = 3_000) -> str:
        """
        Click on an element with the given CSS selector

        :param str selector: CSS selector for the element to click
        :param int index: Index of the element to click
        :param int timeout: Timeout for Playwright to wait for element to be ready.
        """

        visible_only: bool = True

        def _selector_effective(selector: str, index: int) -> str:
            if not visible_only:
                return selector
            return f"{selector} >> visible=1 >> nth={index}"

        playwright_strict: bool = False
        page = self.get_current_page(self._browser)
        try:
            page.click(selector=_selector_effective(selector, index),
                       strict=playwright_strict,
                       timeout=timeout)
        except TimeoutError:
            return f"Unable to click on element '{selector}'"

        return f"Clicked element '{selector}'"

    @tool
    def fill_element(self, selector: str, text: str, timeout: int = 3000):
        """
        Text input on element in the current web page matching the text content

        :param str selector: Selector for the element by text content.
        :param str text: Text what you want to fill up.
        :param int timeout: Timeout for Playwright to wait for element to be ready.
        """

        page = self.get_current_page(self._browser)
        try:
            page.locator(selector).fill(text, timeout=timeout)
        except Exception:
            return f"Unable to fill up text on element '{selector}'."
        return f"Text input on the element by text, {selector}, was successfully performed."

    @staticmethod
    def get_current_page(browser: playwright.sync_api.Browser) -> playwright.sync_api.Page:
        if not browser.contexts:
            raise Exception("No browser contexts found")
        # Get the first browser context
        context = browser.contexts[0]
        if not context.pages:
            raise Exception("No pages found in the browser context")
        # Get the last page in the context (assuming the last one is the active one)
        page = context.pages[-1]

        return page

    def close(self):
        if self._page:
            self._page.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
