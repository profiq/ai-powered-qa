import json

params_to_pass = {
    "go_to_page": ["url"],
    "take_screenshot": ["path", "full_page"],
    "expect_text": ["text"],
}


def go_to_page(**kwargs):
    """Go to a page in the browser"""
    url_info = {key: kwargs.get(key)
                for key in params_to_pass['go_to_page']}
    # here we will run the playwright code a set the status code. Then inform gpt about it.
    url_info['status'] = 200
    cmd = f"    await page.goto('{kwargs.get('url')}');\n"
    url_info['cmd'] = cmd
    with open('tempfile', 'a') as f:
        f.write(cmd)
    return json.dumps(url_info)


def take_screenshot(**kwargs):
    """Take screenshot of the page"""
    screenshot_info = {key: kwargs.get(key)
                       for key in params_to_pass['take_screenshot']}
    screenshot_info['status'] = 200
    cmd = f"    await page.screenshot({{ path: '{screenshot_info['path']}', fullPage: \
{str(screenshot_info['full_page']).lower() if not None else 'true' }}});\n"

    screenshot_info['cmd'] = cmd
    with open('tempfile', 'a') as f:
        f.write(cmd)
    return json.dumps(screenshot_info)

def expect_text(**kwargs):
    """Expect text on the page"""
    expect_info = {key: kwargs.get(key)
                       for key in params_to_pass['expect_text']}
    cmd = f"    expect(page.getByText(/{expect_info['text']}/).nth({expect_info.get('index') if not 'None' else 0})).toHaveText(/{expect_info['text']}/);\n"
    expect_info['cmd'] = cmd
    with open('tempfile', 'a') as f:
        f.write(cmd)
    return json.dumps(expect_info)
