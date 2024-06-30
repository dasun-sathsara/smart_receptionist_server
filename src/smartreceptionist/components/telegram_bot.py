import asyncio
import logging
from enum import Enum
from pathlib import Path

from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Update,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.error import NetworkError, TelegramError, TimedOut
from telegram.ext import ContextTypes

from .app_state import AppState, GateState, LightState
from .events.event import Event
from .events.event_listener import EventListener


class Actions(str, Enum):
    LIGHT_TOGGLE = "light_toggle"
    GATE_TOGGLE = "gate_toggle"
    ACCESS_ALLOW = "access_allow"
    ACCESS_DENY = "access_deny"
    START_RECORDING = "start_recording"
    STOP_RECORDING = "stop_recording"
    START_PLAYBACK = "start_playback"
    STOP_PLAYBACK = "stop_playback"
    CAPTURE_IMAGE = "capture_image"


class Menus(str, Enum):
    MAIN_MENU = "main"
    HOME_CONTROL = "home_control"
    CAMERA_CONTROL = "camera_control"
    AUDIO_CONTROL = "audio_control"


AUDIO_ACTIONS = (Actions.START_RECORDING, Actions.STOP_RECORDING, Actions.START_PLAYBACK, Actions.STOP_PLAYBACK)
CAMERA_ACTIONS = (Actions.CAPTURE_IMAGE,)
ACCESS_CONTROL_ACTIONS = (Actions.ACCESS_ALLOW, Actions.ACCESS_DENY)
HOME_CONTROL_ACTIONS = (Actions.LIGHT_TOGGLE, Actions.GATE_TOGGLE)
MENU_ACTIONS = (Menus.MAIN_MENU, Menus.HOME_CONTROL, Menus.CAMERA_CONTROL, Menus.AUDIO_CONTROL)


