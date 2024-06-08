import asyncio
import json
import logging
from typing import Dict

import websockets


async def websocket_client():
    uri = "ws://localhost:8765"  # Replace with your actual WebSocket server address

    async with websockets.connect(uri) as websocket:
        # Send the init message (registering as esp_cam)
        init_message = json.dumps({"event_type": "init", "data": {"device": "esp_s3"}})
        await websocket.send(init_message)
        logging.info("[ESPS3] Sent init message")

        async def handle_change_state(event: Dict):
            state = event["data"]["state"]

            # simulate some processing
            await asyncio.sleep(1)

            # Send a response message
            response = json.dumps({"event_type": "change_state", "data": {"device": event["data"]["device"], "state": state}})
            await websocket.send(response)
            logging.info(f"[ESPS3] Sent response: {response}")

        # Receive and process messages from the server
        async for message in websocket:
            logging.info(f"[ESPS3] Received message: {message}")
            try:
                message_data = json.loads(message)

            except json.JSONDecodeError:
                logging.error(f"[ESPS3] Received invalid JSON: {message}")
                continue

            if message_data["event_type"] == "change_state":
                await handle_change_state(message_data)
            # Add handling for other event types if needed


# Run the client
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)  # Set up basic logging
    asyncio.run(websocket_client())
