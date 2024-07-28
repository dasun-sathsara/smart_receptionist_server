import asyncio

import websockets


async def test_connection():
    uri = "ws://34.47.99.122:8765"
    try:
        async with websockets.connect(uri) as websocket:
            print("Successfully connected to the WebSocket server!")

            # Optional: Send a test message
            await websocket.send("Hello, WebSocket Server!")
            response = await websocket.recv()
            print(f"Received response: {response}")

    except websockets.exceptions.ConnectionClosed:
        print("Connection closed unexpectedly.")
    except ConnectionRefusedError:
        print("Connection refused. The server might be down or unreachable.")
    except Exception as e:
        print(f"An error occurred: {e}")


asyncio.get_event_loop().run_until_complete(test_connection())
