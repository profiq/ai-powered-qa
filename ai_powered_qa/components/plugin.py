from abc import ABC
import inspect
import random
import json
import playwright.sync_api

import docstring_parser


def tool(method):
    """Decorator to mark a method as a tool."""
    method.__tool__ = True
    return method


class Plugin(ABC):
    TYPE_MAP = {
        "int": "integer",
        "str": "string",
        "float": "number",
        "bool": "boolean",
    }

    def __init__(self, system_message: str = ""):
        self._system_message = system_message
        self._tools = []
        self._register_tools()

    @property
    def tools(self):
        return self._tools

    @property
    def system_message(self) -> str:
        return self._system_message

    @system_message.setter
    def system_message(self, value: str):
        if not isinstance(value, str):
            raise TypeError("system_message must be a string")
        self._system_message = value

    @property
    def context(self) -> str:
        return ""

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
                "type": self.TYPE_MAP.get(param.type_name, param.type_name),
                "description": param.description,
            }
        return param_object


class RandomNumberPlugin(Plugin):
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
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._playwright = playwright.sync_api.sync_playwright().start()
        self._browser = self._playwright.chromium.launch()
        self._page = self._browser.new_page()

    @tool
    def navigate_to_url(self, url: str) :
        """
        Navigates to a URL

        :param str url: The URL to navigate to
        """
        self._page.goto(url)
        return 'OK'
    

    def __del__(self):
        self._page.close()
        self._browser.close()
        self._playwright.stop()
