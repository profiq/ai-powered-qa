import asyncio
from inspect import cleandoc
import json
from typing import Any

from bs4 import BeautifulSoup
from openai import OpenAI
import playwright.async_api
from pydantic import Field

from ai_powered_qa import config
from ai_powered_qa.components.plugin import Plugin, tool

from . import clean_html


class PageNotLoadedException(Exception):
    pass


DESCRIBE_HTML_SYSTEM_MESSAGE = cleandoc(
    """
    You are an HTML interpreter assisting in web automation. Given HTML code of a page, you should return a natural language description of how the page probably looks.
    Be specific and exhaustive. 
    Mention all elements that can be interactive.
    Describe the state of all form elements, the value of each input is provided as the `data-playwright-value` attribute.
    Mention all elements that are scrollable (these are marked with the `data-playwright-scrollable` attribute).
    """
)

CONTEXT_TEMPLATE = cleandoc(
    """
    Here is the HTML of the current page:

    ```html
    {html}
    ```

    And here is a description of the page:
    ```text
    {description}
    ```
    """
)

GENERATE_SELECTOR_SCRIPT = cleandoc(
    """
    (([x, y]) => {
        // Find the element at the given coordinates.
        const element = document.elementFromPoint(x, y);
        if (!element) return '';

        let path = '';
        for (let current = element; current && current !== document.body; current = current.parentElement) {
            let selector = current.localName; // Always include the tag name.

            // Include the ID if present.
            if (current.id) {
                selector += `#${current.id}`;
            }

            // Include class names if present.
            if (current.className && typeof current.className === 'string') {
                const classes = current.className.trim().split(/\s+/).join('.');
                if (classes) {
                    selector += `.${classes}`;
                }
            }

            // Include data-test-id if present.
            const testId = current.getAttribute('data-test-id');
            if (testId) {
                selector += `[data-test-id='${testId}']`;
            }

            // Prepend the current selector to the path with a ' > ' if path is not empty.
            path = selector + (path ? ' > ' + path : '');
        }

        // Prepend 'body' tag to the path as the starting point.
        return 'body' + (path ? ' > ' + path : '');
    })
    """
)


