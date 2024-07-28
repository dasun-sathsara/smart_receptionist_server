import asyncio
import json
import logging
from typing import Dict

import websockets
from dotenv import load_dotenv
from rich.logging import RichHandler

# Load environment variables from .env file
load_dotenv()

# Set up logging with RichHandler
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],  # Enable rich tracebacks for errors
)

# Set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def websocket_client():
    uri = "ws://34.124.199.12:8765"  # Replace with your actual WebSocket server address

    while True:
        try:
            async with websockets.connect(uri) as websocket:
                logger.info("[ESPS3] Connected to the server")

                # Send the init message (registering as esp_s3)
                init_message = json.dumps({"event_type": "init", "data": {"device": "esp_s3"}})
                await websocket.send(init_message)
                logger.info("[ESPS3] Sent init message")

                async def send_unsolicited_message():
                    await asyncio.sleep(10)
                    unsolicited_message = json.dumps({"event_type": "motion_detected", "data": {}})
                    await websocket.send(unsolicited_message)
                    logger.info("[ESPS3] Sent unsolicited message")

                # unsolicited_task = asyncio.create_task(send_unsolicited_message())

                async def handle_change_state(event: Dict):
                    state = event["data"]["state"]
                    await asyncio.sleep(1)
                    response = json.dumps(
                        {
                            "event_type": "change_state",
                            "data": {"device": event["data"]["device"], "state": state},
                        }
                    )
                    await websocket.send(response)
                    logger.info(f"[ESPS3] Sent response: {response}")

                try:
                    async for message in websocket:
                        logger.info(f"[ESPS3] Received message: {message}")
                        try:
                            message_data = json.loads(message)
                            if message_data["event_type"] == "change_state":
                                await handle_change_state(message_data)
                        except json.JSONDecodeError:
                            logger.error(f"[ESPS3] Received invalid JSON: {message}")
                except websockets.ConnectionClosed:
                    logger.info("[ESPS3] Server disconnected. Attempting to reconnect...")
                # finally:
                # unsolicited_task.cancel()

        except (OSError, websockets.InvalidURI, websockets.InvalidHandshake, ConnectionRefusedError) as e:
            if isinstance(e, ConnectionRefusedError):
                logger.error("[ESP CAM] Connection refused. Is the server running? Retrying in 5 seconds...")
            else:
                logger.error(f"[ESP CAM] Failed to connect: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)


async def main():
    client_task = asyncio.create_task(websocket_client())

    # This will allow the script to run until interrupted
    try:
        await client_task
    except asyncio.CancelledError:
        pass


def run():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("[ESPS3] Received keyboard interrupt, shutting down...")


if __name__ == "__main__":
    run()
