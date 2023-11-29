from ai_powered_qa.components.plugin import RandomNumberPlugin
from ai_powered_qa.components.plugin import PlaywrightPlugin
import pytest


def test_set_system_message():
    plugin = RandomNumberPlugin("You can generate random numbers")
    assert plugin.system_message == "You can generate random numbers"
    plugin.system_message = "You can generate random integers"
    assert plugin.system_message == "You can generate random integers"


def test_automatic_tool_description():
    plugin = RandomNumberPlugin("You can generate random numbers")
    expected_element = {"type": "function", "function": {"name": "get_random_number",
                        "description": "Returns a random number in the specified range",
                                                         "parameters": {"type": "object",
                                                                        "properties": {"min_number": {"type": "integer",
                                                                                                      "description": "The minimum number"},
                                                                                       "max_number": {"type": "integer",
                                                                                                      "description": "The maximum number"}}}}}
    assert expected_element in plugin.tools


def test_tool_description_override():
    plugin = RandomNumberPlugin("You can generate random numbers")
    plugin.set_tool_description(
        "get_random_number",
        "Returns a random integer in the specified range",
    )
    assert (
        plugin.tools[1]["function"]["description"]
        == "Returns a random integer in the specified range"
    )
    plugin.set_tool_description(
        "get_random_number",
        "The low end of the range",
        "min_number",
    )
    assert (
        plugin.tools[1]["function"]["parameters"]["properties"]["min_number"]["description"]
        == "The low end of the range"
    )


def test_custom_tool_description():
    plugin = RandomNumberPlugin("You can generate random numbers")
    assert (
        plugin.tools[0]["function"]["description"]
        == "Returns a random number from a normal distribution"
    )
    assert plugin.tools[0]["function"]["name"] == "get_random_normal"
    properties = plugin.tools[0]["function"]["parameters"]["properties"]
    assert properties["mean"]["description"] == "The mean of the normal distribution"
    assert (
        properties["standard_deviation"]["description"]
        == "The standard deviation of the normal distribution"
    )
    assert properties["mean"]["type"] == "number"
    assert properties["standard_deviation"]["type"] == "number"


def test_playwright_navigate():
    plugin = PlaywrightPlugin("You can interact with web pages")
    tool_name = "navigate_to_url"
    url = "https://www.google.com/"
    response = plugin.call_tool(tool_name, url=url)
    assert response == f"Navigating to {url} returned status code 200"
    assert plugin._page.url == url
    plugin.close()
