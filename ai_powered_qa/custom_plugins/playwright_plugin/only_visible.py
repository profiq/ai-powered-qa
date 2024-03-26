from inspect import cleandoc
import logging

from bs4 import BeautifulSoup
import playwright.async_api
from playwright.async_api import Error

from ai_powered_qa.components.plugin import tool

from . import clean_html
from .base import PageNotLoadedException, PlaywrightPlugin

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
        if not self._page:
            self._playwright = await playwright.async_api.async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=False)
            browser_context = await self._browser.new_context()
            await browser_context.add_init_script(JS_FUNCTIONS)
            self._page = await browser_context.new_page()
        return self._page

    @tool
    def scroll(self, selector: str, direction: str):
        """
        Scroll up or down in a selected scroll container

        :param str selector: CSS selector for the scroll container
        :param str direction: Direction to scroll in. Either 'up' or 'down'
        """
        return self._run_async(self._scroll(selector, direction))

    async def _scroll(self, selector: str, direction: str):
        page = await self._ensure_page()
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
