from __future__ import annotations

from typing import Optional, Type

from pydantic import BaseModel, Field

from langchain.callbacks.manager import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain.tools.playwright.base import BaseBrowserTool
from langchain.tools.playwright.utils import aget_current_page, get_current_page
from .utils import awrite_to_file, awrite_fail_to_file



class TakeScreenshotToolInput(BaseModel):
    """Input for TakeScreenshotTool."""

    path: str = Field(..., description="Path to save the screenshot to.")
    full: bool = Field(True, description="Whether to take a full page screenshot.")


class TakeScreenshotTool(BaseBrowserTool):
    name: str = "take_screenshot"
    description: str = "Take a screenshot of the current page"
    args_schema: Type[BaseModel] = TakeScreenshotToolInput

    def _run(
        self,
        path: str,
        full: bool = True,
    ) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        page = aget_current_page(self.async_browser)
        try:
            page.screenshot(path=path,full_page=full)
            # write playwright command to temp file
            playwright_cmd = f"    page.screenshot({{path:'{path}', fullPage:{str(full).lower()}}});\n"
            with open('tempfile', 'a') as f:
                f.write(playwright_cmd)
        except Exception as e:
            with open('tempfile', 'a') as f:
                f.write(f"    // FAIL - page.screenshot({{path:'{path}', fullPage:{str(full).lower()}}});\n")
            return f"Unable to take screenshot with exception: {e}"
        return "Screenshot taken"

    async def _arun(
        self,
        path: str,
        full: bool = True,
    ) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")
        page = await aget_current_page(self.async_browser)
        playwright_cmd = f"await page.screenshot({{path:'{path}', fullPage:{str(full).lower()}}});\n"

        try:
            await page.screenshot(path=path, full_page=full)
            await awrite_to_file(msg=f'    {playwright_cmd}')
        except Exception:
            await awrite_fail_to_file(msg=playwright_cmd, page=page)
            return f"Unable to take screenshot."
        return "Screenshot taken"
