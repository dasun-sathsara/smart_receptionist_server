import asyncio
import logging
from typing import TYPE_CHECKING

from .event import Event

if TYPE_CHECKING:
    from .event_handler import EventHandler


class EventListener:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.logger = logging.getLogger(__name__)

    async def listen(self, event_handler: "EventHandler"):

        self.logger.info("Event listener started.")

        while True:
            try:
                event = await self.queue.get()
                self.logger.debug(f"Received event: {event}")
                await self._handle_event(event, event_handler)
                self.queue.task_done()
            except asyncio.CancelledError:
                self.logger.info("Event listener stopped.")
                break

    async def _handle_event(self, event: Event, event_handler: "EventHandler"):

        if event.event_type == "change_state" and event.origin == "tg":
            try:
                await event_handler.handle_tg_state_change(event)
            except Exception as e:
                self.logger.error(f"Error handling TG state change: {e}")

        elif event.event_type == "change_state" and event.origin == "esp":
            try:
                await event_handler.handle_esp_state_change(event)
            except Exception as e:
                self.logger.error(f"Error handling ESP state change: {e}")

    async def enqueue_event(self, event: Event):

        try:
            await self.queue.put(event)
            self.logger.debug(f"Enqueued event: {event}")  # Log enqueued event
        except asyncio.QueueFull:
            self.logger.error("Event queue is full. Event dropped.")
