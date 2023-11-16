from ai_powered_qa.components.utils import amark_invisible_elements, strip_html_to_structure
from ai_powered_qa.langchain_modules.tools.playwright.utils import aget_current_page


async def get_context_message(browser):
    page = await aget_current_page(browser)
    await amark_invisible_elements(page)

    html_content = await page.content()
    stripped_html = strip_html_to_structure(html_content)

    context_message = f"Here is the current state of the browser:\n" \
                    f"```\n" \
                    f"{stripped_html}\n" \
                    f"```\n"
    return context_message
