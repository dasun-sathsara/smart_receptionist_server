import logging

from websockets import WebSocketServerProtocol

from .interfaces.iapp_state import IAppState
from .interfaces.ievent_handler import IEventHandler


class WebSocketServer:
    def __init__(self, event_listener: IEventHandler, app_state: IAppState):
        self.app_state = app_state
        self.event_listener = event_listener

    async def send(self, data):
        logging.info(f"Sending data: {data}")

    async def process_messages(self):
        ...

    async def handle_new_connection(self, websocket: WebSocketServerProtocol):
        ...
