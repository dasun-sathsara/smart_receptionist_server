import asyncio
import json
import logging
from dataclasses import asdict
from dataclasses import dataclass
from typing import Literal

from websockets import WebSocketServerProtocol, ConnectionClosed

from .app_state import AppState, ESPState
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
                except ConnectionClosed:
                    self.logger.warning(f"Failed to send to {device}: connection closed.")

    async def _handle_init_message(self, message: WSMessage, websocket: WebSocketServerProtocol):
        device_name = message.data["device"]
        if device_name in ("esp_cam", "esp_s3"):
            self.connected_devices[websocket] = device_name
            setattr(self.app_state, f"{device_name}_state", ESPState.CONNECTED)
            self.logger.info(f"{device_name} connected.")

    async def process_messages(self, message: WSMessage, websocket: WebSocketServerProtocol):
        if message.event_type == "init":
            await self._handle_init_message(message, websocket)

        elif message.event_type == "change_state":
            await self.event_listener.enqueue_event(Event(event_type=message.event_type, origin="esp", data=message.data))
        elif message.event_type == "person_detected":
            await self.event_listener.enqueue_event(Event(event_type=message.event_type, origin="esp", data=message.data))
        elif message.event_type == "motion_detected":
            await self.event_listener.enqueue_event(Event(event_type=message.event_type, origin="esp", data=message.data))
        elif message.event_type == "image":
            await self.event_listener.enqueue_event(Event(event_type=message.event_type, origin="esp", data=message.data))

    async def handle_new_connection(self, websocket: WebSocketServerProtocol):
        self.logger.info(f"Websocket client connected: {websocket.remote_address}")

        try:
            async for message in websocket:
                self.logger.info(f"Received message: {message[:100]}")

                try:
                    message = WSMessage(**json.loads(message))
                except json.JSONDecodeError:
                    self.logger.error(f"Invalid JSON data: {message}")
                    await websocket.close(code=1007, reason="Invalid JSON")
                    return

                _ = asyncio.create_task(self.process_messages(message, websocket))

        except ConnectionClosed as e:
            self.logger.warning(f"Connection closed unexpectedly: {e.code} - {e.reason}")
        finally:
            self.logger.info(f"Websocket client disconnected: {websocket.remote_address}")

            # Clean up connected devices
            if websocket in self.connected_devices:
                device_name = self.connected_devices.pop(websocket)
                setattr(self.app_state, f"{device_name}_state", ESPState.DISCONNECTED)
                self.logger.info(f"{device_name} disconnected.")
