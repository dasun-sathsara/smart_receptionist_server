import asyncio
import logging

from sinric import SinricPro, SinricProConstants

from ..app_state import AppState, GateState, LightState
from ..audio_processing.audio_helpers import get_latest_telegram_audio, save_audio_file
from ..audio_processing.audio_processor import AudioProcessor
from ..audio_processing.audio_queue import AudioQueue
from ..config import Config
from ..events.event import Event, Origin, EventType
from ..image_processing.image_processor import ImageProcessor
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
        audio_queue: AudioQueue,
        audio_processor: AudioProcessor,
    ):
        self.telegram_bot = telegram_bot
        self.ws_server = ws_server
        self.app_state = app_state
        self.image_queue = image_queue
        self.sinric_pro_client = sinric_pro_client
        self.audio_queue = audio_queue
        self.audio_processor = audio_processor
        self.logger = logging.getLogger(__name__)

    async def handle_audio_event(self, event: Event):
        action = event.data["action"]
        await self.ws_server.send("esp_s3", WSMessage(event_type=EventType.AUDIO, data={"action": action}))

    async def handle_recording_sent_event(self):
        pcm_data = await self.audio_queue.get_audio_data()

        if pcm_data:
            wav = await self.audio_processor.process_audio(pcm_data, "pcm")
            await self.telegram_bot.send_voice_message(wav)
            await save_audio_file(wav, "esp")
            await self.audio_queue.cleanup()
            self.logger.info("Audio recording from ESP processed and sent.")
        else:
            self.logger.warning("No audio data found in the queue.")

    async def handle_ap_state_change_event(self, event: Event):
        if event.origin == Origin.ESP:
            device = event.data["device"]
            new_state_str = event.data["state"]

            state_enum_class = getattr(self.app_state, f"{device}_state").__class__
            new_state = state_enum_class(new_state_str)
            setattr(self.app_state, f"{device}_state", new_state)

            if not self.app_state.home_control_prompt_sent:
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
                        SinricProConstants.MODE: (
                            SinricProConstants.OPEN if new_state == GateState.OPEN else SinricProConstants.CLOSE
                        ),
                    },
                )

            elif device == "light":
                self.sinric_pro_client.event_handler.raise_event(
                    Config.LIGHT_ID,
                    SinricProConstants.SET_POWER_STATE,
                    data={
                        SinricProConstants.STATE: (
                            SinricProConstants.POWER_STATE_ON
                            if new_state == LightState.ON
                            else SinricProConstants.POWER_STATE_OFF
                        )
                    },
                )

        elif event.origin == Origin.TG or event.origin == Origin.GHOME:
            try:
                message = WSMessage(event_type=EventType.CHANGE_STATE, data=event.data)
                await self.ws_server.send("esp_s3", message)
            except Exception as e:
                self.logger.error(f"Error sending message to WebSocket: {e}")

    async def handle_camera_event(self, event: Event):
        if event.data["action"] == "capture_image":
            await self.ws_server.send("esp_cam", WSMessage(event_type=EventType.CAPTURE_IMAGE, data={}))

    async def handle_motion_detected_event(self):
        self.app_state.motion_detected = True

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
            await self._handle_person_confirmed_with_face()
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
            await self.ws_server.send("esp_cam", WSMessage(event_type=EventType.CAPTURE_IMAGE, data={}))
            return False

    async def handle_person_detected_event(self):
        self.app_state.person_detected = True
        await self.telegram_bot.send_message("👤 Person detected at the gate!")

        if await self.image_queue.dequeue_processed_image() and self.image_queue.num_of_face_detected_images >= 1:
            self.logger.info("Person confirmed at the gate!")
            await self._handle_person_confirmed_with_face()
        else:
            for interval in [5, 9, 13]:
                await asyncio.sleep(interval)
                await self.ws_server.send("esp_cam", WSMessage(event_type=EventType.CAPTURE_IMAGE, data={}))

                try:
                    await asyncio.wait_for(self.image_queue.dequeue_processed_image(), timeout=30)
                except asyncio.TimeoutError:
                    break

                if self.image_queue.num_of_face_detected_images >= 1:
                    self.logger.info("Person confirmed at the gate!")
                    await self._handle_person_confirmed_with_face()
            else:
                self.logger.info("Person confirmed, but no face detected.")
                await self._handle_person_confirmed_without_face()

    async def _handle_person_confirmed_with_face(self):
        self.logger.info("Sending access control prompt and images to Telegram.")
        images = [image for image in await self.image_queue.get_face_detected_images()]
        [await image.save_to_disk() for image in images]
        await self.telegram_bot.send_images(images=[image.path for image in images])
        await self.telegram_bot.send_access_control_prompt()
        await self.image_queue.cleanup()

    async def handle_access_control_event(self, event: Event):
        action = event.data["action"]

        if action == "grant_access":
            await self.ws_server.send("esp_cam", WSMessage(event_type=EventType.GRANT_ACCESS, data={}))
        elif action == "deny_access":
            await self.ws_server.send("esp_cam", WSMessage(event_type=EventType.DENY_ACCESS, data={}))

    async def _handle_person_confirmed_without_face(self):
        self.logger.info("Sending access control prompt to Telegram.")
        await self.telegram_bot.send_access_control_prompt()
        await self.image_queue.cleanup()

    # Handling raw data
    async def handle_audio_data(self, event: Event):
        audio_data = event.data["audio"]

        if event.origin == Origin.ESP:
            await self.audio_queue.add_audio_chunk(audio_data)
        elif event.origin == Origin.TG:
            wav = await self.audio_processor.process_audio(audio_data, "opus")
            await save_audio_file(wav, "tg")
            self.logger.info("Audio file from telegram processed and saved.")

            latest_audio_path = await get_latest_telegram_audio()
            await self.ws_server.start_prefetching(latest_audio_path)

    async def handle_image_data(self, event: Event):
        if self.app_state.motion_detected:
            await self.image_queue.enqueue_image(event.data["image"])
        else:
            # Process the image and send the result to the Telegram bot
            image = ImageProcessor.apply_processing(event.data["image"])
            await self.telegram_bot.send_image(image)
            self.logger.info("Image processed and sent to Telegram.")
