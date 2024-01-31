import asyncio
import json
import re

import playwright.async_api
import playwright.sync_api
from bs4 import BeautifulSoup

from ai_powered_qa.components.plugin import Plugin, tool


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
            await page.locator(selector).fill(text, timeout=timeout)
        except Exception:
            return f"Unable to fill up text on element '{selector}'."
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

    # @tool
    # def assert_that(self, selector: str, action: str, value: str = None):
    #     """
    #     Perform an assertion on an element based on its text content.
    #
    #     :param str selector: Selector for the element identified by its text content.
    #     :param str action: [
    #               {
    #                 "option": "is_visible",
    #                 "description": "Check if the element is displayed in the content.",
    #               },
    #               {
    #                 "option": "contain_text",
    #                 "description": "Check if the element contains the specified text content.",
    #               }
    #             ]
    #     :param str value: Text to comparing in action contain_text or None.
    #     """
    #     return self.run_async(self._assert_that(selector, action, value))
    #
    # async def _assert_that(self, selector: str, action: str, value: str = None):
    #     page = await self.ensure_page()
    #
    #     if action == "is_visible":
    #         state = await page.locator(selector).is_visible()
    #         result_message = f"{selector} is {'visible' if state else 'not visible'} in context."
    #     elif action == "contain_text":
    #         text = await page.inner_text(selector)
    #         if text == "":
    #             text = await page.locator(selector).get_attribute("value")
    #         result_message = (
    #             f"{selector} {'contains' if value == text else 'does not contain'} '{value}', "
    #             f"actual value: '{text}'."
    #         )
    #     else:
    #         return "Not implemented action"
    #     return f"Action '{action}' was successfully performed: {result_message}"


    async def ensure_page(self) -> playwright.async_api.Page:
        if not self._page:
            self._playwright = await playwright.async_api.async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=False)
            self._page = await self._browser.new_page()
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
    html_clean = _clean_attributes(html_content)
    html_clean = re.sub(r"<div[\s]*>[\s]*</div>", "", html_clean)
    html_clean = re.sub(r"<!--[\s\S]*?-->", "", html_clean)
    html_clean = html_clean.replace("<div", "<d").replace("</div>", "</d>")
    soup = BeautifulSoup(html_clean, "html.parser")
    _unwrap_single_child(soup)
    _remove_useless_tags(soup)
    return str(soup)


def _clean_attributes(html: str) -> str:
    regexes = [
        r'class="[^"]*"',
        r'style="[^"]*"',
        r'data-(?!test)[a-zA-Z\-]+="[^"]*"',
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
        if len(tag.contents) == 1 and not isinstance(tag.contents[0], str):
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
