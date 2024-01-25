import asyncio
import json
import re

import playwright.async_api
import playwright.sync_api
from bs4 import BeautifulSoup

from ai_powered_qa.components.plugin import Plugin, tool


class PlaywrightPlugin(Plugin):
    name: str = "PlaywrightPlugin"
    part_length: str = 15000

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
        self._part = 0

    def run_async(self, coroutine):
        asyncio.set_event_loop(self._loop)
        return self._loop.run_until_complete(coroutine)

    @property
    def system_message(self) -> str:
        return """
            You can use Playwright to interact with web pages. You get 
            the HTML content of the current page.

            When working with HTML content you can use the `move_to_html_part`
            tool to move to a specific part of the HTML content. Alway take a 
            short note about what the part contains before moving to a 
            different part.
        """

    @property
    def context_message(self) -> str:
        html = self.run_async(self._get_page_content())
        self.screenshot()
        part, max_parts = self._get_html_part(html)
        return f"Current page content:\n\n ```\n{part}\n``` \n\n Part {self._part + 1} of {max_parts}."

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
        self._part = 0
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
        Click on an element identified by a given CSS selector. Prioritize clicking on interactive
        elements such as buttons and links.

        :param str selector: CSS selector for the element to click
        :param int index: Index of the element to click
        :param int timeout: Timeout for Playwright to wait for element to be ready.
        """
        return self.run_async(self._click_element(selector, index, timeout))

    async def _click_element(
        self, selector: str, index: int = 0, timeout: int = 3_000
    ) -> str:
        playwright_strict: bool = False
        page = await self.ensure_page()
        try:
            selector = f"{selector} >> nth={index}"
            element_exists = await page.is_visible(selector)
            if not element_exists:
                return f"Unable to click on element '{selector}' as it does not exist"
            await page.click(
                selector=selector,
                strict=playwright_strict,
                timeout=timeout,
            )
        except TimeoutError:
            return f"Unable to click on element '{selector}'"

        return f"Clicked element '{selector}'"

    @tool
    def fill_element(self, selector: str, text: str, timeout: int = 3000):
        """
        Fill up a form input element identified by a given CSS selector with a given text

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
    def move_to_html_part(self, part: int):
        """
        Moves to the HTML part at the given index. We split the HTML content of the website
        into multiple smaller parts to avoid reaching the token limit

        :param int part: Index of the HTML part to move to (starts at 1)
        """
        self._part = part - 1
        return f"Moved to HTML part {part}"

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

    def _get_html_part(self, html: str) -> str:
        """
        Splits the HTML content into parts of about self.part_length characters.
        Always performs a split at a tag start character.

        After HTML is split it returns the part at intex self._part

        We split the HTML content into parts to avoid reaching the token limit
        """
        if len(html) < self.part_length:
            return html, 1
        parts = []
        current_part = ""
        for char in html:
            if char == "<" and len(current_part) > self.part_length:
                parts.append(current_part)
                current_part = "<"
            else:
                current_part += char
        parts.append(current_part)
        return parts[self._part], len(parts)


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
    html_clean = re.sub(r"<span[\s]*>[\s]*</span>", "", html_clean)
    html_clean = re.sub(r"<!--[\s\S]*?-->", "", html_clean)
    soup = BeautifulSoup(html_clean, "html.parser")
    _unwrap_single_child(soup)
    _remove_useless_tags(soup)
    html_clean = str(soup)
    html_clean = re.sub(r"[\n]{2,}", "\n", html_clean)
    return html_clean


def _clean_attributes(html: str) -> str:
    regexes = [
        r'class="[^"]*"',
        r'style="[^"]*"',
        r'data-(?!test)[a-zA-Z0-9-]+="[^"]*"',
        r'aria-[a-zA-Z\-]+="[^"]*"',
        r'on[a-zA-Z\-]+="[^"]*"',
        r'role="[^"]*"',
        r'grow="[^"]*"',
        r'transform="[^"]*"',
        r'height="[^"]*"',
        r'width="[^"]*"',
        r'version="[^"]*"',
        r'value="[^"]*"',
        r'values="[^"]*"',
        r'loading="[^"]*"',
        r'decoding="[^"]*"',
        r'srcset="[^"]*"',
        r'sizes="[^"]*"',
        r'fill="[^"]*"',
        r'jsaction="[^"]*"',
        r'jscontroller="[^"]*"',
        r'jsrenderer="[^"]*"',
        r'jsmodel="[^"]*"',
        r'c-wiz="[^"]*"',
        r'jsshadow="[^"]*"',
        r'jsslot="[^"]*"',
        r'dir"[^"]*"',
        r'view[bB]ox="[^"]*"',
        r'media="[^"]*"',
        r'xmlns="[^"]*"',
    ]
    for regex in regexes:
        html = re.sub(regex, "", html)

    return html


def _unwrap_single_child(soup: BeautifulSoup):
    """
    Unwraping means removing a tag but keeping its children. This can again
    save some tokens.
    """
    wrappable_tags = ("d", "span", "i", "b", "strong", "em")

    for tag in soup.find_all(True):
        if (
            len(tag.contents) == 1
            and not isinstance(tag.contents[0], str)
            and tag.name in wrappable_tags
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
        "iframe",
    ]
    for t in soup.find_all(tags_to_remove):
        t.decompose()
