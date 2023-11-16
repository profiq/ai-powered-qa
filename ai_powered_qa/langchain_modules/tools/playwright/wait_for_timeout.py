from __future__ import annotations

from typing import Type

from langchain.tools.playwright.base import BaseBrowserTool
from langchain.tools.playwright.utils import aget_current_page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from pydantic import BaseModel, Field

from .utils import awrite_to_file, awrite_fail_to_file


class WaitToolInput(BaseModel):
    """Input for PressInput."""
    timeout: float = Field(..., description="Timeout (in ms) for Playwright to wait for element to be ready.")


class WaitTool(BaseBrowserTool):
    """Tool for clicking on an element with the given CSS selector."""

    name: str = "wait"
    description: str = "Wait for seconds"
    args_schema: Type[BaseModel] = WaitToolInput

    visible_only: bool = True
    """Whether to consider only visible elements."""
    playwright_strict: bool = False
    """Whether to employ Playwright's strict mode when clicking on elements."""

    @staticmethod
    def _run() -> str:
        """_run() isn't implemented, but is required to be defined."""
        return "_run() not implemented."

    async def _arun(self, timeout: float) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")
        page = await aget_current_page(self.async_browser)
        # Navigate to the desired webpage before using this tool
        playwright_cmd = f"await page.waitForTimeout({timeout});\n"

        try:
            await page.wait_for_timeout(timeout=timeout)
            await awrite_to_file(msg=f'    {playwright_cmd}')
        except PlaywrightTimeoutError:
            await awrite_fail_to_file(msg=playwright_cmd, page=page)
            return f"Unable to wait for '{timeout} ms'"
        return f"Waited for '{timeout} ms'"
