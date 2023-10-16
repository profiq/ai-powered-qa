from __future__ import annotations

from typing import Type

from langchain.tools.playwright.base import BaseBrowserTool
from langchain.tools.playwright.utils import aget_current_page
from playwright.async_api import expect as async_expect
from pydantic import BaseModel, Field


class ExpectTextToolInput(BaseModel):
    """Input for ExpectTextTool."""

    text: str = Field(..., description="Text what you expect to see.")
    index: int = Field(0, description="Index of the element to check.")


class ExpectTextTool(BaseBrowserTool):
    """Tool for checking expected text."""

    name: str = "expect_text"
    description: str = "Check if expected text is the same as the text of the current web page."
    args_schema: Type[BaseModel] = ExpectTextToolInput

    @staticmethod
    def _run() -> str:
        """_run() isn't implemented, but is required to be defined."""
        return "_run() not implemented."

    async def _arun(self, text: str, index: int = 0) -> str:
        """Use the tool."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")

        page = await aget_current_page(self.async_browser)

        try:
            element = page.get_by_text(text).nth(index)
            await async_expect(element).to_have_text(text)
        except Exception:
            return f"Unable to expect '{text}'"

        return f"Text: , {text}, is visible on the current page."