class TelegramBot:
    def __init__(self, admin_user_id: int, event_listener: EventListener, app_state: AppState):
        self.admin_user_id = admin_user_id
        self.event_listener = event_listener
        self.app_state = app_state
        self.logger = logging.getLogger(__name__)
        self.bot: Bot | None = None
        self.current_menu_message = None
        self.user_start_message = None
        self.user_menu_message = None

    @staticmethod
    async def _build_custom_keyboard():
        keyboard = [
            [KeyboardButton("🏠 Home Control"), KeyboardButton("📹 Camera Control")],
            [KeyboardButton("🎙️ Audio Control"), KeyboardButton("🔄 Start")],
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    @staticmethod
    async def _build_main_menu():
        keyboard = [
            [
                InlineKeyboardButton("🏠 Home Control", callback_data="home_control"),
                InlineKeyboardButton("📹 Camera Control", callback_data="camera_control"),
            ],
            [InlineKeyboardButton("🎙️ Audio Control", callback_data=Menus.AUDIO_CONTROL)],
        ]
        return InlineKeyboardMarkup(keyboard)

    async def _build_home_control_menu(self):
        keyboard = [
            [
                InlineKeyboardButton(
                    "💡 Light ON" if self.app_state.light_state == LightState.OFF else "💡 Light OFF",
                    callback_data=Actions.LIGHT_TOGGLE,
                ),
                InlineKeyboardButton(
                    "🚪 Gate OPEN" if self.app_state.gate_state == GateState.CLOSED else "🚪 Gate CLOSE",
                    callback_data=Actions.GATE_TOGGLE,
                ),
            ],
            [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data=Menus.MAIN_MENU)],
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    async def _build_camera_control_menu():
        keyboard = [
            [InlineKeyboardButton("📸 Capture Image", callback_data=Actions.CAPTURE_IMAGE)],
            [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data=Menus.MAIN_MENU)],
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    async def _build_audio_control_menu():
        keyboard = [
            [
                InlineKeyboardButton("🔴 Start Recording", callback_data=Actions.START_RECORDING),
                InlineKeyboardButton("⏹️ Stop Recording", callback_data=Actions.STOP_RECORDING),
            ],
            [
                InlineKeyboardButton("▶️ Start Playback", callback_data=Actions.START_PLAYBACK),
                InlineKeyboardButton("⏹️ Stop Playback", callback_data=Actions.STOP_PLAYBACK),
            ],
            [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data=Menus.MAIN_MENU)],
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    async def _build_access_control_prompt():
        keyboard = [
            [
                InlineKeyboardButton("✅ Allow Access", callback_data=Actions.ACCESS_ALLOW),
                InlineKeyboardButton("❌ Deny Access", callback_data=Actions.ACCESS_DENY),
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            self.bot = context.bot
            user_id = update.effective_user.id
            if user_id != self.admin_user_id:
                await update.message.reply_text("⛔ Unauthorized: You are not authorized to use this bot.")
                return

            await self.delete_user_sent_messages(context)
            self.user_start_message = update.message.message_id
            custom_keyboard = await self._build_custom_keyboard()
            await update.message.reply_text("Welcome to Smart Home Control Center", reply_markup=custom_keyboard)
            await self.send_main_menu(update, context)
        except TelegramError as e:
            self.logger.error(f"Telegram error during /start: {e}")
            await update.message.reply_text("An error occurred. Please try again later.")
        except Exception as e:
            self.logger.exception(f"Unexpected error during /start: {e}")
            await update.message.reply_text("An error occurred. Please try again later.")

    async def handle_unrecognized_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            message_text = update.message.text
            if message_text == "🏠 Home Control":
                await self.send_home_control_menu(update, context)
            elif message_text == "📹 Camera Control":
                await self.send_camera_control_menu(update, context)
            elif message_text == "🎙️ Audio Control":
                await self.send_audio_control_menu(update, context)
            elif message_text == "🔄 Start":
                await self.start(update, context)
            else:
                await update.message.reply_text(
                    "🤔 Sorry, I didn't quite get that. Please use the custom keyboard or /start command."
                )
        except TelegramError as e:
            self.logger.error(f"Telegram error during handle_unrecognized_message: {e}")

    async def delete_user_sent_messages(self, context: ContextTypes.DEFAULT_TYPE):
        if self.user_start_message:
            try:
                await context.bot.delete_message(chat_id=self.admin_user_id, message_id=self.user_start_message)
            except TelegramError:
                pass
        if self.user_menu_message:
            try:
                await context.bot.delete_message(chat_id=self.admin_user_id, message_id=self.user_menu_message)
            except TelegramError:
                pass

    async def send_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.delete_user_sent_messages(context)
        self.user_menu_message = update.message.message_id
        if self.current_menu_message:
            try:
                await context.bot.delete_message(chat_id=self.admin_user_id, message_id=self.current_menu_message)
            except TelegramError:
                pass
        menu_message = await update.message.reply_text("🏡 Smart Home Control Center", reply_markup=await self._build_main_menu())
        self.current_menu_message = menu_message.message_id

    async def send_home_control_menu(self, update: Update, _: ContextTypes.DEFAULT_TYPE):
        menu_message = await update.message.reply_text(
            "🏠 Home Control Panel", reply_markup=await self._build_home_control_menu()
        )
        self.current_menu_message = menu_message.message_id

    async def send_camera_control_menu(self, update: Update, _: ContextTypes.DEFAULT_TYPE):
        menu_message = await update.message.reply_text(
            "📹 Camera Control Panel", reply_markup=await self._build_camera_control_menu()
        )
        self.current_menu_message = menu_message.message_id

    async def send_audio_control_menu(self, update: Update, _: ContextTypes.DEFAULT_TYPE):
        menu_message = await update.message.reply_text(
            "🎙️ Audio Control Panel", reply_markup=await self._build_audio_control_menu()
        )
        self.current_menu_message = menu_message.message_id

    async def handle_callback_query(self, update: Update, _: ContextTypes.DEFAULT_TYPE):
        try:
            query = update.callback_query
            if query.data in MENU_ACTIONS:
                await self._handle_menu_response(query)
            elif query.data in HOME_CONTROL_ACTIONS:
                await self._handle_home_control_prompt_response(query)
            elif query.data in CAMERA_ACTIONS:
                await self._handle_camera_control_prompt_response(query)
            elif query.data in AUDIO_ACTIONS:
                await self._handle_audio_control_prompt_response(query)
            elif query.data in ACCESS_CONTROL_ACTIONS:
                await self._handle_access_control_prompt_response(query)
        except TelegramError as e:
            self.logger.error(f"Telegram error during handle_callback_query: {e}")
            await update.callback_query.answer("An error occurred. Please try again.")
        except Exception as e:
            self.logger.exception(f"Unexpected error during handle_callback_query: {e}")
            await update.callback_query.answer("An error occurred. Please try again.")

    async def _handle_menu_response(self, query: CallbackQuery):
        await query.answer()

        if query.data == Menus.MAIN_MENU:
            await query.edit_message_text("🏡 Smart Home Control Center", reply_markup=await self._build_main_menu())
        elif query.data == Menus.HOME_CONTROL:
            await query.edit_message_text("🏠 Home Control Panel", reply_markup=await self._build_home_control_menu())
        elif query.data == Menus.CAMERA_CONTROL:
            await query.edit_message_text("📹 Camera Control Panel", reply_markup=await self._build_camera_control_menu())
        elif query.data == Menus.AUDIO_CONTROL:
            await query.edit_message_text("🎙️ Audio Control Panel", reply_markup=await self._build_audio_control_menu())

        self.current_menu_message = query.message.message_id

    async def _handle_audio_control_prompt_response(self, query: CallbackQuery):
        if query.data == Actions.START_RECORDING:
            await self.event_listener.enqueue_event(Event("audio", "tg", {"action": "start_recording"}))
            await query.edit_message_text("🔴 Recording started", reply_markup=await self._build_audio_control_menu())
        elif query.data == Actions.STOP_RECORDING:
            await self.event_listener.enqueue_event(Event("audio", "tg", {"action": "stop_recording"}))
            await query.edit_message_text("⏹️ Recording stopped", reply_markup=await self._build_audio_control_menu())
        elif query.data == Actions.START_PLAYBACK:
            await self.event_listener.enqueue_event(Event("audio", "tg", {"action": "start_playing"}))
            await query.edit_message_text("▶️ Playback started", reply_markup=await self._build_audio_control_menu())
        elif query.data == Actions.STOP_PLAYBACK:
            await self.event_listener.enqueue_event(Event("audio", "tg", {"action": "stop_playing"}))
            await query.edit_message_text("⏹️ Playback stopped", reply_markup=await self._build_audio_control_menu())

    async def _handle_camera_control_prompt_response(self, query: CallbackQuery):
        if query.data == Actions.CAPTURE_IMAGE:
            await query.answer("📸 Capturing image...")
            await query.edit_message_text("📸 Capturing image...")
            await self.event_listener.enqueue_event(Event("camera", "tg", {"action": "capture_image"}))

    async def _handle_home_control_prompt_response(self, query: CallbackQuery):
        try:
            self.app_state.home_control_prompt_sent = True

            device, action = query.data.split("_")

            current_state = getattr(self.app_state, f"{device}_state")
            new_state = None

            if current_state.__class__ == LightState:
                new_state = "on" if action == "toggle" and current_state != LightState.ON else "off"
            elif current_state.__class__ == GateState:
                new_state = "open" if action == "toggle" and current_state != GateState.OPEN else "closed"

            event = Event("change_state", "tg", {"device": device, "state": new_state})
            await self.event_listener.enqueue_event(event)

            await query.answer("🔄 Processing...")
            await query.edit_message_text(f"🔄 Changing {device} state to {new_state}...")

            event_name = f"{device}_state_changed_event"
            event_obj = getattr(self.app_state, event_name, None)
            if event_obj:
                try:
                    await asyncio.wait_for(event_obj.wait(), timeout=20)
                    await query.edit_message_text(
                        f"✅ {device.capitalize()} is now {new_state}", reply_markup=await self._build_home_control_menu()
                    )
                except asyncio.TimeoutError:
                    await query.edit_message_text(
                        f"❌ Failed to change {device} state to {new_state}. Please try again later.",
                        reply_markup=await self._build_home_control_menu(),
                    )
                    self.logger.error(f"Timeout waiting for {device} state change.")
                finally:
                    event_obj.clear()
            else:
                await query.edit_message_text(
                    f"🤔 Event for {device} not found.", reply_markup=await self._build_home_control_menu()
                )
                self.logger.error(f"Event for {device} not found.")

        except Exception as e:
            self.logger.error(f"Error handling action: {e}")
            await query.edit_message_text(
                "⚠️ An error occurred while processing the request. Please try again later.",
                reply_markup=await self._build_home_control_menu(),
            )

        finally:
            self.app_state.home_control_prompt_sent = False

    async def _handle_access_control_prompt_response(self, query: CallbackQuery):
        try:
            if query.data == Actions.ACCESS_ALLOW:
                await query.answer("✅ Granting access...")
                await query.edit_message_text("✅ Access granted.")
                await self.event_listener.enqueue_event(Event("access_control", "tg", {"action": "granted"}))
            elif query.data == Actions.ACCESS_DENY:
                await query.answer("❌ Denying access...")
                await query.edit_message_text("❌ Access denied.")
                await self.event_listener.enqueue_event(Event("access_control", "tg", {"action": "denied"}))

        except TelegramError as e:
            self.logger.error(f"Telegram error during _handle_access_control_response: {e}")
            await query.answer("An error occurred. Please try again.")

        except Exception as e:
            self.logger.exception(f"Unexpected error during _handle_access_control_response: {e}")
            await query.answer("An error occurred. Please try again.")

    async def handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            voice_file = await context.bot.get_file(update.message.voice.file_id)
            self.logger.info("Received voice message.")
            voice_bytes = await voice_file.download_as_bytearray()
            await self.event_listener.enqueue_event(Event("audio_data", "tg", {"audio": voice_bytes}))

        except (TelegramError, TimedOut, NetworkError) as e:
            error_message = f"Error getting or downloading voice message: {e}"
            self.logger.error(error_message)
            await update.message.reply_text("Sorry, there was an issue processing your voice message.")

        except Exception as e:
            error_message = f"Unexpected error handling voice message: {e}"
            self.logger.exception(error_message)
            await update.message.reply_text("An error occurred. Please try again later.")

    async def send_images(self, images: list[Path]):
        if not self.bot:
            self.logger.error("Bot instance not found.")
            return

        media_group = []
        for photo_path in images:
            if photo_path.exists():
                try:
                    with open(photo_path, "rb") as photo_file:
                        media_group.append(InputMediaPhoto(media=photo_file))
                except (OSError, IOError) as e:
                    self.logger.error(f"Error reading image file: {e}")
            else:
                self.logger.error(f"Image not found at path: {photo_path}")

        if media_group:  # Send only if there are valid images
            try:
                await self.bot.send_media_group(chat_id=self.admin_user_id, media=media_group)
                self.logger.info("Images sent successfully.")

            except TelegramError as e:
                self.logger.error(f"Error sending images: {e}")
        else:
            self.logger.error("No valid images to send.")

    async def send_image(self, image: bytes):
        if not self.bot:
            self.logger.error("Bot instance not found.")
            return

        try:
            await self.bot.send_photo(self.admin_user_id, photo=image)
            self.logger.info("Image sent successfully.")

        except TelegramError as e:
            self.logger.error(f"Error sending image: {e}")

    async def send_access_control_prompt(self):
        if not self.bot:
            self.logger.error("Bot instance not found.")
            return

        try:
            await self.bot.send_message(
                self.admin_user_id,
                "🚶‍♂️ Access Request: Allow or deny access?",
                reply_markup=await self._build_access_control_prompt(),
            )
            self.logger.info("Access control prompt sent.")
        except TelegramError as e:
            self.logger.error(f"Error sending access control prompt: {e}")

    async def send_message(self, message: str):
        if not self.bot:
            self.logger.error("Bot instance not found.")
            return

        try:
            await self.bot.send_message(self.admin_user_id, message)
            self.logger.info(f"Message sent: {message}")

        except TelegramError as e:
            self.logger.error(f"Error sending message: {e}")

    async def send_voice_message(self, voice_bytes: bytes):
        if not self.bot:
            self.logger.error("Bot instance not found.")
            return

        try:
            await self.bot.send_voice(self.admin_user_id, voice=voice_bytes)
            self.logger.info("Voice message sent.")

        except TelegramError as e:
            self.logger.error(f"Error sending voice message: {e}")
            raise
