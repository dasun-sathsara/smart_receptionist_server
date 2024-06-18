import asyncio
import json
import logging
import time

import websockets

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


async def receive_audio(uri):
    async with websockets.connect(uri) as websocket:
        logging.info("Connected to WebSocket server")
        await websocket.send(json.dumps({"event_type": "init", "data": {"device": "esp_s3"}}))
        logging.info("Sent init message")

        audio_chunks = []
        recording = False
        async for message in websocket:
            try:
                data = json.loads(message)
                event_type = data.get("event_type")
                if event_type == "start_playing":
                    logging.info("Started recording")
                    recording = True
                    audio_chunks = []
                elif event_type == "stop_playing" and recording:
                    logging.info("Stopped recording")
                    timestamp = time.strftime("%Y%m%d-%H%M%S")
                    filename = f"recorded_audio_{timestamp}.pcm"
                    with open(filename, "wb") as f:
                        f.write(b"".join(audio_chunks))
                    logging.info(f"Audio saved to {filename}")
                    recording = False
                else:
                    logging.info(f"Received event: {data}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                if recording:
                    audio_chunks.append(message)
                else:
                    logging.warning(f"Error decoding message: {message}")


if __name__ == "__main__":
    asyncio.run(receive_audio("ws://localhost:8765"))
