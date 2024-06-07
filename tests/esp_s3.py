import asyncio
import json
import logging

import websockets


async def websocket_client():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        # Send init message to the server
        message = json.dumps({
            "event_type": "init",
            "data": "esp_cam"
        })

        await websocket.send(message)

        # Receive and print messages from the server
        async for message in websocket:
            logging.info(f"[ESPCAM] Received message: {message}")


# Run the client
asyncio.run(websocket_client())
