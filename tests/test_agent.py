from ai_powered_qa.components.agent import Agent
from ai_powered_qa.components.plugin import PlaywrightPlugin


def test_agent_with_playwrights():
    agent = Agent()
    agent.add_plugin(PlaywrightPlugin())
    assert len(agent._plugins) == 1
    agent.append_message("user", "Can you open google.com?")
    completion = agent.get_completion("Can you open google.com?")
    assert completion.tool_calls[0].function.name == "PlaywrightPlugin_navigate_to_url"
    agent.append_message("assistant", "", completion.tool_calls)
    plugin: PlaywrightPlugin = agent._plugins[0]
    assert plugin._page.url == "https://www.google.com/"
    plugin.playwright.stop()
