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
        self._handler_tasks = set()  # Store references to handler tasks

    async def listen(self, event_handler: "EventHandler"):
        self.logger.info("Event listener started.")

        while True:
            try:
                event = await self.queue.get()
                task = asyncio.create_task(self._handle_event(event, event_handler))
                self._handler_tasks.add(task)  # Add the task to the set
                task.add_done_callback(self._handler_tasks.discard)  # Remove when done

            except asyncio.CancelledError:
                self.logger.info("Event listener stopped.")
                await self._cancel_handler_tasks()
                break

    async def _handle_event(
        self,
        event: Event,
        event_handler: "EventHandler",
    ):
        # Do not log if the event is audio_data as it will clutter the logs
        if event.event_type != "audio_data":
            self.logger.info(f"Handling event: {event.event_type}")

        if event.event_type == "change_state":
            await asyncio.create_task(event_handler.handle_ap_state_change_event(event))
        elif event.event_type == "motion_detected":
            await asyncio.create_task(event_handler.handle_motion_detected_event())
        elif event.event_type == "person_detected":
            await asyncio.create_task(event_handler.handle_person_detected_event())
        elif event.event_type == "audio":
            await asyncio.create_task(event_handler.handle_audio_event(event))
        elif event.event_type == "camera":
            await asyncio.create_task(event_handler.handle_camera_event(event))

        # Handling raw data
        elif event.event_type == "image_data":
            await asyncio.create_task(event_handler.handle_image_data(event))
        elif event.event_type == "audio_data":
            await asyncio.create_task(event_handler.handle_audio_data(event))

        # Mark the task as done
        self.queue.task_done()

    async def _cancel_handler_tasks(self):
        for task in self._handler_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def enqueue_event(self, event: Event):
        try:
            await self.queue.put(event)
        except asyncio.QueueFull:
            self.logger.error("Event queue is full. Event dropped.")
