from playwright.async_api import TimeoutError, Page
from pydantic import Field


class FunctionBase:
    name: str
    description: str
    parameters: dict

    def __init__(self, page):
        self.page: Page = page

    async def arun(self) -> str:
        pass


class NavigateFunction(FunctionBase):
    name: str = "navigate_browser"
    description: str = "Navigate a browser to the specified URL"
    parameters: dict = {
                            "type": "object",
                            "properties": {"url": {"type": "string"}},
                            "required": ["url"],
                       }

    def __init__(self, page: Page, url: str):
        super().__init__(page)
        self.url = url

    async def arun(self) -> str:
        try:
            response = await self.page.goto(self.url)
        except Exception:
            return f"Unable to navigate to {self.url}"

        return f"Navigating to {self.url} returned status code {response.status if response else 'unknown'}"


class ClickFunction(FunctionBase):
    name: str = "click_element"
    description: str = "Click on an element with the given CSS selector"
    parameters: dict = {
                            "type": "object",
                            "properties": {
                                "selector": {"type": "string"},
                                "index": {"type": "number"},
                                "timeout": {"type": "number"},
                            },
                            "required": ["selector"],
                       }

    visible_only: bool = True  # Whether to consider only visible elements.
    playwright_strict: bool = False  # Whether to employ Playwright's strict mode when clicking on elements.

    def __init__(self,
                 page: Page,
                 selector: str = Field(..., description="CSS selector for the element to click"),
                 index: int = Field(0, description="Index of the element to click"),
                 timeout: float = 3000):
        super().__init__(page)
        self.selector = selector
        self.index = index
        self.timeout = timeout

    def _selector_effective(self, selector: str, index: int) -> str:
        if not self.visible_only:
            return selector
        return f"{selector} >> visible=1 >> nth={index}"

    async def arun(self) -> str:
        try:
            await self.page.click(selector=self._selector_effective(self.selector, self.index),
                                  strict=self.playwright_strict,
                                  timeout=self.timeout)
        except TimeoutError:
            return f"Unable to click on element '{self.selector}'"

        return f"Clicked element '{self.selector}'"


class FillFunction(FunctionBase):
    name: str = "fill_element"
    description: str = "Text input on element in the current web page matching the text content"
    parameters: dict = {
                            "type": "object",
                            "properties": {
                                "selector": {"type": "string"},
                                "text": {"type": "string"},
                                "timeout": {"type": "number"},
                            },
                            "required": ["selector", "text"],
                       }

    def __init__(self,
                 page: Page,
                 selector: str = Field(..., description="Selector for the element by text content.", ),
                 text: str = Field(..., description="Text what you want to fill up."),
                 timeout: float = 3000):
        super().__init__(page)
        self.selector = selector.replace("\"", "'")
        self.text = text
        self.timeout = timeout

    async def arun(self) -> str:
        try:
            await self.page.locator(self.selector).fill(self.text, timeout=self.timeout)
        except Exception:
            return f"Unable to fill up text on element '{self.selector}'."

        return f"Text input on the element by text, {self.selector}, was successfully performed."
