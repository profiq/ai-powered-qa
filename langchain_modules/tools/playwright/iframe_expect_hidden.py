from __future__ import annotations

from typing import Type

from pydantic import BaseModel, Field

from langchain.tools.playwright.base import BaseBrowserTool
from langchain.tools.playwright.utils import aget_current_page, get_current_page
from .utils import awrite_to_file, awrite_fail_to_file

from playwright.sync_api import expect as syncExpect
from playwright.async_api import expect as asyncExpect


class IframeExpectHiddenToolInput(BaseModel):
    """Input for IframeExpectHiddenTool."""

    iframe: str = Field(..., description="Selector for the iframe.")
    selector: str = Field(..., description="Selector for desired element.")


class IframeExpectHiddenTool(BaseBrowserTool):
    """Tool for checking hidden element in iframe"""

    name: str = "iframe_expect_hidden"
    description: str = "Check if element in iframe is hidden."
    args_schema: Type[BaseModel] = IframeExpectHiddenToolInput

    def _run(
        self,
        iframe: str,
        selector: str,
    ) -> str:
        """Use the tool."""
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        page = get_current_page(self.sync_browser)
        # check if the text is the same as expected
        try:
            syncExpect(page.frame_locator(iframe).last.locator(selector)).to_be_hidden()
            playwrite_command = f"    expect(page.frameLocator(\"{iframe}\").last.locator(\"{selector}\")).toBeHidden();\n"
            with open('tempfile', 'a') as f:
                f.write(playwrite_command)
        except Exception as e:
            with open('tempfile', 'a') as f:
                f.write(f"    // FAIL - expect(page.frameLocator(\"{iframe}\").last.locator(\"{selector}\")).toBeHidden();\n")
            return f"Cannot to find iframe '{iframe}' with selector '{selector}' with exception: {e}"

        return f"Element: , {selector},  in iframe: , {iframe}, is hidden on the current page."

    async def _arun(
        self,
        iframe: str,
        selector: str,
    ) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")
        page = await aget_current_page(self.async_browser)
        playwright_cmd = f"await expect(page.frameLocator(\"{iframe}\").last().locator(\"{selector}\")).toBeHidden();\n"
        # check if the text is the same as expected
        try:
            await asyncExpect(page.frame_locator(iframe).last.locator(selector)).to_be_hidden()
            await awrite_to_file(msg=f'    {playwright_cmd}')
        except Exception as e:
            await awrite_fail_to_file(msg=playwright_cmd, page=page)
            return f"Cannot to find iframe '{iframe}' with selector '{selector}' with exception: {e}"
        return f"Element: , {selector},  in iframe: , {iframe}, is hidden on the current page."
