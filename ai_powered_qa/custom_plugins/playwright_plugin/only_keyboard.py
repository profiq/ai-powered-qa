from inspect import cleandoc
import logging

from bs4 import BeautifulSoup
import playwright.async_api
from playwright.async_api import Error

from ai_powered_qa.components.plugin import tool

from . import clean_html
from .base import PageNotLoadedException, PlaywrightPlugin
from ai_powered_qa.custom_plugins.playwright_plugin.base import LinkedPage
JS_FUNCTIONS = cleandoc(
    """
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

    function setValueAsDataAttribute() {
        const inputs = document.querySelectorAll('input, textarea, select');

        inputs.forEach(input => {
            const value = input.value;
            input.setAttribute('data-playwright-value', value);
        });
    }

    function setFocusAsDataAttribute() {
        // Clear the attribute from all elements
        const previouslyMarkedElements = document.querySelectorAll('[data-playwright-focused]');
        previouslyMarkedElements.forEach(el => el.removeAttribute('data-playwright-focused'));

        const focusedElement = document.activeElement;
        focusedElement.setAttribute('data-playwright-focused', 'true');
    }

    function updateDataAttributes() {
        updateElementVisibility();
        updateElementScrollability();
        setValueAsDataAttribute();
        setFocusAsDataAttribute();
    }
    window.updateDataAttributes = updateDataAttributes;
    """
)

CONTEXT_TEMPLATE = cleandoc(
    """
    Here is a description of the current page:
    ```text
    {description}
    ```
    """
)


class PlaywrightPluginOnlyKeyboard(PlaywrightPlugin):
    name: str = "PlaywrightPluginOnlyKeyboard"
    enabled_tools: list[str] = ["navigate_to_url", "press_key", "input_text"]

    @property
    def system_message(self) -> str:
        return cleandoc(
            """
            You can use Playwright to interact with web pages.
            """
        )

    def _format_context_message(self, html, description):
        return CONTEXT_TEMPLATE.format(description=description)

    @property
    def tools(self):
        """
        Filter the _tools list to include only those tools whose names are in the enabled_tools list.
        """
        return [
            tool
            for tool in self._tools
            if tool.get("function", {}).get("name") in self.enabled_tools
        ]

    @tool
    def press_key(self, key: str, count: int = 1) -> str:
        """
        {
            "type": "function",
            "function": {
                "name": "press_key",
                "description": "Press a specified key on the keyboard.",
                "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                    "type": "string",
                    "description": "The key to press (e.g., 'Enter', 'Tab', 'ArrowDown')."
                    },
                    "count": {
                    "type": "integer",
                    "description": "The number of times to press the key.",
                    "default": 1
                    }
                },
                "required": ["key"]
                }
            }
        }
        """
        return self._run_async(self._press_key(key, count))

    async def _press_key(self, key: str, count: int) -> str:
        page = await self._ensure_page()
        page.on("popup", self._handle_popup)
        try:
            for _ in range(count):
                await page.keyboard.press(key)
        except Exception as e:
            print(e)
            return f"Failed to press {key}. {e}"

        return f"Pressed {key} {count} time(s) successfully."

    @tool
    def input_text(self, text: str, delay: int = 0) -> str:
        """
        {
            "type": "function",
            "function": {
                "name": "input_text",
                "description": "Input text into the currently focused element.",
                "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to input."
                    }
                },
                "required": ["text"]
                }
            }
        }
        """
        return self._run_async(self._input_text(text))

    async def _input_text(self, text: str) -> str:
        page = await self._ensure_page()
        page.on("popup", self._handle_popup)
        try:
            await page.keyboard.type(text)
        except Exception as e:
            print(e)
            return f"Failed to input text. {e}"

        return f"Inputted text successfully."

    async def _get_page_content(self):
        page = await self._ensure_page()
        if page.url == "about:blank":
            raise PageNotLoadedException("No page loaded yet.")
        try:
            await page.evaluate("window.updateDataAttributes()")
        except Error as e:
            if (
                e.message
                == "Execution context was destroyed, most likely because of a navigation"
            ):
                logging.warning("Execution context was destroyed")
                await page.wait_for_url(page.url, wait_until="domcontentloaded")
                await page.evaluate("window.updateDataAttributes()")
            else:
                raise e
        html = await page.content()
        html_clean = self._clean_html(html)
        return html_clean

    async def _ensure_page(self) -> playwright.async_api.Page:
        if not self._pages:
            self._playwright = await playwright.async_api.async_playwright().start()
            self._browser = await self._playwright.firefox.launch(headless=False)
            self._browser_context = await self._browser.new_context(ignore_https_errors=True)
            await self._browser_context.add_init_script(JS_FUNCTIONS)
            page = await self._browser_context.new_page()
            self._pages = LinkedPage(page)
        if (self._pages._page.is_closed()):
            while(self._pages._page is not None and self._pages._page.is_closed()):
                await self._pages.set_prev()
            if(self._pages._page is None):
                page = await self._browser_context.new_page()
                self._pages._page = page
        return self._pages._page


    @staticmethod
    def _clean_html(html: str) -> str:
        """
        Cleans the web page HTML content from irrelevant tags and attributes
        to save tokens.
        """
        soup = BeautifulSoup(html, "html.parser")
        clean_html.remove_invisible(soup)
        clean_html.remove_useless_tags(soup)
        clean_html.clean_attributes(soup)
        html_clean = soup.prettify()
        html_clean = clean_html.remove_comments(html_clean)
        return html_clean

    def _enhance_selector(self, selector):
        return _selector_visible(selector)


def _selector_visible(selector: str) -> str:
    if "[data-playwright-visible=true]" not in selector:
        return f"{selector}[data-playwright-visible=true]"
    return selector
