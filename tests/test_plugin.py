from ai_powered_qa.components.plugin import RandomNumberPlugin
from ai_powered_qa.components.plugin import PlaywrightPlugin


def test_set_system_message():
    plugin = RandomNumberPlugin("You can generate random numbers")
    assert plugin.system_message == "You can generate random numbers"
    plugin.system_message = "You can generate random integers"
    assert plugin.system_message == "You can generate random integers"


def test_automatic_tool_description():
    plugin = RandomNumberPlugin("You can generate random numbers")
    assert (
        plugin.tools[1][0]["description"]
        == "Returns a random number in the specified range"
    )
    assert plugin.tools[1][0]["name"] == "RandomNumberPlugin_get_random_number"
    properties = plugin.tools[1][0]["parameters"]["properties"]
    assert properties["min_number"]["description"] == "The minimum number"
    assert properties["max_number"]["description"] == "The maximum number"
    assert properties["min_number"]["type"] == "integer"
    assert properties["max_number"]["type"] == "integer"


def test_tool_description_override():
    plugin = RandomNumberPlugin("You can generate random numbers")
    plugin.set_tool_description(
        "RandomNumberPlugin_get_random_number",
        "Returns a random integer in the specified range",
    )
    assert (
        plugin.tools[1][0]["description"]
        == "Returns a random integer in the specified range"
    )
    plugin.set_tool_description(
        "RandomNumberPlugin_get_random_number",
        "The low end of the range",
        "min_number",
    )
    assert (
        plugin.tools[1][0]["parameters"]["properties"]["min_number"]["description"]
        == "The low end of the range"
    )


def test_custom_tool_description():
    plugin = RandomNumberPlugin("You can generate random numbers")
    assert (
        plugin.tools[0][0]["description"]
        == "Returns a random number from a normal distribution"
    )
    assert plugin.tools[0][0]["name"] == "RandomNumberPlugin_get_random_normal"
    properties = plugin.tools[0][0]["parameters"]["properties"]
    assert properties["mean"]["description"] == "The mean of the normal distribution"
    assert (
        properties["standard_deviation"]["description"]
        == "The standard deviation of the normal distribution"
    )
    assert properties["mean"]["type"] == "number"
    assert properties["standard_deviation"]["type"] == "number"


def test_playwright_plugin():
    plugin = PlaywrightPlugin("You can interact with web pages")
    plugin.tools[0][1]("https://www.google.com/")
    assert plugin._page.url == "https://www.google.com/"
