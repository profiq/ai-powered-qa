from ai_powered_qa.custom_plugins.playwright_plugin.html_paging import (
    PlaywrightPluginHtmlPaging,
)


def test_html_paging():
    plugin = PlaywrightPluginHtmlPaging()
    plugin.navigate_to_url("https://news.ycombinator.com/")
    context_message = plugin.context_message
    plugin.close()

    # The HTML content is too long to display in one go
    assert "HTML part 1 of" in context_message


def test_move_to_html_part():
    plugin = PlaywrightPluginHtmlPaging()
    plugin.navigate_to_url("https://news.ycombinator.com/")
    context_message_before = plugin.context_message
    plugin.move_to_html_part(2)
    context_message = plugin.context_message
    plugin.close()

    # The HTML content is too long to display in one go
    assert "HTML part 2 of" in context_message
    assert context_message_before != context_message
