from __future__ import annotations

from typing import Optional, Type

from pydantic import BaseModel, Field

from langchain.callbacks.manager import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain.tools.playwright.base import BaseBrowserTool
from langchain.tools.playwright.utils import aget_current_page, get_current_page
from .utils import awrite_to_file, awrite_fail_to_file

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


class IframeUploadToolInput(BaseModel):
    """Input for class IframeUploadToolInput"""

    iframe: str = Field(..., description="Selector for the iframe.")
    path: str = Field(..., description="Path for uploaded file.")


class IframeUploadTool(BaseBrowserTool):
    """Tool for uploading files inside iframe."""

    name: str = "iframe_upload"
    description: str = "Upload specified file inside iframe"
    args_schema: Type[BaseModel] = IframeUploadToolInput

    visible_only: bool = True
    """Whether to consider only visible elements."""
    playwright_strict: bool = False
    """Whether to employ Playwright's strict mode when clicking on elements."""
    playwright_timeout: float = 1_000
    """Timeout (in ms) for Playwright to wait for element to be ready."""

    def _run(
        self,
        iframe: str,
        path: str,
    ) -> str:
        """Use the tool."""
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        # Navigate to the desired webpage before using this tool
        page = get_current_page(self.sync_browser)

        try:
            page.frame_locator(iframe).last.locator("input[type=file]").set_input_files(path)
            # write playwright command to temp file
            playwright_cmd = f"    page.frameLocator(\"{iframe}\").last().locator(\"input[type=file]\").set_input_files(\"{path}\");\n"
            with open('tempfile', 'a') as f:
                f.write(playwright_cmd)
        except PlaywrightTimeoutError:
            with open('tempfile', 'a') as f:
                f.write(f"    // FAIL - page.frameLocator(\"{iframe}\").last().locator(\"input[type=file]\").setInputFiles(\"{path}\");\n")
            return f"Unable to upload files '{path}' in iframe"
        return f"Uploaded files '{path}'"

    async def _arun(
        self,
        iframe: str,
        path: str,
    ) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        # Navigate to the desired webpage before using this tool
        page = await aget_current_page(self.async_browser)
        playwright_cmd = f"await page.frameLocator(\"{iframe}\").last().locator(\"input[type=file]\").setInputFiles(\"{path}\");\n"

        try:
            await page.frame_locator(iframe).last.locator("input[type=file]").set_input_files(path)
            await awrite_to_file(msg=f'    {playwright_cmd}')
        except PlaywrightTimeoutError:
            await awrite_fail_to_file(msg=playwright_cmd, page=page)
            return f"Unable to upload files '{path}' in iframe"
        return f"Uploaded files '{path}'"
