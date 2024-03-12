from inspect import cleandoc

from ai_powered_qa.components.plugin import tool

from . import base


class PlaywrightPluginHtmlPaging(base.PlaywrightPlugin):
    name: str = "PlaywrightPluginHtmlPaging"
    html_part_length: int = 15000

    def __init__(self, **data):
        super().__init__(**data)
        self._part = 1

    @property
    def system_message(self):
        system_message_main = super().system_message
        return cleandoc(
            f"""
            {system_message_main}

            The HTML content is too long to display in one go. The content has
            been split into multiple parts. Use the `move_to_html_part` tool to
            move between parts of the HTML content.
            """
        )

    @property
    def context_message(self):
        try:
            html = self._run_async(self._get_page_content())
            html, max_parts = self._get_html_part(html)
        except base.PageNotLoadedException:
            html = "No page loaded yet."
            max_parts = 1
            description = "The browser is empty"
        else:
            description = self._get_html_description(html)
        self._run_async(self._screenshot())
        context_message_main = base.CONTEXT_TEMPLATE.format(
            html=html, description=description
        )
        return cleandoc(
            f"""
            {context_message_main}

            HTML part {self._part} of {max_parts}
            """
        )

    @tool
    def move_to_html_part(self, part: int):
        """
        Moves to the HTML part at the given index. We split the HTML content of the website
        into multiple smaller parts to avoid reaching the token limit

        :param int part: Index of the HTML part to move to (starts at 1)
        """
        self._part = part
        return f"Moved to HTML part {self._part}"

    def _get_html_part(self, html: str) -> str:
        """
        Splits the HTML content into parts of about self.part_length characters.
        Always performs a split at a tag start character.
        After HTML is split it returns the part at intex self._part
        We split the HTML content into parts to avoid reaching the token limit
        """
        if len(html) < self.html_part_length:
            return html, 1
        parts = []
        current_part = ""
        for char in html:
            if char == "<" and len(current_part) > self.html_part_length:
                parts.append(current_part)
                current_part = "<"
            else:
                current_part += char
        parts.append(current_part)
        return parts[self._part - 1], len(parts)
