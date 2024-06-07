import json
import logging
from dataclasses import dataclass

from websockets import WebSocketServerProtocol

from .app_state import AppState
from .app_state import ESPState
from .events.event_listener import EventListener


@dataclass
class WSMessage:
    event_type: str
    data: str


class WebSocketServer:
    def __init__(self, event_listener: EventListener, app_state: AppState):
        self.app_state = app_state
        self.event_listener = event_listener
        self.connected_devices = {}  # New attribute to keep track of connected devices

    async def send(self, data: any):
        logging.info(f"Sending data: {data}")

    async def process_messages(self, message: WSMessage, websocket: WebSocketServerProtocol):

        # ESPs are connected
        if message.event_type == 'init':
            self.app_state.set_esps_state(message.data, ESPState.CONNECTED)
            self.connected_devices[websocket] = message.data  # Add the device to the dictionary

    async def handle_new_connection(self, websocket: WebSocketServerProtocol):
        logging.info(f"Websocket client connected: {websocket.remote_address}")

        try:
            async for message in websocket:
                logging.info(f"Received message: {message}")

                try:
                    message = WSMessage(**json.loads(message))
                except json.JSONDecodeError:
                    logging.error(f"Invalid JSON data: {message}")
                    continue

                await self.process_messages(message, websocket)
        finally:
            logging.info(f"Websocket client disconnected: {websocket.remote_address}")
            device = self.connected_devices.pop(websocket)  # Remove the device from the dictionary

            self.app_state.set_esps_state(device, ESPState.DISCONNECTED)
            await websocket.close()
