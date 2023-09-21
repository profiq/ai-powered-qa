example = """
"""

indykite = """Navigate to https://buildtoriot-dev.web.app
    Click on 'Sign in'
    Expect title 'Login'
    Fill email 'yexifoc431@quipas.com'
    Fill password 'crre%N^8wLkW9'
    Click "Login" button
    Expect text 'You are now signed in'
    Expect title 'Discover | IndyRiot Dev'
    Click on data-icon=close
    Take screenshot full False to file 'screenshot/indyriot/login.png'"""

#Take screenshot full False to file path 'screenshot/login.png

example_test = {
    "name": "gmail_login",
    "title": "User successfully signs in to google",
    "steps": example,
}
