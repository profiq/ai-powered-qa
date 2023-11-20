from __future__ import annotations

from typing import Optional, Type

from pydantic import BaseModel, Field

from langchain.callbacks.manager import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain.tools.playwright.base import BaseBrowserTool
from langchain.tools.playwright.utils import aget_current_page, get_current_page
from .utils import awrite_to_file, awrite_fail_to_file

from playwright.async_api import TimeoutError as PlaywrightTimeoutError


class PressToolInput(BaseModel):
    """Input for PressInput."""
    key: str = Field(..., description="Key to press")


class PressTool(BaseBrowserTool):
    """Tool for clicking on an element with the given CSS selector."""

    name: str = "press_key"
    description: str = "Press a key on the keyboard"
    args_schema: Type[BaseModel] = PressToolInput

    visible_only: bool = True
    """Whether to consider only visible elements."""
    playwright_strict: bool = False
    """Whether to employ Playwright's strict mode when clicking on elements."""

    @staticmethod
    def _run() -> str:
        """_run() isn't implemented, but is required to be defined."""
        return "_run() not implemented."

    async def _arun(self, key: str) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")
        page = await aget_current_page(self.async_browser)
        # Navigate to the desired webpage before using this tool
        playwright_cmd = f"await page.keyboard.press(\"{key}\");\n"

        try:
            await page.keyboard.press(key=key)
            await awrite_to_file(msg=f'    {playwright_cmd}')
        except PlaywrightTimeoutError:
            await awrite_fail_to_file(msg=playwright_cmd, page=page)
            return f"Unable to press '{key}'"
        return f"Pressed key '{key}'"
