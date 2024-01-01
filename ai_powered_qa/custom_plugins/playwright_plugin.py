import asyncio
import json
import playwright.sync_api
import playwright.async_api

from ai_powered_qa.components.plugin import Plugin, tool


class PlaywrightPlugin(Plugin):
    name: str = "PlaywrightPlugin"

    _playwright: playwright.async_api.Playwright
    _browser: playwright.async_api.Browser
    _page: playwright.async_api.Page

    def __init__(self, **data):
        super().__init__(**data)
        self._playwright = None
        self._browser = None
        self._page = None
        self._loop = asyncio.new_event_loop()

    def run_async(self, coroutine):
        asyncio.set_event_loop(self._loop)
        return self._loop.run_until_complete(coroutine)

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
        except Exception as e:
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
            if message["role"] == "tool":
                for tool_call in message["tool_calls"]:
                    self.call_tool(
                        tool_call["function"]["name"],
                        **json.loads(tool_call["function"]["arguments"]),
                    )
