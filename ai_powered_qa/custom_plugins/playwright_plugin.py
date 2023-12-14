from ai_powered_qa.components.plugin import Plugin, tool
import playwright.sync_api
import playwright.async_api
import asyncio


class PlaywrightPlugin(Plugin):
    name: str = "PlaywrightPlugin"

    _playwright: playwright.sync_api.Playwright
    _browser: playwright.sync_api.Browser
    _page: playwright.sync_api.Page

    def __init__(self, **data):
        super().__init__(**data)
        self._playwright = playwright.sync_api.sync_playwright().start()
        self._browser = self._playwright.chromium.launch()
        self._page = self._browser.new_page()

    @tool
    def navigate_to_url(self, url: str):
        """
        Navigates to a URL

        :param str url: The URL to navigate to.
        """
        self._page = self.get_current_page(self._browser)
        try:
            response = self._page.goto(url)
        except Exception:
            return f"Unable to navigate to {url}"

        return f"Navigating to {url} returned status code {response.status if response else 'unknown'}"

    @tool
    def click_element(self, selector: str, index: int = 0, timeout: int = 3_000) -> str:
        """
        Click on an element with the given CSS selector

        :param str selector: CSS selector for the element to click
        :param int index: Index of the element to click
        :param int timeout: Timeout for Playwright to wait for element to be ready.
        """

        visible_only: bool = True

        def _selector_effective(selector: str, index: int) -> str:
            if not visible_only:
                return selector
            return f"{selector} >> visible=1 >> nth={index}"

        playwright_strict: bool = False
        page = self.get_current_page(self._browser)
        try:
            page.click(selector=_selector_effective(selector, index),
                       strict=playwright_strict,
                       timeout=timeout)
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

        page = self.get_current_page(self._browser)
        try:
            page.locator(selector).fill(text, timeout=timeout)
        except Exception:
            return f"Unable to fill up text on element '{selector}'."
        return f"Text input on the element by text, {selector}, was successfully performed."

    @staticmethod
    def get_current_page(browser: playwright.sync_api.Browser) -> playwright.sync_api.Page:
        if not browser.contexts:
            raise Exception("No browser contexts found")
        # Get the first browser context
        context = browser.contexts[0]
        if not context.pages:
            raise Exception("No pages found in the browser context")
        # Get the last page in the context (assuming the last one is the active one)
        page = context.pages[-1]

        return page

    def close(self):
        if self._page:
            self._page.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
