from __future__ import annotations

from typing import Type

from pydantic import BaseModel, Field

from langchain.tools.playwright.base import BaseBrowserTool
from langchain.tools.playwright.utils import aget_current_page, get_current_page
from .utils import awrite_to_file, awrite_fail_to_file

from playwright.sync_api import expect as syncExpect
from playwright.async_api import expect as asyncExpect


class ExpectTitleToolInput(BaseModel):
    """Input for ExpectTitleTool."""

    title: str = Field(
        ...,
        description="Title what you expect to see.",
    )


class ExpectTitleTool(BaseBrowserTool):
    """Tool for checking expected title."""

    name: str = "expect_title"
    description: str = "Check if expected title is the same as the title of the current web page."
    args_schema: Type[BaseModel] = ExpectTitleToolInput

    def _run(
        self,
        title: str,
    ) -> str:
        """Use the tool."""
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        page = get_current_page(self.sync_browser)
        # check if the title is the same as expected
        try:
            syncExpect(page).to_have_title(title)
            playwrite_command = f"    expect(page).toHaveTitle(/{title}/);\n"
            with open('tempfile', 'a') as f:
                f.write(playwrite_command)
        except Exception as e:
            return f"Cannot to find '{title}' with exception: {e}"

        return "Title: ", title ,"is visible on the current page."

    async def _arun(
        self,
        title: str,
    ) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")
        page = await aget_current_page(self.async_browser)
        playwright_cmd = f"await expect(page).toHaveTitle(/{title}/);\n"
        # check if the title is the same as expected
        try:
            await asyncExpect(page).to_have_title(title)
            await awrite_to_file(msg=f'    {playwright_cmd}')
        except Exception as e:
            await awrite_fail_to_file(msg=playwright_cmd, page=page)
            return f"Cannot to find '{title}' with exception: {e}"
        return f"Title: , {title} ,is visible on the current page."
