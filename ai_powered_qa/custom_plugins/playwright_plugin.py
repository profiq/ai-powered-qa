import asyncio
import json
import re

import playwright.async_api
import playwright.sync_api
from bs4 import BeautifulSoup

from ai_powered_qa.components.plugin import Plugin, tool


js_function = """
function updateElementVisibility() {
    const visibilityAttribute = 'data-playwright-visible';

    const previouslyMarkedElements = document.querySelectorAll('[' + visibilityAttribute + ']');
    previouslyMarkedElements.forEach(el => el.removeAttribute(visibilityAttribute));

    function isElementVisibleInViewport(el) {
        const rect = el.getBoundingClientRect();
        const windowHeight = (window.innerHeight || document.documentElement.clientHeight);
        const windowWidth = (window.innerWidth || document.documentElement.clientWidth);
        return (
            rect.top >= 0 && rect.top <= windowHeight && rect.height > 0 &&
            rect.left >= 0 && rect.left <= windowWidth && rect.width > 0
        );
    }

    const allElements = document.querySelectorAll('*');
    allElements.forEach(el => {
        if (isElementVisibleInViewport(el)) {
            el.setAttribute(visibilityAttribute, 'true');
        }
    });
}
window.updateElementVisibility = updateElementVisibility;

function updateElementScrollability() {
    const scrollableAttribute = 'data-playwright-scrollable';

    // First, clear the attribute from all elements
    const previouslyMarkedElements = document.querySelectorAll('[' + scrollableAttribute + ']');
    previouslyMarkedElements.forEach(el => el.removeAttribute(scrollableAttribute));

    // Function to check if an element is scrollable
    function isElementScrollable(el) {
        const hasScrollableContent = el.scrollHeight > el.clientHeight || el.scrollWidth > el.clientWidth;
        const overflowStyle = window.getComputedStyle(el).overflow + window.getComputedStyle(el).overflowX + window.getComputedStyle(el).overflowY;
        return hasScrollableContent && /(auto|scroll)/.test(overflowStyle);
    }

    // Mark all scrollable elements
    const allElements = document.querySelectorAll('*');
    allElements.forEach(el => {
        if (isElementScrollable(el)) {
            el.setAttribute(scrollableAttribute, 'true');
        }
    });
}
window.updateElementScrollability = updateElementScrollability;
"""


