from playwright.async_api import async_playwright
import asyncio


class PlaywrightWrapper:
    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._browser = None

    async def get_browser(self):
        if self._browser is None:
            playwright = await async_playwright().start()
            self._browser = await playwright.chromium.launch()
        return self._browser

    async def _take_screenshot(self, url):
        browser = await self.get_browser()
        page = await browser.new_page()
        await page.goto(url)
        screenshot = await page.screenshot()
        await page.close()
        return screenshot

    def take_screenshot(self, url):
        asyncio.set_event_loop(self._loop)
        return self._loop.run_until_complete(self._take_screenshot(url))
