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
)


class PlaywrightPluginOnlyVisible(PlaywrightPlugin):
    name: str = "PlaywrightPluginOnlyVisible"

    @property
    def system_message(self) -> str:
        return cleandoc(
            """
            You are an expert QA engineer. Your goal is to execute text scenarios given to you in natural language by controlling a browser.
            You can see your previous actions, and the user will give you the current state of the browser and the description of the test scenario. Your task is to suggest the next step to take towards completing the test scenario.
            When making assertions in the scenario, make them as robust as possible. Focus on things that should be stable across multiple runs of the test scenarion.
            You can use multiple assertions.
            For example in search results make sure the UI for search results is there, and check for specific keywords in the results that should be stable, but avoid asserting long texts are on the page, word for word.
            Before executing the test case, make sure to close any cookie consent, promotional or sign-up banners and popups that could be obscuring the elements you want to interact with.
            Always end the scenario with a call to the "finish" tool.
            """
        )

    async def _get_page_content(self):
        page = await self._ensure_page()
        if page.url == "about:blank":
            raise PageNotLoadedException("No page loaded yet.")
        try:
            await page.evaluate("window.updateElementVisibility()")
            await page.evaluate("window.updateElementScrollability()")
            await page.evaluate("window.setValueAsDataAttribute()")
        except Error as e:
            if (
                e.message
                == "Execution context was destroyed, most likely because of a navigation"
            ):
                logging.warning("Execution context was destroyed")
                await page.wait_for_url(page.url, wait_until="domcontentloaded")
                await page.evaluate("window.updateElementVisibility()")
                await page.evaluate("window.updateElementScrollability()")
                await page.evaluate("window.setValueAsDataAttribute()")
            else:
                raise e
        html = await page.content()
        html_clean = self._clean_html(html)
        return html_clean

    async def _ensure_page(self) -> playwright.async_api.Page:
        if self._pages is None:
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

    # @tool
    # def scroll(self, selector: str, direction: str):
    #     """
    #     Scroll up or down in a selected scroll container

    #     :param str selector: CSS selector for the scroll container
    #     :param str direction: Direction to scroll in. Either 'up' or 'down'
    #     """
    #     return self._run_async(self._scroll(selector, direction))

    # async def _scroll(self, selector: str, direction: str):
    #     page = await self._ensure_page()
    #     try:
    #         # Get viewport dimensions
    #         window_height = await page.evaluate("window.innerHeight")
    #         window_width = await page.evaluate("window.innerWidth")

    #         # Get element's bounding box
    #         bounds = await page.locator(selector).bounding_box()
    #         if not bounds:
    #             return f"Unable to scroll in element '{selector}' as it does not exist"

    #         # Calculate the visible part of the element within the viewport
    #         visible_x = max(
    #             0,
    #             min(bounds["x"] + bounds["width"], window_width) - max(bounds["x"], 0),
    #         )
    #         visible_y = max(
    #             0,
    #             min(bounds["y"] + bounds["height"], window_height)
    #             - max(bounds["y"], 0),
    #         )

    #         # Adjust x and y to be within the visible part of the viewport
    #         x = max(bounds["x"], 0) + visible_x / 2
    #         y = max(bounds["y"], 0) + visible_y / 2

    #         # Calculate delta based on the visible part of the element
    #         delta = min(visible_y, window_height) * 0.8

    #         await page.mouse.move(x=x, y=y)
    #         if direction == "up":
    #             await page.mouse.wheel(delta_y=-delta, delta_x=0)
    #         elif direction == "down":
    #             await page.mouse.wheel(delta_y=delta, delta_x=0)
    #         else:
    #             return f"Unable to scroll in element '{selector}' as direction '{direction}' is not supported"
    #     except Exception as e:
    #         print(e)
    #         return f"Unable to scroll. {e}"
    #     return f"Scrolled successfully."

    @tool
    def finish(self, success: bool, comment: str):
        """
        Finish the current session by closing the browser.

        :param bool success: Whether the scenario was finished successfully
        :param str comment: Additional comment about the scenario execution
        """
        return self._run_async(self._finish())

    async def _finish(self):
        if self._pages:
            await self._pages.close()
            if self._pages._page is not None:
                await self._pages._page.close()
        if self._browser_context:
            await self._browser_context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._pages = None
        return "Session finished."

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
