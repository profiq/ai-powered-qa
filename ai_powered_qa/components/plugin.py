import inspect
import json
import random
from abc import ABC
from typing import Any

import docstring_parser
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
        self._register_tools()

    @property
    def context_message(self) -> str:
        return ""

    @property
    def system_message(self) -> str:
        return ""

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
                                "required": self._get_required_params(method),
                            },
                        },
                    }
                self._tools.append(tool_description)
                self._callable_tools[tool_description["function"]["name"]] = method

    def _build_param_object(self, params):
        param_object = {}
        for param in params:
            param_object[param.arg_name] = {
                "type": TYPE_MAP.get(param.type_name, param.type_name),
                "description": param.description,
            }
        return param_object

    def _get_required_params(self, method):
        method_signature = inspect.signature(method)
        required_params = []
        for param_name, param in method_signature.parameters.items():
            if param.default is inspect.Parameter.empty:
                required_params.append(param_name)
        return required_params

    def reset_history(self, history):
        for message in history:
            if "tool_calls" in message:
                for tool_call in message["tool_calls"]:
                    self.call_tool(
                        tool_call["function"]["name"],
                        **json.loads(tool_call["function"]["arguments"]),
                    )


class RandomNumberPlugin(Plugin):
    name: str = "RandomNumberPlugin"

    @tool
    def get_random_number(self, min_number: int, max_number: int = 100):
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
