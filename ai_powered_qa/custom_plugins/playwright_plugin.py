import asyncio
import json
import re

from typing import Any
from openai import OpenAI
from pydantic import Field

import playwright.async_api
from playwright.async_api import TimeoutError
from bs4 import BeautifulSoup

from ai_powered_qa.components.plugin import Plugin, tool


js_function = """
function updateElementVisibility() {
    const visibilityAttribute = 'data-playwright-visible';

    // Remove the visibility attribute from elements that were previously marked
    const previouslyMarkedElements = document.querySelectorAll('[' + visibilityAttribute + ']');
    previouslyMarkedElements.forEach(el => el.removeAttribute(visibilityAttribute));

    // Function to check if an element is visible in the viewport
    function isElementVisibleInViewport(el) {
        const rect = el.getBoundingClientRect();
        const windowHeight = (window.innerHeight || document.documentElement.clientHeight);
        const windowWidth = (window.innerWidth || document.documentElement.clientWidth);

        const hasSize = rect.width > 0 && rect.height > 0;

        const startsWithinVerticalBounds = rect.top >= 0 && rect.top <= windowHeight;
        const endsWithinVerticalBounds = rect.bottom >= 0 && rect.bottom <= windowHeight;
        const overlapsVerticalBounds = rect.top <= 0 && rect.bottom >= windowHeight;

        const startsWithinHorizontalBounds = rect.left >= 0 && rect.left <= windowWidth;
        const endsWithinHorizontalBounds = rect.right >= 0 && rect.right <= windowWidth;
        const overlapsHorizontalBounds = rect.left <= 0 && rect.right >= windowWidth;

        const verticalOverlap = startsWithinVerticalBounds || endsWithinVerticalBounds || overlapsVerticalBounds;
        const horizontalOverlap = startsWithinHorizontalBounds || endsWithinHorizontalBounds || overlapsHorizontalBounds;

        const isInViewport = hasSize && verticalOverlap && horizontalOverlap;

        // Get computed styles to check for visibility and opacity
        const style = window.getComputedStyle(el);
        const isVisible = style.opacity !== '0' && style.visibility !== 'hidden';

        // The element is considered visible if it's within the viewport and not explicitly hidden or fully transparent
        return isInViewport && isVisible;
    }

    // Check all elements in the document
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

    function isWindowScrollable() {
        return document.documentElement.scrollHeight > window.innerHeight;
    }

    // Function to check if an element is scrollable
    function isElementScrollable(el) {
        if (el === document.body) {
            return isWindowScrollable();
        }
        const hasScrollableContent = el.scrollHeight > el.clientHeight;
        const overflowStyle = window.getComputedStyle(el).overflow + window.getComputedStyle(el).overflowX;
        return hasScrollableContent && /(auto|scroll)/.test(overflowStyle);
    }

    // Mark all scrollable elements
    const allElements = document.querySelectorAll('[data-playwright-visible]');
    allElements.forEach(el => {
        if (isElementScrollable(el)) {
            el.setAttribute(scrollableAttribute, 'true');
        }
    });
}
window.updateElementScrollability = updateElementScrollability;

function setValueAsDataAttribute() {
    const inputs = document.querySelectorAll('input, textarea, select');

    inputs.forEach(input => {
        const value = input.value;
        input.setAttribute('data-playwright-value', value);
    });
}
window.setValueAsDataAttribute = setValueAsDataAttribute;
"""

