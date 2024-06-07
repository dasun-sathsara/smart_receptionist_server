import asyncio
from typing import TYPE_CHECKING

from .event import Event

if TYPE_CHECKING:
    from .event_handler import EventHandler


class EventListener:
    def __init__(self, ):
        self.queue = asyncio.Queue()

    async def listen(self, event_handler: 'EventHandler'):
        while True:
            try:
                event = await self.queue.get()
                # User started the bot
                if event.event_type == 'start':
                    ...
                self.queue.task_done()
            except asyncio.CancelledError:
                break

    async def enqueue_event(self, event: Event):
        self.queue.put_nowait(event)
