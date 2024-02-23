from ai_powered_qa.custom_plugins.playwright_plugin import clean_html
from ai_powered_qa.custom_plugins.playwright_plugin.base import PlaywrightPlugin
from bs4 import BeautifulSoup


def test_playwright_navigate():
    plugin = PlaywrightPlugin()
    tool_name = "navigate_to_url"
    url = "https://opinionet.swarm.svana.name/"
    response = plugin.call_tool(tool_name, url=url)
    assert response == f"Navigating to {url} returned status code 200"
    assert plugin._page.url == url
    assert '<div id="root">' in plugin.context_message
    plugin.close()


def test_playwright_click():
    plugin = PlaywrightPlugin()
    url = "https://bazos.cz/"
    plugin.call_tool("navigate_to_url", url=url)
    plugin.call_tool("click_element", selector="a[href='https://pc.bazos.cz/']")
    assert plugin._page.url == "https://pc.bazos.cz/"
    plugin.close()


def test_playwright_click_incorrect():
    plugin = PlaywrightPlugin()
    url = "https://bazos.cz/"
    plugin.call_tool("navigate_to_url", url=url)
    selector = "a[href='/something-that-doesnt-exist']"
    response = plugin.call_tool("click_element", selector=selector)
    expected = f"Unable to click on element '{selector}'"
    assert response == expected
    plugin.close()


def test_clean_attributes():
    example_html = """
        <html>
            <head>
                <title>Test</title>
                <script src="https://example.com"></script>
            </head>
            <body>
                <div id="root">
                    <!-- This is a comment -->
                    <span id="hi" class="testClass" style="border: 1px solid red">Hello</div>
                    <h1 aria-label="Test" role="cell">Test</h1>
                    <span><a>Test</a></span>
                    <div data-testid="test" data-something="hi">Some test div</div>
                    <div> </div>
                </div>
            </body>
        </html>
    """

    soup = BeautifulSoup(example_html, "html.parser")
    clean_html.clean_attributes(soup)
    clean_html.remove_useless_tags(soup)
    html_cleaned = clean_html.remove_comments(soup.prettify())
    print(html_cleaned)

    # Just a few selected attributes
    assert 'class="testClass"' not in html_cleaned
    assert 'style="border: 1px solid red"' not in html_cleaned
    assert 'aria-label="Test"' not in html_cleaned
    assert 'role="cell"' not in html_cleaned

    # All data attributes are removed with the exception of those whose
    # name starts with "data-test"
    assert 'data-testid="test"' in html_cleaned
    assert 'data-something="hi"' not in html_cleaned

    # Comments are removed
    assert "<!-- This is a comment -->" not in html_cleaned

    # Script tags are removed
    assert '<script src="https://example.com"></script>' not in html_cleaned
