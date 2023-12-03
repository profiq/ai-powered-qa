import inspect
import json
import random
from typing import Any, List
import docstring_parser
import playwright.sync_api

from abc import ABC, abstractmethod
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

    _tools: List[Any] = PrivateAttr(default_factory=list)

    def __init__(self, **data):
        super().__init__(**data)
        self._register_tools()

    @property
    def tools(self):
        return self._tools

    def get_tools_for_gpt(self):
        tools = [{"type": "function", "function": t[0]} for t in self._tools]

        return tools

    def call_tool(self, tool_name: str, **kwargs):
        for tool in self._tools:
            if tool[0]["name"] == tool_name:
                return tool[1](**kwargs)
        return None

    def set_tool_description(
        self, tool_name: str, description: str, argument: str | None = None
    ):
        for tool in self._tools:
            if tool[0]["name"] == tool_name:
                tool_params = tool[0]["parameters"]["properties"]
                if argument is not None and argument in tool_params:
                    tool_params[argument]["description"] = description
                else:
                    tool[0]["description"] = description
                break

    def _register_tools(self):
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(method, "__tool__"):
                docstring = inspect.getdoc(method).strip()
                if docstring.startswith("{"):
                    tool_description = json.loads(docstring)
                else:
                    docstring_parsed = docstring_parser.parse(docstring)
                    tool_description = {
                        "name": f"{self.__class__.__name__}_{name}",
                        "description": docstring_parsed.short_description,
                        "parameters": {
                            "type": "object",
                            "properties": self._build_param_object(
                                docstring_parsed.params
                            ),
                        },
                    }
                self._tools.append((tool_description, method))

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
            "name": "RandomNumberPlugin_get_random_normal",
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

        :param str url: The URL to navigate to
        """
        self._page.goto(url)
        return "OK"

    @property
    def playwright(self):
        return self._playwright

    def __del__(self):
        self._playwright.stop()
