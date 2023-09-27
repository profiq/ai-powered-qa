from __future__ import annotations

from typing import Type

from pydantic import BaseModel, Field

from langchain.tools.playwright.base import BaseBrowserTool
from langchain.tools.playwright.utils import aget_current_page, get_current_page
from .utils import awrite_to_file, awrite_fail_to_file

from playwright.sync_api import expect as sync_expect
from playwright.async_api import expect as async_expect


class ExpectTextToolInput(BaseModel):
    """Input for ExpectTextTool."""

    text: str = Field(..., description="Text what you expect to see.")
    index: int = Field(0, description="Index of the element to check.")


class ExpectTextTool(BaseBrowserTool):
    """Tool for checking expected text."""

    name: str = "expect_text"
    description: str = "Check if expected text is the same as the text of the current web page."
    args_schema: Type[BaseModel] = ExpectTextToolInput

    def _run(
        self,
        text: str,
        index: int = 0,
    ) -> str:
        """Use the tool."""
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        page = get_current_page(self.sync_browser)
        # check if the text is the same as expected
        try:
            element = page.get_by_text(text).nth(index)
            sync_expect(element).to_have_text(text)
            playwright_cmd = f"    expect(page.getByText(/{text}/).nth({index})).toHaveText(/{text}/);\n"
            with open('tempfile', 'a') as f:
                f.write(playwright_cmd)
        except Exception as e:
            with open('tempfile', 'a') as f:
                f.write(f"    // FAIL - expect(page.getByText(/{text}/).nth({index})).toHaveText(/{text}/);\n")
            return f"Cannot to find '{text}' with exception: {e}"

        return "Text: ", text, "is visible on the current page."

    async def _arun(
        self,
        text: str,
        index: int = 0,
    ) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")
        page = await aget_current_page(self.async_browser)
        playwright_cmd = f"await expect(page.getByText(/{text}/).nth({index})).toHaveText(/{text}/);\n"
        # check if the text is the same as expected
        try:
            element = page.get_by_text(text).nth(index)
            await async_expect(element).to_have_text(text)
            await awrite_to_file(msg=f'    {playwright_cmd}')
        except Exception as e:
            await awrite_fail_to_file(msg=playwright_cmd, page=page)
            return f"Cannot to find '{text}' with exception: {e}"
        return f"Text: , {text}, is visible on the current page."
