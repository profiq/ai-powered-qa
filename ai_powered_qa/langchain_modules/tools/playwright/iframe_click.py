from __future__ import annotations

from typing import Optional, Type

from pydantic import BaseModel, Field

from langchain.callbacks.manager import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain.tools.playwright.base import BaseBrowserTool
from langchain.tools.playwright.utils import aget_current_page, get_current_page
from .utils import awrite_to_file, awrite_fail_to_file

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


class IframeClickToolInput(BaseModel):
    """Input for IframeClickByTextTool."""

    iframe: str = Field(..., description="Selector for the iframe.")
    selector: str = Field(..., description="Selector for desired element.")


class IframeClickTool(BaseBrowserTool):
    """Tool for clicking on an element with given selector inside iframe."""

    name: str = "iframe_click"
    description: str = "Click in specified iframe on element with the given selector"
    args_schema: Type[BaseModel] = IframeClickToolInput

    visible_only: bool = True
    """Whether to consider only visible elements."""
    playwright_strict: bool = False
    """Whether to employ Playwright's strict mode when clicking on elements."""
    playwright_timeout: float = 1_000
    """Timeout (in ms) for Playwright to wait for element to be ready."""

    def _run(
        self,
        iframe: str,
        selector: str,
    ) -> str:
        """Use the tool."""
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        # Navigate to the desired webpage before using this tool
        page = get_current_page(self.sync_browser)

        try:
            page.frame_locator(iframe).last.locator(selector).click()
            # write playwright command to temp file
            playwright_cmd = f"    page.frameLocator(\"{iframe}\").last().locator(\"{selector}\").click();\n"
            with open('tempfile', 'a') as f:
                f.write(playwright_cmd)
        except PlaywrightTimeoutError:
            with open('tempfile', 'a') as f:
                f.write(f"    // FAIL - page.frameLocator(\"{iframe}\").last().locator(\"{selector}\").click();)\n")
            return f"Unable to click on element '{selector}'"
        return f"Clicked element '{selector}'"

    async def _arun(
        self,
        iframe: str,
        selector: str,
    ) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")
        # Navigate to the desired webpage before using this tool
        page = await aget_current_page(self.async_browser)
        playwright_cmd = f"await page.frameLocator(\"{iframe}\").last().locator(\"{selector}\").click();\n"

        try:
            await page.frame_locator(iframe).last.locator(selector).click()
            await awrite_to_file(msg=f'    {playwright_cmd}')
        except PlaywrightTimeoutError:
            await awrite_fail_to_file(msg=playwright_cmd, page=page)
            return f"Unable to click on element '{selector}'"
        return f"Clicked element '{selector}'"