class PlaywrightPlugin(Plugin):
    name: str = "PlaywrightPlugin"

    _playwright: playwright.async_api.Playwright
    _browser: playwright.async_api.Browser
    _page: playwright.async_api.Page
    _buffer: bytes

    @property
    def buffer(self) -> bytes:
        return bytes(self._buffer)

    def __init__(self, **data):
        super().__init__(**data)
        self._playwright = None
        self._browser = None
        self._page = None
        self._buffer = None
        self._loop = asyncio.new_event_loop()

    def run_async(self, coroutine):
        asyncio.set_event_loop(self._loop)
        return self._loop.run_until_complete(coroutine)

    @property
    def system_message(self) -> str:
        return """
            You can use Playwright to interact with web pages. You always get 
            the HTML content of the current page. There is one caveat though:
            You need to handle all <d> tags as if they were <div> tags.
        """

    @property
    def context_message(self) -> str:
        html = self.run_async(self._get_page_content())
        self.screenshot()
        return f"Current page content:\n\n ```\n{html}\n```"

    async def _get_page_content(self):
        page = await self.ensure_page()
        if page.url == "about:blank":
            return "No page loaded yet."
        await page.evaluate("window.updateElementVisibility()")
        await page.evaluate("window.updateElementScrollability()")
        html_content = await page.content()
        stripped_html = clean_html(html_content)
        return stripped_html

    @tool
    def navigate_to_url(self, url: str):
        """
        Navigates to a URL

        :param str url: The URL to navigate to.
        """
        return self.run_async(self._navigate_to_url(url))

    async def _navigate_to_url(self, url: str):
        page = await self.ensure_page()
        try:
            response = await page.goto(url)
        except Exception:
            return f"Unable to navigate to {url}."

        return f"Navigating to {url} returned status code {response.status if response else 'unknown'}"

    @tool
    def click_element(self, selector: str, index: int = 0, timeout: int = 3_000) -> str:
        """
        Click on an element with the given CSS selector

        :param str selector: CSS selector for the element to click
        :param int index: Index of the element to click
        :param int timeout: Timeout for Playwright to wait for element to be ready.
        """
        return self.run_async(self._click_element(selector, index, timeout))

    async def _click_element(
        self, selector: str, index: int = 0, timeout: int = 3_000
    ) -> str:
        visible_only: bool = True

        def _selector_effective(selector: str, index: int) -> str:
            if not visible_only:
                return selector
            return f"{selector} >> visible=1 >> nth={index}"

        playwright_strict: bool = False
        page = await self.ensure_page()
        try:
            selector = _selector_effective(selector, index)
            element_exists = await page.is_visible(selector)
            if not element_exists:
                return f"Unable to click on element '{selector}' as it does not exist"
            await page.click(
                selector=_selector_effective(selector, index),
                strict=playwright_strict,
                timeout=timeout,
            )
        except TimeoutError:
            return f"Unable to click on element '{selector}'"

        return f"Clicked element '{selector}'"

    @tool
    def fill_element(self, selector: str, text: str, timeout: int = 3000):
        """
        Text input on element in the current web page matching the text content

        :param str selector: Selector for the element by text content.
        :param str text: Text what you want to fill up.
        :param int timeout: Timeout for Playwright to wait for element to be ready.
        """

        return self.run_async(self._fill_element(selector, text, timeout))

    async def _fill_element(self, selector: str, text: str, timeout: int = 3000):
        page = await self.ensure_page()
        try:
            await page.locator(_selector_visible(selector)).fill(text, timeout=timeout)
        except Exception as e:
            print(e)
            return f"Unable to fill element. {e}"
        return f"Text input on the element by text, {selector}, was successfully performed."

    @tool
    def select_option(self, selector: str, value: str):
        """
        Select an option from a dropdown element identified by its text content.

        :param str selector: Selector for the element identified by its text content.
        :param str value: Text content of the option to select.
        """
        return self.run_async(self._select_option(selector, value))

    async def _select_option(self, selector: str, value: str):
        page = await self.ensure_page()
        try:
            await page.select_option(selector, value)
        except Exception:
            return f"Unable to select option '{value}' on element '{selector}'."
        return f"Option '{value}' on element '{selector}' was successfully selected."

    @tool
    def assert_that(self, selector: str, action: str, value: str = None):
        """
        Perform an assertion on an element based on its text content.

        :param str selector: Selector for the element identified by its text content.
        :param str action: [
                  {
                    "option": "is_visible",
                    "description": "Check if the element is displayed in the content.",
                  },
                  {
                    "option": "contain_text",
                    "description": "Check if the element contains the specified text content.",
                  }
                ]
        :param str value: Text to comparing in action contain_text or None.
        """
        return self.run_async(self._assert_that(selector, action, value))

    async def _assert_that(self, selector: str, action: str, value: str = None):
        page = await self.ensure_page()

        if action == "is_visible":
            state = await page.locator(selector).is_visible()
            result_message = (
                f"{selector} is {'visible' if state else 'not visible'} in context."
            )
        elif action == "contain_text":
            text = await page.inner_text(selector)
            if text == "":
                text = await page.locator(selector).get_attribute("value")
            result_message = (
                f"{selector} {'contains' if value == text else 'does not contain'} '{value}', "
                f"actual value: '{text}'."
            )
        else:
            return "Not implemented action"
        return f"Action '{action}' was successfully performed: {result_message}"

    @tool
    def scroll(self, selector: str, direction: str):
        """
        Scroll up or down in a selected scroll container

        :param str selector: CSS selector for the scroll container
        :param str direction: Direction to scroll in. Either 'up' or 'down'
        """
        return self.run_async(self._scroll(selector, direction))

    async def _scroll(self, selector: str, direction: str):
        page = await self.ensure_page()
        try:
            bounds = await page.locator(selector).bounding_box()
            if not bounds:
                return f"Unable to scroll in element '{selector}' as it does not exist"
            x = bounds["x"] + bounds["width"] / 2
            y = bounds["y"] + bounds["height"] / 2
            delta = bounds["height"] * 0.8
            await page.mouse.move(x=x, y=y)
            if direction == "up":
                await page.mouse.wheel(delta_y=-delta, delta_x=0)
            elif direction == "down":
                await page.mouse.wheel(delta_y=delta, delta_x=0)
            else:
                return f"Unable to scroll in element '{selector}' as direction '{direction}' is not supported"

        except Exception as e:
            print(e)
            return f"Unable to scroll. {e}"
        return f"Scrolling in {direction} direction was successfully performed."

    async def ensure_page(self) -> playwright.async_api.Page:
        if not self._page:
            self._playwright = await playwright.async_api.async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=False)
            browser_context = await self._browser.new_context()
            await browser_context.add_init_script(js_function)
            self._page = await browser_context.new_page()
        return self._page

    def close(self):
        self.run_async(self._close())

    async def _close(self):
        if self._page:
            await self._page.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    def reset_history(self, history):
        self.close()
        self._playwright = None
        self._browser = None
        self._page = None
        for message in history:
            if "tool_calls" in message:
                for tool_call in message["tool_calls"]:
                    self.call_tool(
                        tool_call["function"]["name"],
                        **json.loads(tool_call["function"]["arguments"]),
                    )

    def screenshot(self):
        self.run_async(self._screenshot())

    async def _screenshot(self):
        page = await self.ensure_page()
        self._buffer = await page.screenshot()


