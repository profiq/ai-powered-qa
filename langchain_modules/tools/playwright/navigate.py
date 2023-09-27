from __future__ import annotations

from typing import Optional, Type

from langchain.callbacks.manager import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain.tools.playwright.base import BaseBrowserTool
from langchain.tools.playwright.utils import aget_current_page, get_current_page
from pydantic import BaseModel, Field

from .utils import awrite_to_file, awrite_fail_to_file


class NavigateToolInput(BaseModel):
    """Input for NavigateToolInput."""

    url: str = Field(..., description="url to navigate to")


class NavigateTool(BaseBrowserTool):
    """Tool for navigating a browser to a URL."""

    name: str = "navigate_browser"
    description: str = "Navigate a browser to the specified URL"
    args_schema: Type[BaseModel] = NavigateToolInput

    def _run(
        self,
        url: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        page = get_current_page(self.sync_browser)
        response = page.goto(url)
        status = response.status if response else "unknown"

        # write playwright command to temp file
        playwright_cmd = f"    page.goto('{url}');\n"
        with open('tempfile', 'a') as f:
            f.write(playwright_cmd)

        return f"Navigating to {url} returned status code {status}"

    async def _arun(
        self,
        url: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")
        page = await aget_current_page(self.async_browser)
        playwright_cmd = f"await page.goto('{url}');\n"

        try:
            response = await page.goto(url)
            status = response.status if response else "unknown"
            await awrite_to_file(msg=f'    {playwright_cmd}')
        except Exception as e:
            await awrite_fail_to_file(msg=playwright_cmd, page=page)
            return f"Unable to navigate to {url}"
        return f"Navigating to {url} returned status code {status}"