class PlaywrightPlugin(Plugin):
    name: str = "PlaywrightPlugin"
    client: Any = Field(default_factory=OpenAI, exclude=True)

    _playwright: playwright.async_api.Playwright | None
    _browser: playwright.async_api.Browser | None
    _page: playwright.async_api.Page | None
    _buffer: bytes | None

    def __init__(self, **data):
        super().__init__(**data)
        self._playwright = None
        self._browser = None
        self._page = None
        self._buffer = None
        self._loop = asyncio.new_event_loop()

    @property
    def system_message(self) -> str:
        return cleandoc(
            """
            You can use Playwright to interact with web pages. You always get 
            the HTML content of the current page
            """
        )

    @property
    def context_message(self) -> str:
        self._run_async(self._screenshot())
        try:
            html = self._run_async(self._get_page_content())
        except PageNotLoadedException:
            html = "No page loaded yet."
            description = "The browser is empty"
        else:
            description = self._get_html_description(html)
        return CONTEXT_TEMPLATE.format(html=html, description=description)

    @property
    def buffer(self) -> bytes:
        return bytes(self._buffer) if self._buffer else b""

    def get_selector_for_coordinates(self, x, y):
        return self.run_async(self._get_selector_from_coordinates(x, y))

    async def _get_selector_from_coordinates(self, x, y):
        page = await self.ensure_page()
        selector = await page.evaluate(GENERATE_SELECTOR_SCRIPT, [x, y])
        return selector

    def get_elements_count_for_selector(self, selector: str):
        selector = self._enhance_selector(selector)
        return self.run_async(self._get_elements_count_for_selector(selector))

    async def _get_elements_count_for_selector(self, selector: str):
        page = await self.ensure_page()
        count = await page.locator(selector).count()
        return count

    @tool
    def navigate_to_url(self, url: str):
        """
        Navigates to a URL

        :param str url: The URL to navigate to.
        """
        return self._run_async(self._navigate_to_url(url))

    async def _navigate_to_url(self, url: str):
        page = await self._ensure_page()
        try:
            response = await page.goto(url, wait_until="domcontentloaded")
        except Exception as e:
            print(e)
            return f"Unable to navigate to {url}."

        status = response.status if response else "unknown"
        return f"Navigating to {url} returned status code {status}"

    @tool
    def click_element(self, selector: str) -> str:
        """
        Click on an element with the given CSS selector.

        :param str selector: CSS selector for the element to click. Be as specific as possible with the selector to ensure only one item is clicked.
        """
        return self._run_async(self._click_element(selector))

    async def _click_element(self, selector: str) -> str:
        timeout = config.PLAYWRIGHT_TIMEOUT
        page = await self._ensure_page()
        try:
            selector = self._enhance_selector(selector)

            # Count the number of elements that match the selector
            element_count = await page.locator(selector).count()

            # If no elements found
            if element_count == 0:
                raise Exception(f"No element found for selector: {selector}")

            # If more than one element found
            if element_count > 1:
                raise Exception("Selector returned more than one element.")
            await page.click(
                selector=selector,
                timeout=timeout,
            )
        except TimeoutError:
            return f"Element did not become clickable within {timeout}ms. It might be obscured by another element."
        except Exception as e:
            print(e)
            return f"Unable to click on element. {e}"

        return f"Element clicked successfully."

    @tool
    def fill_element(self, selector: str, text: str):
        """
        Fill a text input element with a specific text

        :param str selector: Selector for the input element you want to fill in.
        :param str text: Text you want to fill in.
        """

        return self._run_async(self._fill_element(selector, text))

    async def _fill_element(self, selector: str, text: str):
        page = await self._ensure_page()
        try:
            await page.locator(self._enhance_selector(selector)).fill(
                text, timeout=config.PLAYWRIGHT_TIMEOUT
            )
        except Exception as e:
            print(e)
            return f"Unable to fill element. {e}"
        return f"Text input was successfully performed."

    @tool
    def select_option(self, selector: str, value: str):
        """
        Select an option from a dropdown element identified by its text content.

        :param str selector: Selector for the element identified by its text content.
        :param str value: Text content of the option to select.
        """
        return self._run_async(self._select_option(selector, value))

    async def _select_option(self, selector: str, value: str):
        page = await self._ensure_page()
        try:
            await page.locator(selector).first.select_option(value)
        except Exception:
            return f"Unable to select option '{value}' on element '{selector}'."
        return f"Option '{value}' was successfully selected."

    @tool
    def press_enter(self):
        """
        Press the Enter key. This can be useful for submitting forms that
        don't have a submit button.
        """
        return self._run_async(self._press_enter())

    async def _press_enter(self):
        page = await self._ensure_page()
        try:
            await page.keyboard.press("Enter")
        except Exception as e:
            print(e)
            return f"Unable to press Enter. {e}"
        return "Enter key was successfully pressed."

    @tool
    def assert_that(self, selector: str, action: str, value: str | None = None):
        """
        {
            "type": "function",
            "function": {
                "name": "assert_that",
                "description": "Perform an assertion on an element based on its text content",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {
                            "type": "string",
                            "description": "Playwright-compatible selector for the element to test"
                        },
                        "action": {
                            "type": "string",
                            "description": "The assertion action to perform on the element",
                            "enum": ["is_visible", "contain_text"]
                        },
                        "value": {
                            "type": "string",
                            "description": "Value to compare to the element's text content"
                        }
                    },
                    "required": ["selector", "action"]
                }
            }
        }
        """
        return self._run_async(self._assert_that(selector, action, value))

    async def _assert_that(self, selector: str, action: str, value: str | None = None):
        page = await self._ensure_page()
        if action == "is_visible":
            visible = await page.locator(selector).first.is_visible()
            result_message = f"{selector} is {'not ' if not visible else ''}visible."
        elif action == "contain_text":
            text = await page.inner_text(selector)
            if text == "":
                text = await page.locator(selector).first.get_attribute("value")
            contain_string = "contains" if value == text else "does not contain"
            result_message = (
                f"{selector} {contain_string} {value}', ",
                f"actual value: '{text}'.",
            )
        else:
            return "Action not implemented"
        return f"Action '{action}' was successfully performed: {result_message}"

    def close(self):
        self._run_async(self._close())

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
        super().reset_history(history)

    async def _get_page_content(self):
        page = await self._ensure_page()
        if page.url == "about:blank":
            raise PageNotLoadedException("No page loaded yet.")
        html = await page.content()
        html_clean = self._clean_html(html)
        return html_clean

    @staticmethod
    def _clean_html(html: str) -> str:
        """
        Cleans the web page HTML content from irrelevant tags and attributes
        to save tokens.
        """
        soup = BeautifulSoup(html, "html.parser")
        clean_html.remove_useless_tags(soup)
        clean_html.clean_attributes(soup)
        html_clean = soup.prettify()
        html_clean = clean_html.remove_comments(html_clean)
        return html_clean

    def _get_html_description(self, html):
        completion = self.client.chat.completions.create(
            model=config.MODEL_DEFAULT,
            temperature=config.TEMPERATURE_DEFAULT,
            messages=[
                {"role": "system", "content": DESCRIBE_HTML_SYSTEM_MESSAGE},
                {"role": "user", "content": html},
            ],
        )
        return completion.choices[0].message.content

    async def _ensure_page(self) -> playwright.async_api.Page:
        if not self._page:
            self._playwright = await playwright.async_api.async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=False)
            browser_context = await self._browser.new_context()
            self._page = await browser_context.new_page()
        return self._page

    async def _screenshot(self):
        page = await self._ensure_page()
        self._buffer = await page.screenshot()

    def _run_async(self, coroutine):
        asyncio.set_event_loop(self._loop)
        return self._loop.run_until_complete(coroutine)

    def _enhance_selector(self, selector):
        return selector