def clean_html(html_content):
    """
    Cleans the web page HTML content from irrelevant tags and attributes
    to save tokens.

    There are two controversial actions here:
    - We replace <div> with <d> as they are very common.
    - The _clean_attributes function removes all `data-` attributes
    """
    soup = BeautifulSoup(html_content, "html.parser")
    _remove_not_visible(soup)
    _remove_useless_tags(soup)
    _unwrap_single_child(soup)
    html_clean = str(soup)
    html_clean = _clean_attributes(html_clean)
    html_clean = re.sub(r"<div[\s]*>[\s]*</div>", "", html_clean)
    html_clean = re.sub(r"<!--[\s\S]*?-->", "", html_clean)
    # html_clean = html_clean.replace("<div", "<d").replace("</div>", "</d>")
    return html_clean


def _remove_not_visible(soup: BeautifulSoup):
    to_keep = set()
    visible_elements = soup.find_all(attrs={"data-playwright-visible": True})
    for element in visible_elements:
        current = element
        while current is not None:
            if current in to_keep:
                break
            to_keep.add(current)
            current = current.parent

    for element in soup.find_all(True):
        if element.name and element not in to_keep:
            element.decompose()


def _clean_attributes(html: str) -> str:
    regexes = [
        r'class="[^"]*"',
        r'style="[^"]*"',
        r'data-(?!test|playwright-scrollable)[a-zA-Z\-]+="[^"]*"',
        r'aria-[a-zA-Z\-]+="[^"]*"',
        r'on[a-zA-Z\-]+="[^"]*"',
        r'role="[^"]*"',
        r'grow="[^"]*"',
        r'transform="[^"]*"',
        r'height="[^"]*"',
        r'width="[^"]*"',
        r'jsaction="[^"]*"',
        r'jscontroller="[^"]*"',
        r'jsrenderer="[^"]*"',
        r'jsmodel="[^"]*"',
        r'c-wiz="[^"]*"',
        r'jsshadow="[^"]*"',
        r'jsslot="[^"]*"',
        r'dir"[^"]*"',
    ]
    for regex in regexes:
        html = re.sub(regex, "", html)

    return html


def _unwrap_single_child(soup: BeautifulSoup):
    """
    Unwraping means removing a tag but keeping its children. This can again
    save some tokens.
    """
    for tag in soup.find_all(True):
        if (
            len(tag.contents) == 1
            and not isinstance(tag.contents[0], str)
            and not tag.name in ["button", "input", "a", "select", "textarea"]
        ):
            tag.unwrap()


def _remove_useless_tags(soup):
    tags_to_remove = [
        "path",
        "meta",
        "link",
        "noscript",
        "script",
        "style",
    ]
    for t in soup.find_all(tags_to_remove):
        t.decompose()


def _selector_visible(selector: str) -> str:
    if ":visible" not in selector:
        return f"{selector}:visible"
    return selector
