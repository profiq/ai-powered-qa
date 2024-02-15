from inspect import cleandoc

from bs4 import BeautifulSoup
import playwright

from ai_powered_qa.components.plugin import tool

from . import clean_html
from .base import PageNotLoadedException, PlaywrightPlugin

JS_FUNCTIONS = cleandoc(
    """
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
            const overflowStyle = window.getComputedStyle(el).overflow 
                + window.getComputedStyle(el).overflowX 
                + window.getComputedStyle(el).overflowY;
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
        await page.evaluate("window.updateElementVisibility()")
        await page.evaluate("window.updateElementScrollability()")
        await page.evaluate("window.setValueAsDataAttribute()")
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
        if not direction in ["up", "down"]:
            return (
                f"Unable to scroll in element '{selector}' "
                f"as direction '{direction}' is not supported"
            )
        page = await self._ensure_page()
        try:
            window_height = await page.evaluate("window.innerHeight")
            bounds = await page.locator(selector).bounding_box()
            if not bounds:
                return f"Unable to scroll in element '{selector}' as it does not exist"
            x = bounds["x"] + bounds["width"] / 2
            y = bounds["y"] + bounds["height"] / 2
            delta = min(bounds["height"], window_height) * 0.8
            delta = delta if direction == "up" else -delta
            await page.mouse.move(x=x, y=y)
            await page.mouse.wheel(delta_y=delta, delta_x=0)
        except Exception as e:
            print(e)
            return f"Unable to scroll. {e}"
        return f"Scrolling in {direction} direction was successfully performed."

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
