import time

from ai_powered_qa.custom_plugins.playwright_plugin.only_visible import (
    PlaywrightPluginOnlyVisible,
)


def test_only_visible():
    plugin = PlaywrightPluginOnlyVisible()
    plugin.navigate_to_url("https://news.ycombinator.com/")
    context_message = plugin.context_message
    plugin.close()

    # The link is at the bottom of the page and it shouldn't be visible
    assert '<a href="newsguidelines.html">' not in context_message


def test_scroll():
    plugin = PlaywrightPluginOnlyVisible()
    plugin.navigate_to_url("https://news.ycombinator.com/")
    plugin.scroll("body", "up")
    plugin.scroll("body", "up")
    context_message = plugin.context_message
    plugin.close()

    # The link should be visible after scrolling
    assert '<a href="newsguidelines.html">' in context_message
