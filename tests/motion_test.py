import asyncio
import json
import logging

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


async def simulate_motion_detection():
    # uri = "ws://35.197.142.113:8765"  # Replace with your WebSocket server URI
    uri = "ws://localhost:8765"  # Replace with your WebSocket server URI

    while True:
        try:
            logger.info("[ESP CAM] Attempting to connect to the server...")
            async with websockets.connect(uri) as websocket:
                logger.info("[ESP CAM] Connected to WebSocket server")

                # Simulate ESP32 Cam initialization
                init_message = json.dumps(
                    {"event_type": "init", "data": {"device": "esp_cam"}},
                )
                await websocket.send(init_message)
                logger.info("[ESP CAM] Sent init message as esp_cam")
                await asyncio.sleep(1)

                # Trigger motion detection
                motion_message = json.dumps(
                    {"event_type": "motion_detected", "data": {}},
                )
                await websocket.send(motion_message)

                # Send an image right away
                with open("test_images/test1.jpg", "rb") as f:
                    image_bytes = f.read()
                    await websocket.send(b"IMAGE:" + image_bytes)

                logger.info("[ESP CAM] Triggered motion detection and sent an image")

                # await asyncio.sleep(3)
                #
                # # Trigger person detection
                # person_message = json.dumps(
                #     {"event_type": "person_detected", "data": {}},
                # )
                # await websocket.send(person_message)
                #
                # # Send another image
                # with open("test_images/test2.jpg", "rb") as f:
                #     image_bytes = f.read()
                #     await websocket.send(b"IMAGE:" + image_bytes)

                logger.info("[ESP CAM] Triggered person detecktion and sent another image")

                try:
                    async for message in websocket:
                        try:
                            msg_data = json.loads(message)
                            if msg_data["event_type"] == "capture_image":
                                await asyncio.sleep(1)
                                with open("test_images/test2.jpg", "rb") as f:
                                    image_bytes = f.read()
                                    await websocket.send(b"IMAGE:" + image_bytes)
                                logger.info("[ESP CAM] Sent an image in response to capture_image event")
                        except json.JSONDecodeError:
                            logger.warning("[ESP CAM] Received message is not valid JSON")
                except websockets.ConnectionClosed:
                    logger.info("[ESP CAM] Server disconnected. Attempting to reconnect...")

        except (OSError, websockets.InvalidURI, websockets.InvalidHandshake) as e:
            if isinstance(e, ConnectionRefusedError):
                logger.error("[ESP CAM] Connection refused. Is the server running? Retrying in 5 seconds...")
            else:
                logger.error(f"[ESP CAM] Failed to connect: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)


async def main():
    client_task = asyncio.create_task(simulate_motion_detection())

    try:
        await client_task
    except asyncio.CancelledError:
        pass


def run():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("[ESP CAM] Received keyboard interrupt, shutting down...")


if __name__ == "__main__":
    run()
