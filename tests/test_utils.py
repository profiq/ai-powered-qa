from ai_powered_qa.components.utils import remove_invisible_elements
from bs4 import BeautifulSoup


def test_remove_invisible_elements():
    html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test</title>
        </head>
        <body>
            <div class="root" data-visible="false">
                <div class="child" data-visible="false">A</div>
                <div class="child" data-visible="true">B</div>
                <div class="child">C</div>
            </div>
        </body>
    """
    soup = BeautifulSoup(html, "html.parser")
    remove_invisible_elements(soup)
    text = soup.prettify()
    assert "Test" in text
    assert "A" not in text
    assert "B" in text
    assert "C" in text