generate_selector_script = """(([x, y]) => {
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

describe_html_system_message = """You are an HTML interpreter assisting in web automation. Given HTML code of a page, you should return a natural language description of how the page probably looks.
Be specific and exhaustive. 
Mention all elements that can be interactive.
Describe the state of all form elements, the value of each input is provided as the `data-playwright-value` attribute.
Mention all elements that are scrollable (these are marked with the `data-playwright-scrollable` attribute).
"""

context_template = """Here is the HTML of the current page:
```html
{html}
```
And here is a description of the page:
```text
{description}
```
"""


class PlaywrightPlugin(Plugin):
    name: str = "PlaywrightPlugin"

    client: Any = Field(default_factory=OpenAI, exclude=True)

    _playwright: playwright.async_api.Playwright
    _browser: playwright.async_api.Browser
    _page: playwright.async_api.Page
    _buffer: bytes

    @property
    def buffer(self) -> bytes:
        return bytes(self._buffer)

    def get_selector_for_coordinates(self, x, y):
        return self.run_async(self._get_selector_from_coordinates(x, y))

    async def _get_selector_from_coordinates(self, x, y):
        page = await self.ensure_page()
        selector = await page.evaluate(generate_selector_script, [x, y])
        return selector

    def get_elements_count_for_selector(self, selector: str):
        return self.run_async(self._get_elements_count_for_selector(selector))

    async def _get_elements_count_for_selector(self, selector: str):
        page = await self.ensure_page()
        count = await page.locator(selector).count()
        return count

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
        if html.startswith("No page loaded yet."):
            return context_template.format(
                html=html,
                description="The browser is empty",
            )
        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            temperature=0,
            messages=[
                {"role": "system", "content": describe_html_system_message},
                {"role": "assistant", "content": html},
            ],
        )
        return context_template.format(
            html=html,
            description=completion.choices[0].message.content,
        )

    async def _get_page_content(self):
        page = await self.ensure_page()
        if page.url == "about:blank":
            return "No page loaded yet."
        await page.evaluate("window.updateElementVisibility()")
        await page.evaluate("window.updateElementScrollability()")
        await page.evaluate("window.setValueAsDataAttribute()")
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
    def click_element(self, selector: str) -> str:
        """
        Click on an element with the given CSS selector.

        :param str selector: CSS selector for the element to click. Be as specific as possible with the selector to ensure only one item is clicked.
        """
        return self.run_async(self._click_element(selector))

    async def _click_element(self, selector: str) -> str:
        timeout = 3_000
        page = await self.ensure_page()
        try:
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

        return self.run_async(self._fill_element(selector, text))

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

    # @tool
    # def assert_that(self, selector: str, action: str, value: str = None):
    #     """
    #     Perform an assertion on an element based on its text content.

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

    # async def _assert_that(self, selector: str, action: str, value: str = None):
    #     page = await self.ensure_page()

    #     if action == "is_visible":
    #         state = await page.locator(selector).is_visible()
    #         result_message = (
    #             f"{selector} is {'visible' if state else 'not visible'} in context."
    #         )
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
            # Get viewport dimensions
            window_height = await page.evaluate("window.innerHeight")
            window_width = await page.evaluate("window.innerWidth")

            # Get element's bounding box
            bounds = await page.locator(selector).bounding_box()
            if not bounds:
                return f"Unable to scroll in element '{selector}' as it does not exist"

            # Calculate the visible part of the element within the viewport
            visible_x = max(
                0,
                min(bounds["x"] + bounds["width"], window_width) - max(bounds["x"], 0),
            )
            visible_y = max(
                0,
                min(bounds["y"] + bounds["height"], window_height)
                - max(bounds["y"], 0),
            )

            # Adjust x and y to be within the visible part of the viewport
            x = max(bounds["x"], 0) + visible_x / 2
            y = max(bounds["y"], 0) + visible_y / 2

            # Calculate delta based on the visible part of the element
            delta = min(visible_y, window_height) * 0.8

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
        return f"Scrolled successfully."

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
        super().reset_history(history)

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
    # _unwrap_single_child(soup)
    _clean_attributes(soup)
    html_clean = soup.prettify()
    html_clean = re.sub(r"[\s]*<!--[\s\S]*?-->[\s]*?", "", html_clean)
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


def _clean_attributes(soup: BeautifulSoup) -> str:
    allowed_attrs = [
        "class",
        "id",
        "name",
        "value",
        "placeholder",
        "data-test-id",
        "data-playwright-scrollable",
        "data-playwright-value",
        "href",
    ]

    for element in soup.find_all(True):
        element.attrs = element.attrs = {
            key: value for key, value in element.attrs.items() if key in allowed_attrs
        }


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


def _remove_useless_tags(soup: BeautifulSoup):
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
