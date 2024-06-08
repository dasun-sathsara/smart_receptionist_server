import asyncio
import json
import logging
from typing import Dict

import websockets


async def websocket_client():
    uri = "ws://localhost:8765"  # Replace with your actual WebSocket server address

    async with websockets.connect(uri) as websocket:
        # Send the init message (registering as esp_cam)
        init_message = json.dumps({"event_type": "init", "data": {"device": "esp_cam"}})
        await websocket.send(init_message)
        logging.info("[ESPCAM] Sent init message")

        async def handle_change_state(event: Dict):
            ...

        # Receive and process messages from the server
        async for message in websocket:
            logging.info(f"[ESPCAM] Received message: {message}")
            try:
                message_data = json.loads(message)
            except json.JSONDecodeError:
                logging.error(f"[ESPCAM] Received invalid JSON: {message}")
                continue


# Run the client
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)  # Set up basic logging
    asyncio.run(websocket_client())
