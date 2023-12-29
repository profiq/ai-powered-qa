import streamlit as st
from playwright_class import PlaywrightWrapper


@st.cache_resource
def get_playwright_wrapper():
    return PlaywrightWrapper()


playwright_wrapper = get_playwright_wrapper()

st.title("Async URL Screenshot App")

url = st.text_input("Enter a URL", "https://example.com")

if st.button("Take Screenshot"):
    screenshot = playwright_wrapper.take_screenshot(url)
    st.image(screenshot)
