from bs4 import BeautifulSoup, Tag


async def ais_element_in_viewport(element, viewport_width, viewport_height):
    bounding_box = await element.bounding_box()
    if not bounding_box:
        return False
    x, y, width, height = (
        bounding_box["x"],
        bounding_box["y"],
        bounding_box["width"],
        bounding_box["height"],
    )
    return (
        x >= 0
        and y >= 0
        and x + width <= viewport_width
        and y + height <= viewport_height
    )


async def amark_invisible_elements(page):
    # Get viewport size
    viewport_size = page.viewport_size
    viewport_width = viewport_size["width"]
    viewport_height = viewport_size["height"]

    body = await page.query_selector("body")
    for element in await body.query_selector_all("*"):
        # TODO: mark visible elements too?
        if not await ais_element_in_viewport(element, viewport_width, viewport_height):
            await element.evaluate('el => el.setAttribute("data-visible", "false")')


def is_element_in_viewport(element, viewport_width, viewport_height):
    bounding_box = element.bounding_box()
    if not bounding_box:
        return False
    x, y, width, height = (
        bounding_box["x"],
        bounding_box["y"],
        bounding_box["width"],
        bounding_box["height"],
    )
    return (
        x >= 0
        and y >= 0
        and x + width <= viewport_width
        and y + height <= viewport_height
    )


def mark_invisible_elements(page):
    # Get viewport size
    viewport_size = page.viewport_size
    viewport_width = viewport_size["width"]
    viewport_height = viewport_size["height"]

    body = page.query_selector("body")
    for element in body.query_selector_all("*"):
        if is_element_in_viewport(element, viewport_width, viewport_height):
            element.evaluate('el => el.setAttribute("data-visible", "true")')
        else:
            element.evaluate('el => el.setAttribute("data-visible", "false")')


def clean_attributes(tag):
    # List of attributes to remove, add or remove attributes as needed
    blocked_attrs = ["class", "style"]
    tag.attrs = {k: v for k, v in tag.attrs.items() if k not in blocked_attrs}


def remove_specific_tags(tag):
    # List of tags to remove
    tags_to_remove = ["path", "meta", "link", "noscript", "script", "style", "title"]
    for t in tag.find_all(tags_to_remove):
        t.decompose()


def remove_elements_by_data_attribute(tag, attribute, value):
    for elem in tag.select(f'[{attribute}="{value}"]'):
        elem.decompose()


def strip_html_recursively(tag):
    clean_attributes(tag)
    for child in tag.find_all(
        True, recursive=False
    ):  # `recursive=False` to only go one level deep
        if isinstance(child, Tag):
            strip_html_recursively(child)


def strip_html_to_structure(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    remove_specific_tags(soup)  # Remove specific tags before processing
    remove_elements_by_data_attribute(soup, "data-visible", "false")
    strip_html_recursively(soup)
    return str(soup)
