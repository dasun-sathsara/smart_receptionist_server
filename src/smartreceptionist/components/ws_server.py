import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import aiofiles
from websockets import ConnectionClosed, WebSocketServerProtocol

from .app_state import AppState, ESPState
from .config import Config
from .events.event import Event
from .events.event_listener import EventListener


@dataclass
class WSMessage:
    event_type: str
    data: dict


class WSMessageEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, WSMessage):
            return asdict(o)  # Convert dataclass to dict
        return super().default(o)


class WebSocketServer:
    def __init__(self, event_listener: EventListener, app_state: AppState):
        self.app_state = app_state
        self.event_listener = event_listener
        self.connected_devices = {}
        self.logger = logging.getLogger(__name__)

    async def send(self, device: Literal["esp_cam", "esp_s3"], message: WSMessage):
        for websocket, device_name in self.connected_devices.items():
            if device_name == device:
                try:
                    await websocket.send(json.dumps(message, cls=WSMessageEncoder))
                    self.logger.info(f"Sent message to {device}: {message}")
                except ConnectionClosed:
                    self.logger.warning(f"Failed to send to {device}: connection closed.")

    async def _handle_init_message(self, message: WSMessage, websocket: WebSocketServerProtocol):
        device_name = message.data["device"]
        if device_name in ("esp_cam", "esp_s3"):
            self.connected_devices[websocket] = device_name
            setattr(self.app_state, f"{device_name}_state", ESPState.CONNECTED)
            self.logger.info(f"{device_name} connected.")

    async def stream_audio(self, audio_file_path: Path):
        device_name = "esp_s3"

        # Find the websocket for the device
        websocket = next((ws for ws, name in self.connected_devices.items() if name == device_name), None)

        if not websocket:
            self.logger.warning(f"No connected websocket found for device: {device_name}")
            return

        try:
            self.logger.info(f"Started streaming audio to {websocket.remote_address}")
            async with aiofiles.open(audio_file_path, "rb") as audio_file:
                while self.app_state.is_playing:
                    chunk = await audio_file.read(Config.DEFAULT_CHUNK_SIZE)
                    if not chunk:
                        break  # End of file
                    await websocket.send(chunk)
                    # Delay for real-time playback
                    # await asyncio.sleep(Config.DEFAULT_CHUNK_SIZE / (Config.SAMPLE_RATE * Config.BYTES_PER_SAMPLE))
                    await asyncio.sleep(0.001)
            # await self.send("esp_s3", WSMessage(event_type="audio", data={"action": "stop_playing"}))
            self.logger.info(f"Finished streaming audio to {websocket.remote_address}")
        except ConnectionClosed:
            self.logger.warning(f"Connection closed by client {websocket.remote_address} during audio streaming.")
        except Exception as e:
            self.logger.error(f"Error during audio streaming: {e}")

    async def handle_events(self, message: WSMessage, websocket: WebSocketServerProtocol):
        if message.event_type == "init":
            await self._handle_init_message(message, websocket)

        if message.event_type in ("change_state", "person_detected", "motion_detected", "image", "audio"):
            await self.event_listener.enqueue_event(Event(event_type=message.event_type, origin="esp", data=message.data))

    async def handle_audio_chunk(self, message: bytes, _: WebSocketServerProtocol):
        await self.event_listener.enqueue_event(Event(event_type="audio_data", origin="esp", data={"audio": message}))

    async def handle_image_data(self, message: bytes, _: WebSocketServerProtocol):
        await self.event_listener.enqueue_event(Event(event_type="image_data", origin="esp", data={"image": message}))

    async def handle_new_connection(self, websocket: WebSocketServerProtocol):
        self.logger.info(f"Websocket client connected: {websocket.remote_address}")

        try:
            async for message in websocket:
                if isinstance(message, str):  # Check if it's a string
                    message = message.encode("utf-8")  # Encode to bytes

                # Directly check if message starts with JSON opening brace '{'
                if message.startswith(b"{"):
                    try:
                        # Log the received message
                        self.logger.info(f"Received message: {message.decode('utf-8')}")
                        message = json.loads(message.decode("utf-8"))
                        message = WSMessage(**message)
                        _ = asyncio.create_task(self.handle_events(message, websocket))
                    except json.JSONDecodeError:
                        self.logger.warning("Invalid JSON message received")

                else:  # Raw data
                    prefix, data = message.split(b":", 1)
                    if prefix == b"AUDIO":
                        _ = asyncio.create_task(self.handle_audio_chunk(data, websocket))
                    elif prefix == b"IMAGE":
                        _ = asyncio.create_task(self.handle_image_data(data, websocket))
                    else:
                        self.logger.warning("Unknown raw data type received")

        except ConnectionClosed as e:
            self.logger.warning(f"Connection closed unexpectedly: {e.code} - {e.reason}")
        finally:
            self.logger.info(f"Websocket client disconnected: {websocket.remote_address}")

            # Clean up connected devices
            if websocket in self.connected_devices:
                device_name = self.connected_devices.pop(websocket)
                setattr(self.app_state, f"{device_name}_state", ESPState.DISCONNECTED)
                self.logger.info(f"{device_name} disconnected.")
