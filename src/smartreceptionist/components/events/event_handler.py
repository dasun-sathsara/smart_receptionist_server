from ..app_state import AppState
from ..telegram_bot import TelegramBot
from ..ws_server import WebSocketServer


class EventHandler:
    def __init__(self, telegram_bot: TelegramBot, ws_server: WebSocketServer, app_state: AppState):
        self.telegram_bot = telegram_bot
        self.ws_server = ws_server
        self.app_state = app_state
