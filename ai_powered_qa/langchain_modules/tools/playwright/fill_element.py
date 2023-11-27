from __future__ import annotations

from typing import Type

from pydantic import BaseModel, Field

from langchain.tools.playwright.base import BaseBrowserTool
from langchain.tools.playwright.utils import aget_current_page


class FillToolInput(BaseModel):
    """Input for FillTool."""
    selector: str = Field(..., description="Selector for the element by text content.",)
    text: str = Field(..., description="Text what you want to fill up.")


class FillTextTool(BaseBrowserTool):
    """Tool for filling text to the element with the given CSS selector."""

    name: str = "fill_element"
    description: str = "Text input on element in the current web page matching the text content"
    args_schema: Type[BaseModel] = FillToolInput

    # Timeout (in ms) for Playwright to wait for element to be ready.
    playwright_timeout: float = 2_000

    @staticmethod
    def _run() -> str:
        """_run() isn't implemented, but is required to be defined."""
        return "_run() not implemented."

    async def _arun(self, selector: str, text: str) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")

        page = await aget_current_page(self.async_browser)

        try:
            await page.locator(selector).fill(text, timeout=self.playwright_timeout)
        except Exception:
            return f"Unable to fill up text on element '{selector}'."

        return f"Text input on the element by text, {selector} ,was successfully performed"
