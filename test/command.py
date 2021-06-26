import asyncio, socket
from os import path
from cdp import target
asyncio.Queue()
target.attach_to_browser_target("9ded39ba-fd15-4d67-9c84-a2c17f8eebb3")

def connect_to_browser(loop):
    reader, writer = asyncio.open_connection(
        host = "localhost", 
        port = 9223,
        path = f"/devtools/browser/9ded39ba-fd15-4d67-9c84-a2c17f8eebb3"
    )