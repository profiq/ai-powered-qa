from bs4 import BeautifulSoup
import re


def clean_attributes(soup: BeautifulSoup, classes: bool = True) -> str:
    allowed_attrs = [
        "id",
        "name",
        "value",
        "placeholder",
        "data-test-id",
        "data-testid",
        "data-playwright-scrollable",
        "data-playwright-value",
        "href"
    ]

    if not classes:
        allowed_attrs.append("class")

    for element in soup.find_all(True):
        element.attrs = element.attrs = {
            key: value for key, value in element.attrs.items() if key in allowed_attrs
        }


def remove_useless_tags(soup: BeautifulSoup):
    tags_to_remove = [
        "path",
        "meta",
        "link",
        "noscript",
        "script",
        "style",
    ]
    for t in soup.find_all(tags_to_remove):
        t.decompose()


def remove_invisible(soup: BeautifulSoup):
    to_keep = set()
    visible_elements = soup.find_all(attrs={"data-playwright-visible": True})
    for element in visible_elements:
        current = element
        while current is not None:
            if current in to_keep:
                break
            to_keep.add(current)
            current = current.parent

    for element in soup.find_all(True):
        if element.name and element not in to_keep:
            element.decompose()


def remove_comments(html: str):
    return re.sub(r"[\s]*<!--[\s\S]*?-->[\s]*?", "", html)
