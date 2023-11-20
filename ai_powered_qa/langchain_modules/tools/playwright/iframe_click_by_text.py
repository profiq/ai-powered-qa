from __future__ import annotations

from typing import Optional, Type

from pydantic import BaseModel, Field

from langchain.callbacks.manager import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain.tools.playwright.base import BaseBrowserTool
from langchain.tools.playwright.utils import aget_current_page, get_current_page
from .utils import awrite_to_file, awrite_fail_to_file

from playwright.async_api import TimeoutError as PlaywrightTimeoutError


class IframeClickByTextToolInput(BaseModel):
    """Input for IframeClickByTextTool."""

    iframe: str = Field(..., description="Selector for the iframe.")
    text: str = Field(..., description="Text what should be displayed in element.")


class IframeClickByTextTool(BaseBrowserTool):
    """Tool for clicking on an element with given text inside iframe."""

    name: str = "iframe_click_by_text"
    description: str = "Click in iframe on element with the given text"
    args_schema: Type[BaseModel] = IframeClickByTextToolInput

    visible_only: bool = True
    """Whether to consider only visible elements."""
    playwright_strict: bool = False
    """Whether to employ Playwright's strict mode when clicking on elements."""
    playwright_timeout: float = 1_000
    """Timeout (in ms) for Playwright to wait for element to be ready."""

    def _run(
        self,
        iframe: str,
        text: str,
    ) -> str:
        """Use the tool."""
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        # Navigate to the desired webpage before using this tool
        page = get_current_page(self.sync_browser)

        try:
            page.frame_locator(iframe).last.get_by_text(text).click()
            # write playwright command to temp file
            playwright_cmd = f"    page.frameLocator(\"{iframe}\").last().getByText(\"{text}\").click();\n"
            with open('tempfile', 'a') as f:
                f.write(playwright_cmd)
        except PlaywrightTimeoutError:
            with open('tempfile', 'a') as f:
                f.write(f"    // FAIL - page.frameLocator(\"{iframe}\").last().getByText(\"{text}\").click();)\n")
            return f"Unable to click on element '{text}'"
        return f"Clicked element '{text}'"

    async def _arun(
        self,
        iframe: str,
        text: str,
    ) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")
        # Navigate to the desired webpage before using this tool
        page = await aget_current_page(self.async_browser)
        playwright_cmd = f"    await page.frameLocator(\"{iframe}\").last().getByText(\"{text}\").click();\n"

        try:
            await page.frame_locator(iframe).last.get_by_text(text).click()
            await awrite_to_file(msg=f'    {playwright_cmd}')
        except PlaywrightTimeoutError:
            await awrite_fail_to_file(msg=playwright_cmd, page=page)
            return f"Unable to click on element '{text}'"
        return f"Clicked element '{text}'"
