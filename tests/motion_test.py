import asyncio
import base64
import json
import logging

import websockets


async def simulate_motion_detection():
    async with websockets.connect("ws://localhost:8765") as websocket:  # Replace with your WebSocket server URI
        logging.info("Connected to WebSocket server")

        # Simulate ESP32 Cam initialization
        init_message = json.dumps(
            {"event_type": "init", "data": {"device": "esp_cam"}},
        )
        await websocket.send(init_message)
        logging.info("Sent init message as esp_cam")
        await asyncio.sleep(1)

        # Load image and convert to base64
        with open("test_images/test1.jpg", "rb") as f:
            image_bytes = f.read()
        image_data = base64.b64encode(image_bytes).decode("utf-8")
        image_message = json.dumps(
            {
                "event_type": "motion_detected",
                "data": {"image_data": image_data},
            }
        )
        await websocket.send(image_message)
        logging.info("Sent image data")

        # Simulate sending another image
        await asyncio.sleep(4)
        with open("test_images/test2.jpg", "rb") as f:
            image_bytes = f.read()
            image_data = base64.b64encode(image_bytes).decode("utf-8")
        await websocket.send(
            json.dumps(
                {
                    "event_type": "person_detected",
                    "data": {"image_data": image_data},
                }
            )
        )

        async for message in websocket:
            try:
                msg_data = json.loads(message)
                if msg_data["event_type"] == "capture_image":
                    await asyncio.sleep(0.2)
                    with open("test_images/test2.jpg", "rb") as f:
                        image_bytes = f.read()
                        image_data = base64.b64encode(image_bytes).decode("utf-8")
                    await websocket.send(
                        json.dumps(
                            {
                                "event_type": "image",
                                "data": {"image_data": image_data},
                            }
                        )
                    )
                    logging.info("Sent another image")
            except json.JSONDecodeError:
                pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(simulate_motion_detection())
