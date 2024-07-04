import asyncio
import json
import logging
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from websockets import ConnectionClosed, WebSocketServerProtocol

from .app_state import AppState, ESPState
from .config import Config
from .events.event import Event, EventType, Origin
from .events.event_listener import EventListener


@dataclass
class WSMessage:
    event_type: EventType
    data: dict

    def __str__(self):
        return f"{self.event_type.name}: {self.data}"

    @classmethod
    def from_dict(cls, data: dict):
        try:
            event_type = EventType(data["event_type"])
        except ValueError:
            raise ValueError(f"Invalid event type: {data['event_type']}")

        return cls(event_type=event_type, data=data.get("data", {}))


class WSMessageEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, WSMessage):
            return {"event_type": o.event_type.value, "data": o.data}
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

    async def start_prefetching(self, audio_file_path: Path):
        device_name = "esp_s3"
        websocket = next((ws for ws, name in self.connected_devices.items() if name == device_name), None)
        if not websocket:
            self.logger.warning(f"No connected websocket found for device: {device_name}")
            return

        try:
            self.logger.info(f"Started streaming audio to {websocket.remote_address}")
            await self.send("esp_s3", WSMessage(event_type=EventType.AUDIO, data={"action": "start_prefetch"}))

            with wave.open(str(audio_file_path), "rb") as wav_file:
                if wav_file.getnchannels() != 1 or wav_file.getsampwidth() != 2 or wav_file.getframerate() != Config.SAMPLE_RATE:
                    raise ValueError(f"Unexpected WAV format. Expected: 1 channel, 16-bit, {Config.SAMPLE_RATE}Hz")

                # Skip the WAV header (44 bytes for standard WAV files)
                wav_file.setpos(44 // wav_file.getsampwidth())

                while True:
                    chunk = wav_file.readframes(Config.DEFAULT_CHUNK_SIZE // 2)
                    if not chunk:
                        break

                    await websocket.send(chunk)
                    await asyncio.sleep(0.01)

            await self.send("esp_s3", WSMessage(event_type=EventType.AUDIO, data={"action": "stop_prefetch"}))
            self.logger.info(f"Finished streaming audio to {websocket.remote_address}")
        except ConnectionClosed:
            self.logger.warning(f"Connection closed by client {websocket.remote_address} during audio streaming.")
        except Exception as e:
            self.logger.error(f"Error during audio streaming: {e}")

    async def handle_events(self, message: WSMessage, websocket: WebSocketServerProtocol):
        if message.event_type == EventType.INIT:
            await self._handle_init_message(message, websocket)
        else:
            await self.event_listener.enqueue_event(Event(message.event_type, Origin.ESP, message.data))

    async def handle_audio_chunk(self, message: bytes, _: WebSocketServerProtocol):
        await self.event_listener.enqueue_event(
            Event(event_type=EventType.AUDIO_DATA, origin=Origin.ESP, data={"audio": message})
        )

    async def handle_image_data(self, message: bytes, _: WebSocketServerProtocol):
        await self.event_listener.enqueue_event(
            Event(event_type=EventType.IMAGE_DATA, origin=Origin.ESP, data={"image": message})
        )

    async def handle_new_connection(self, websocket: WebSocketServerProtocol):
        self.logger.info(f"Websocket client connected: {websocket.remote_address}")

        try:
            async for message in websocket:
                if isinstance(message, str):  # Check if it's a string
                    message = message.encode("utf-8")  # Encode to bytes

                # Directly check if message starts with JSON opening brace '{'
                if message.startswith(b"{"):
                    try:
                        message_dict = json.loads(message.decode("utf-8"))
                        ws_message = WSMessage.from_dict(message_dict)
                        self.logger.info(f"Received message: {ws_message}")
                        await self.handle_events(ws_message, websocket)
                    except json.JSONDecodeError:
                        self.logger.warning("Invalid JSON message received")
                    except ValueError as e:
                        self.logger.warning(f"Invalid message format: {e}")

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
