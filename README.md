# ai-playwright-gpt-functions

## Description
This repo is a demonstration of how to use GPT-3 to generate text using Playwright. We use tools written in langchain library along with openai's function calls.

## Setup
- python (our experiments run on python 3.10.12)
- Install langchain
    - `pip install langchain` into python venv and replace the langchain folder from [langchain fork](https://github.com/jakub-profiq/langchain/tree/jj-merge)
    - or place [langchain fork](https://github.com/jakub-profiq/langchain/tree/jj-merge) to the same folder as this repo. Refer to [langchain fork](https://github.com/jakub-profiq/langchain/tree/jj-merge) on how to install it. Then in `main.py` uncomment two lines before the langchain imports.

## Usage
- run `python main.py`
- You will enter a User-agent loop. You can prompt, validate and communicate with our written "agent".

## How it works?
![alt text](./images/user-agent-loop)
