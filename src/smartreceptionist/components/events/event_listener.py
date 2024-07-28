import asyncio
import logging
from typing import TYPE_CHECKING

from .event import Event, EventType

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
        if event.event_type != EventType.AUDIO_DATA:
            self.logger.info(f"Handling event: {event}")

        if event.event_type == EventType.CHANGE_STATE:
            await asyncio.create_task(event_handler.handle_ap_state_change_event(event))
        elif event.event_type == EventType.MOTION_DETECTED:
            await asyncio.create_task(event_handler.handle_motion_detected_event())
        elif event.event_type == EventType.PERSON_DETECTED:
            await asyncio.create_task(event_handler.handle_person_detected_event())
        elif event.event_type == EventType.AUDIO:
            await asyncio.create_task(event_handler.handle_audio_event(event))
        elif event.event_type == EventType.CAMERA:
            await asyncio.create_task(event_handler.handle_camera_event(event))
        elif event.event_type == EventType.ACCESS_CONTROL:
            await asyncio.create_task(event_handler.handle_access_control_event(event))
        elif event.event_type == EventType.RECORDING_SENT:
            await asyncio.create_task(event_handler.handle_recording_sent_event())
        elif event.event_type == EventType.RESET_DEVICE:
            await asyncio.create_task(event_handler.handle_reset_device_event(event))
        elif event.event_type == EventType.ENROLL_FINGERPRINT:
            await asyncio.create_task(event_handler.handle_enroll_fingerprint())
        elif event.event_type == EventType.FINGERPRINT_ENROLLED:
            await asyncio.create_task(event_handler.handle_fingerprint_enrolled(event))
        elif event.event_type == EventType.FINGERPRINT_ENROLLMENT_FAILED:
            await asyncio.create_task(event_handler.handle_fingerprint_enrollment_failed(event))
        elif event.event_type == EventType.MOTION_ENABLE:
            await asyncio.create_task(event_handler.handle_motion_enable_event(event))
        elif event.event_type == EventType.CHANGE_SERVER:
            await asyncio.create_task(event_handler.handle_change_server_event(event))

        # Handling raw data
        elif event.event_type == EventType.IMAGE_DATA:
            await asyncio.create_task(event_handler.handle_image_data(event))
        elif event.event_type == EventType.AUDIO_DATA:
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
