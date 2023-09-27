from __future__ import annotations

from typing import Type

from langchain.tools.playwright.base import BaseBrowserTool
from langchain.tools.playwright.utils import aget_current_page, get_current_page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from pydantic import BaseModel, Field

from .utils import awrite_to_file, awrite_fail_to_file


class ClickToolInput(BaseModel):
    """Input for ClickTool."""

    selector: str = Field(..., description="CSS selector for the element to click")
    index: int = Field(0, description="Index of the element to click")
    timeout: float = Field(3_000, description="Timeout (in ms) for Playwright to wait for element to be ready.")


class ClickTool(BaseBrowserTool):
    """Tool for clicking on an element with the given CSS selector."""

    name: str = "click_element"
    description: str = "Click on an element with the given CSS selector"
    args_schema: Type[BaseModel] = ClickToolInput

    visible_only: bool = True
    """Whether to consider only visible elements."""
    playwright_strict: bool = False
    """Whether to employ Playwright's strict mode when clicking on elements."""

    def _selector_effective(self, selector: str, index: int) -> str:
        if not self.visible_only:
            return selector
        return f"{selector} >> visible=1 >> nth={index}"

    def _run(
        self,
        selector: str,
        index: int = 0,
    ) -> str:
        """Use the tool."""
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        page = get_current_page(self.sync_browser)
        # Navigate to the desired webpage before using this tool
        selector_effective = self._selector_effective(selector=selector, index=index)

        try:
            page.click(
                selector_effective,
                strict=self.playwright_strict,
                timeout=self.timeout,
            )
            # write playwright command to temp file
            playwright_cmd = f"    page.click(\"{selector} >> visible = true\", {{ strict:{self.playwright_strict}, timeout:{self.timeout}}});\n"
            with open('tempfile', 'a') as f:
                f.write(playwright_cmd)
        except PlaywrightTimeoutError:
            with open('tempfile', 'a') as f:
                f.write(f"    // FAIL page.click(\"{selector} >> visible = true\", {{ strict:{str(self.playwright_strict).lower()}, timeout:{self.timeout}}});\n")
            return f"Unable to click on element '{selector}'"
        return f"Clicked element '{selector}'"

    async def _arun(
        self,
        selector: str,
        index: int = 0,
        timeout: float = 3_000
    ) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")
        page = await aget_current_page(self.async_browser)
        # Navigate to the desired webpage before using this tool
        selector_effective = self._selector_effective(selector=selector, index=index)
        playwright_cmd = f"await page.click(\"{selector_effective}\", {{strict:{str(self.playwright_strict).lower()}, timeout:{timeout}}});\n"

        try:
            await page.click(
                selector_effective,
                strict=self.playwright_strict,
                timeout=timeout,
            )
            await awrite_to_file(msg=f'    {playwright_cmd}')
        except PlaywrightTimeoutError:
            await awrite_fail_to_file(msg=playwright_cmd, page=page)
            return f"Unable to click on element '{selector}'"
        return f"Clicked element '{selector}'"
