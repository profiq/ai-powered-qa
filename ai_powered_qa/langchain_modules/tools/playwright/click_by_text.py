from __future__ import annotations

from typing import Type

from langchain.tools.playwright.base import BaseBrowserTool
from langchain.tools.playwright.utils import aget_current_page
from pydantic import BaseModel, Field


class ClickByTextToolInput(BaseModel):
    """Input for ClickByTextTool."""
    selector: str = Field(..., description="Selector for the element by text content.")
    text: str = Field(..., description="Text content of the element to click on.")
    index: int = Field(0, description="Index of the element to click on.")
    timeout: float = Field(5_000, description="Timeout (in ms) for Playwright to wait for element to be ready.")


class ClickByTextTool(BaseBrowserTool):
    """Tool for clicking on an element with the given text and selector."""

    name: str = "click_by_text"
    description: str = "Click on element in the current web page matching the text content"
    args_schema: Type[BaseModel] = ClickByTextToolInput

    @staticmethod
    def _run() -> str:
        """_run() isn't implemented, but is required to be defined."""
        return "_run() not implemented."

    async def _arun(self, selector: str, text: str, index: int = 0, timeout: float = 5_000) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")

        page = await aget_current_page(self.async_browser)

        try:
            await page.click(selector_effective, strict=self.playwright_strict, timeout=timeout)

            element = page.get_by_role(role=selector).get_by_text(text)

            selector_effective = self._selector_effective(selector=selector, index=index)
            await page.click(selector_effective, strict=self.playwright_strict, timeout=timeout)

            if await element.nth(index).is_visible():  # check if element is visible via selector and text
                await element.nth(index).click(timeout=timeout)
            else:  # if not visible, try to click on element only by text
                await page.get_by_text(text).click(timeout=timeout)
        except Exception:
            return f"Unable to click on element with selector: '{selector}', index: '{index}' text:'{text}'"

        return f"Click on the element with selector: '{selector}', index: '{index}' text: '{text}', was successfully performed"
