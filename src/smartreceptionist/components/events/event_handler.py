import asyncio
import logging

from ..app_state import AppState
from ..events.event import Event
from ..image_processing.image_queue import ImageQueue
from ..telegram_bot import TelegramBot
from ..ws_server import WebSocketServer, WSMessage


class EventHandler:
    def __init__(self, telegram_bot: TelegramBot, ws_server: WebSocketServer, app_state: AppState, image_queue: ImageQueue):
        self.telegram_bot = telegram_bot
        self.ws_server = ws_server
        self.app_state = app_state
        self.image_queue = image_queue
        self.logger = logging.getLogger(__name__)

    async def handle_tg_state_change(self, event: Event):
        try:
            message = WSMessage(event_type="change_state", data=event.data)
            await self.ws_server.send("esp_s3", message)
        except Exception as e:
            self.logger.error(f"Error sending message to WebSocket: {e}")

    async def handle_esp_state_change(self, event: Event):
        device = event.data["device"]
        new_state_str = event.data["state"]

        state_enum_class = getattr(self.app_state, f"{device}_state").__class__
        new_state = state_enum_class(new_state_str)
        setattr(self.app_state, f"{device}_state", new_state)

    async def handle_motion_detected(self):
        await asyncio.wait_for(self.image_queue.dequeue_processed_image(), timeout=30)

        for interval in [3, 6, 9]:
            if await self._wait_for_detection_or_timeout(interval):
                self.logger.info("Person detected during retry interval.")  # Combined logs
                return

            try:
                await asyncio.wait_for(self.image_queue.dequeue_processed_image(), timeout=30)
            except asyncio.TimeoutError:
                break

            if self.image_queue.num_of_face_detected_images >= 2:
                break

        if self.image_queue.num_of_face_detected_images >= 2:
            self.logger.info(f"Person confirmed at the gate! Sending {self.image_queue.num_of_face_detected_images} images.")
            images = await self.image_queue.get_face_detected_images()

            # TODO: Send confirmed images to admin
            for image in images:
                await image.save_to_disk()  # Temporary save to disk
        else:
            self.logger.info("Motion detected, but no person confirmed.")

        await self.image_queue.cleanup()

    async def _wait_for_detection_or_timeout(self, timeout_interval: int) -> bool:
        try:
            await asyncio.wait_for(self.app_state.person_detected_event.wait(), timeout=timeout_interval)
            return True
        except asyncio.TimeoutError:
            await self.ws_server.send("esp_cam", WSMessage(event_type="capture_image", data={}))
            return False

    async def handle_person_detected(self):
        self.app_state.person_detected_event.set()

        if await self.image_queue.dequeue_processed_image() and self.image_queue.num_of_face_detected_images >= 2:
            self.logger.info("Person confirmed at the gate!")
            images = await self.image_queue.get_face_detected_images()

            # TODO: Send confirmed images to admin
            for image in images:
                await image.save_to_disk()  # Temporary save to disk
        else:
            for interval in [5, 9, 13]:
                await asyncio.sleep(interval)
                await self.ws_server.send("esp_cam", WSMessage(event_type="capture_image", data={}))

                try:
                    await asyncio.wait_for(self.image_queue.dequeue_processed_image(), timeout=30)
                except asyncio.TimeoutError:
                    break

                if self.image_queue.num_of_face_detected_images >= 2:
                    self.logger.info("Person confirmed at the gate!")
                    images = await self.image_queue.get_face_detected_images()
                    # TODO: Send confirmed images to admin
                    for image in images:
                        await image.save_to_disk()  # Temporary save to disk
                    break

        await self.image_queue.cleanup()
