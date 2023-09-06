import json

params_to_pass = {
    "go_to_page": ["url"],
    "take_screenshot": ["path", "full_page"]
}


def go_to_page(**kwargs):
    """Go to a page in the browser"""
    url_info = {"url": kwargs.get("url")}
    playwright_cmd = f"    await page.goto('{kwargs.get('url')}');\n"
    with open('tempfile', 'a') as f:
        f.write(playwright_cmd)
    return json.dumps(url_info)


def take_screenshot(**kwargs):
    """Take screenshot of the page"""
    screenshot_info = {key: kwargs.get(key)
                       for key in params_to_pass['take_screenshot']}
    playwright_cmd = f"    await page.screenshot({{ path: '{screenshot_info['path']}', fullPage: \
{str(screenshot_info['full_page']).lower() if not None else 'true' }}});\n"

    with open('tempfile', 'a') as f:
        f.write(playwright_cmd)
    return json.dumps(screenshot_info)
