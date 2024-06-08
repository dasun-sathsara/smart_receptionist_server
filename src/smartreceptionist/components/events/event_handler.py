import logging

from ..app_state import AppState
from ..events.event import Event
from ..telegram_bot import TelegramBot
from ..ws_server import WebSocketServer, WSMessage


class EventHandler:
    def __init__(self, telegram_bot: TelegramBot, ws_server: WebSocketServer, app_state: AppState):
        self.telegram_bot = telegram_bot
        self.ws_server = ws_server
        self.app_state = app_state
        self.logger = logging.getLogger(__name__)

    async def handle_tg_state_change(self, event: Event):
        try:
            message = WSMessage(event_type="change_state", data=event.data)
            await self.ws_server.send("esp_s3", message)
        except Exception as e:
            self.logger.error(f"Error sending message to WebSocket: {e}")

    async def handle_esp_state_change(self, event: Event):
        self.logger.info(f"Received ESP state change event: {event.data}")
        device = event.data["device"]
        new_state_str = event.data["state"]  # Get the state as a string

        # Use getattr to dynamically get the enum class based on device
        state_enum_class = getattr(self.app_state, f"{device}_state").__class__
        new_state = state_enum_class(new_state_str)  # Convert the string to the appropriate enum member

        # Use setattr to dynamically set the state attribute on the app_state object
        setattr(self.app_state, f"{device}_state", new_state)
