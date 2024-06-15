import asyncio
import logging

from sinric import SinricPro
from sinric import SinricProConstants

from ..app_state import AppState, GateState, LightState
from ..config import Config
from ..events.event import Event
from ..image_processing.image_queue import ImageQueue
from ..telegram_bot import TelegramBot
from ..ws_server import WebSocketServer, WSMessage


class EventHandler:
    def __init__(
        self,
        telegram_bot: TelegramBot,
        ws_server: WebSocketServer,
        app_state: AppState,
        image_queue: ImageQueue,
        sinric_pro_client: SinricPro,
    ):
        self.telegram_bot = telegram_bot
        self.ws_server = ws_server
        self.app_state = app_state
        self.image_queue = image_queue
        self.sinric_pro_client = sinric_pro_client
        self.logger = logging.getLogger(__name__)

    async def handle_ap_state_change(self, event: Event):
        if event.origin == "esp":
            device = event.data["device"]
            new_state_str = event.data["state"]

            state_enum_class = getattr(self.app_state, f"{device}_state").__class__
            new_state = state_enum_class(new_state_str)
            setattr(self.app_state, f"{device}_state", new_state)

            if not self.app_state.ap_sent:
                if new_state == GateState.OPEN:
                    await self.telegram_bot.send_message("🚧 Gate is now open.")
                elif new_state == GateState.CLOSED:
                    await self.telegram_bot.send_message("🚧 Gate is now closed.")
                elif new_state == LightState.ON:
                    await self.telegram_bot.send_message("💡 Light is now on.")
                elif new_state == LightState.OFF:
                    await self.telegram_bot.send_message("💡 Light is now off.")

            if device == "gate":
                self.sinric_pro_client.event_handler.raise_event(
                    Config.GATE_ID,
                    SinricProConstants.SET_MODE,
                    data={
                        SinricProConstants.MODE: SinricProConstants.OPEN
                        if new_state == GateState.OPEN
                        else SinricProConstants.CLOSE,
                    },
                )

            elif device == "light":
                self.sinric_pro_client.event_handler.raise_event(
                    Config.LIGHT_ID,
                    SinricProConstants.SET_POWER_STATE,
                    data={
                        SinricProConstants.STATE: SinricProConstants.POWER_STATE_ON
                        if new_state == LightState.ON
                        else SinricProConstants.POWER_STATE_OFF
                    },
                )

        elif event.origin == "tg" or event.origin == "ghome":
            try:
                message = WSMessage(event_type="change_state", data=event.data)
                await self.ws_server.send("esp_s3", message)
            except Exception as e:
                self.logger.error(f"Error sending message to WebSocket: {e}")

    async def handle_motion_detected(self):
        await asyncio.wait_for(self.image_queue.dequeue_processed_image(), timeout=30)

        for interval in [3, 6, 9]:
            if await self._wait_for_detection_or_timeout(interval):
                self.app_state.person_detected = True
                self.logger.info("Person detected during retry interval.")  # Combined logs
                # Will be handled by handle_person_detected
                return

            try:
                await asyncio.wait_for(self.image_queue.dequeue_processed_image(), timeout=30)
            except asyncio.TimeoutError:
                break

            if self.image_queue.num_of_face_detected_images >= 2:
                break

        if self.image_queue.num_of_face_detected_images >= 2:
            self.app_state.person_detected = True
            self.logger.info(f"Person confirmed at the gate! Sending {self.image_queue.num_of_face_detected_images} images.")
            await self.handle_person_confirmed_with_face()
        else:
            self.logger.info("Motion detected, but no person confirmed.")

    async def _wait_for_detection_or_timeout(self, timeout_interval: int) -> bool:
        try:
            await asyncio.wait_for(
                self.app_state.person_detected_event.wait(),
                timeout=timeout_interval,
            )
            return True
        except asyncio.TimeoutError:
            await self.ws_server.send("esp_cam", WSMessage(event_type="capture_image", data={}))
            return False

    async def handle_person_detected(self):
        self.app_state.person_detected = True

        if await self.image_queue.dequeue_processed_image() and self.image_queue.num_of_face_detected_images >= 1:
            self.logger.info("Person confirmed at the gate!")
            await self.handle_person_confirmed_with_face()
        else:
            for interval in [5, 9, 13]:
                await asyncio.sleep(interval)
                await self.ws_server.send("esp_cam", WSMessage(event_type="capture_image", data={}))

                try:
                    await asyncio.wait_for(self.image_queue.dequeue_processed_image(), timeout=30)
                except asyncio.TimeoutError:
                    break

                if self.image_queue.num_of_face_detected_images >= 1:
                    self.logger.info("Person confirmed at the gate!")
                    await self.handle_person_confirmed_with_face()
            else:
                self.logger.info("Person confirmed, but no face detected.")
                await self.handle_person_confirmed_without_face()

    async def handle_person_confirmed_with_face(self):
        self.logger.info("Sending access control prompt and images to Telegram.")
        images = [image for image in await self.image_queue.get_face_detected_images()]
        [await image.save_to_disk() for image in images]
        await self.telegram_bot.send_images(images=[image.path for image in images])
        await self.telegram_bot.send_access_control_prompt()
        await self.image_queue.cleanup()

    async def handle_person_confirmed_without_face(self):
        self.logger.info("Sending access control prompt to Telegram.")
        await self.telegram_bot.send_access_control_prompt()
        await self.image_queue.cleanup()

    def handle_voice_message(self, event): ...
