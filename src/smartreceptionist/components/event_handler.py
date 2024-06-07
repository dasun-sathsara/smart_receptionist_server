import asyncio

from .interfaces.iapp_state import IAppState
from .interfaces.ievent_handler import IEventHandler
from .event import Event
from .telegram_bot import TelegramBot
from .ws_server import WebSocketServer


class EventHandler(IEventHandler):
    def __init__(self, ):
        self.queue = asyncio.Queue()

    async def process_events(self, telegram_bot: TelegramBot, app_state: IAppState, ws_server: WebSocketServer):
        while True:
            try:
                event = await self.queue.get()
                # User started the bot
                if event.event_type == 'start':
                    await ws_server.send('hi')
                self.queue.task_done()
            except asyncio.CancelledError:
                break

    async def enqueue_event(self, event: Event):
        self.queue.put_nowait(event)
