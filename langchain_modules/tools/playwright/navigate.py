from __future__ import annotations

from typing import Optional, Type

from langchain.callbacks.manager import AsyncCallbackManagerForToolRun
from langchain.tools.playwright.base import BaseBrowserTool
from langchain.tools.playwright.utils import aget_current_page
from pydantic import BaseModel, Field


class NavigateToolInput(BaseModel):
    """Input for NavigateToolInput."""
    url: str = Field(..., description="url to navigate to")


class NavigateTool(BaseBrowserTool):
    """Tool for navigating a browser to a URL."""
    name: str = "navigate_browser"
    description: str = "Navigate a browser to the specified URL"
    args_schema: Type[BaseModel] = NavigateToolInput

    @staticmethod
    def _run() -> str:
        """_run() isn't implemented, but is required to be defined."""
        return "_run() not implemented."

    async def _arun(self, url: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")
        page = await aget_current_page(self.async_browser)

        try:
            response = await page.goto(url)
            status = response.status if response else "unknown"
        except Exception:
            return f"Unable to navigate to {url}"

        return f"Navigating to {url} returned status code {status}"
