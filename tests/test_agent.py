from ai_powered_qa.components.agent import Agent
from ai_powered_qa.components.plugin import PlaywrightPlugin


def test_agent_playwright_response():
    agent = Agent()
    plugin = PlaywrightPlugin()
    agent.add_plugin(plugin)
    assert len(agent._plugins) == 1
    completion = agent.generate_interaction("Can you open google.com?")
    assert completion.tool_calls[0].function.name == "navigate_to_url"
    agent.commit_interaction("assistant", "", completion.tool_calls)
    assert agent._plugins["PlaywrightPlugin"]._page.url == "https://www.google.com/"
    completion = agent.generate_interaction()  # Agent reacts to the tool call
    plugin.close()


def test_agent_parallel_tool_call():
    agent = Agent()
    plugin = PlaywrightPlugin()
    agent.add_plugin(plugin)
    completion = agent.generate_interaction(
        "Navigate to gmail, youtube and google.com")
    assert len(completion.tool_calls) == 3
    plugin.close()


def test():
    agent = Agent()
    plugin = PlaywrightPlugin()
    agent.add_plugin(plugin)
    completion = agent.generate_interaction(
        "Navigate to gmail")
    plugin.close()
