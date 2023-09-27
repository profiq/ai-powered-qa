from __future__ import annotations

from typing import Type

from pydantic import BaseModel, Field

from langchain.tools.playwright.base import BaseBrowserTool
from langchain.tools.playwright.utils import aget_current_page, get_current_page
from .utils import awrite_to_file, awrite_fail_to_file


class FillToolInput(BaseModel):
    """Input for FillTool."""

    selector: str = Field(..., description="Selector for the element by text content.",)
    text: str = Field(..., description="Text what you want to fill up.")


class FillTextTool(BaseBrowserTool):
    """Tool for filling text to the element with the given CSS selector."""

    name: str = "fill_element"
    description: str = "Text input on element in the current web page matching the text content"
    args_schema: Type[BaseModel] = FillToolInput

    # Timeout (in ms) for Playwright to wait for element to be ready.
    playwright_timeout: float = 2_000

    def _run(
        self,
        selector: str,
        text: str,
    ) -> str:
        """Use the tool."""
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        page = get_current_page(self.sync_browser)
        # try to enter the text on the element by text
        try:
            page.locator(selector).fill(text, timeout=self.playwright_timeout)
             # write playwright command to temp file
            playwright_cmd = f"    page.locator(\"{selector}\").fill('{text}');\n"
            with open('tempfile', 'a') as f:
                f.write(playwright_cmd)
        except Exception as e:
            return f"Unable to fill up text on element '{selector}' with exception: {e}"

        return "Text input on the element by text", selector ,"was successfully performed"

    async def _arun(
        self,
        selector: str,
        text: str,
    ) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")
        page = await aget_current_page(self.async_browser)
        playwright_cmd = f"await page.locator(\"{selector}\").fill('{text}');\n"
        # try to enter the text on the element by text
        try:
            await page.locator(selector).fill(text, timeout=self.playwright_timeout)
            await awrite_to_file(msg=f'    {playwright_cmd}')
        except Exception as e:
            await awrite_fail_to_file(msg=playwright_cmd, page=page)
            return f"Unable to fill up text on element '{selector}' with exception: {e}"
        return f"Text input on the element by text, {selector} ,was successfully performed"
