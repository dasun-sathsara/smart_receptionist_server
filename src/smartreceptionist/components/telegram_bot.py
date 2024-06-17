import asyncio
import logging
from enum import Enum
from pathlib import Path

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Update
from telegram.error import NetworkError, TelegramError, TimedOut
from telegram.ext import ContextTypes

from .app_state import AppState, ESPState, GateState, LightState
from .events.event import Event
from .events.event_listener import EventListener


class Actions(str, Enum):
    LIGHT_TOGGLE = "ap_light_toggle"
    GATE_TOGGLE = "ap_gate_toggle"
    ACCESS_ALLOW = "acp_access_allow"
    ACCESS_DENY = "acp_access_deny"


class TelegramBot:
    def __init__(self, admin_user_id: int, event_listener: EventListener, app_state: AppState):
        self.admin_user_id = admin_user_id
        self.event_listener = event_listener
        self.app_state = app_state
        self.logger = logging.getLogger(__name__)
        self.bot: Bot | None = None
        self.prompt_message_ids = {}

    async def _build_action_prompt(self):
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

            if (
                not self.app_state.esp_s3_state == ESPState.CONNECTED
                or not self.app_state.esp_cam_state == ESPState.CONNECTED
            ):
                await update.message.reply_text(
                    "🔌 ESP Devices: Not all ESP devices are connected. Please check their status."
                )
                return

            await update.message.reply_text("🤖 Smart Receptionist Bot started.")
        except TelegramError as e:
            self.logger.error(f"Telegram error during /start: {e}")
            await update.message.reply_text("An error occurred. Please try again later.")
        except Exception as e:  # Catch unexpected errors
            self.logger.exception(f"Unexpected error during /start: {e}")
            await update.message.reply_text("An error occurred. Please try again later.")

    async def handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            voice_file = await context.bot.get_file(update.message.voice.file_id)
            self.logger.info(f"Received voice message: {voice_file.file_id}")
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

    async def handle_action_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if "ap" in self.prompt_message_ids:
                try:
                    await context.bot.delete_message(
                        chat_id=update.effective_chat.id,
                        message_id=self.prompt_message_ids["ap"],
                    )
                    self.prompt_message_ids.pop("ap")
                except TelegramError as e:
                    self.logger.error(f"Error deleting previous prompt: {e}")

            message = await update.message.reply_text(
                "🏡 Home Control Panel\n\nPlease choose an action:", reply_markup=await self._build_action_prompt()
            )
            self.prompt_message_ids["ap"] = message.message_id
        except TelegramError as e:
            self.logger.error(f"Telegram error during handle_action_prompt: {e}")
            await update.message.reply_text("An error occurred. Please try again later.")
        except Exception as e:
            self.logger.exception(f"Unexpected error during handle_action_prompt: {e}")
            await update.message.reply_text("An error occurred. Please try again later.")

    async def _handle_action_prompt_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            self.app_state.ap_sent = True
            query = update.callback_query
            _, device, action = query.data.split("_")

            current_state = getattr(self.app_state, f"{device}_state")
            new_state = None

            if current_state.__class__ == LightState:
                new_state = "on" if action == "toggle" and current_state != LightState.ON else "off"
            elif current_state.__class__ == GateState:
                new_state = "open" if action == "toggle" and current_state != GateState.OPEN else "closed"

            event = Event("change_state", "tg", {"device": device, "state": new_state})

            await self.event_listener.enqueue_event(event)
            await update.callback_query.answer("🔄 Processing...")
            await update.callback_query.edit_message_text(f"🔄 Changing {device} state to {new_state}...")

            event_name = f"{device}_state_changed_event"
            event_obj = getattr(self.app_state, event_name, None)
            if event_obj:
                try:
                    await asyncio.wait_for(event_obj.wait(), timeout=10)
                    await update.callback_query.edit_message_text(f"✅ {device.capitalize()} is now {new_state}")
                except asyncio.TimeoutError:
                    await update.callback_query.edit_message_text(
                        f"❌ Failed to change {device} state to {new_state}. Please try again later."
                    )
                    self.logger.error(f"Timeout waiting for {device} state change.")
                finally:
                    event_obj.clear()
            else:
                await update.callback_query.edit_message_text(f"🤔 Event for {device} not found.")
                self.logger.error(f"Event for {device} not found.")
        except Exception as e:
            self.logger.error(f"Error handling action: {e}")
            await update.callback_query.edit_message_text(
                "⚠️ An error occurred while processing the request. Please try again later."
            )
        finally:
            self.app_state.ap_sent = False

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            query = update.callback_query
            if query.data.startswith("ap_"):
                await self._handle_action_prompt_response(update, context)
            elif query.data.startswith("acp_"):
                await self._handle_access_control_response(update, context)
        except TelegramError as e:
            self.logger.error(f"Telegram error during handle_callback_query: {e}")
            await update.callback_query.answer("An error occurred. Please try again.")
        except Exception as e:
            self.logger.exception(f"Unexpected error during handle_callback_query: {e}")
            await update.callback_query.answer("An error occurred. Please try again.")

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

    @staticmethod
    async def _build_access_control_prompt():
        keyboard = [
            [
                InlineKeyboardButton("✅ Allow Access", callback_data=Actions.ACCESS_ALLOW),
                InlineKeyboardButton("❌ Deny Access", callback_data=Actions.ACCESS_DENY),
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def send_access_control_prompt(self):
        if not self.bot:
            self.logger.error("Bot instance not found.")
            return

        try:
            if "acp" in self.prompt_message_ids:
                try:
                    await self.bot.delete_message(
                        chat_id=self.admin_user_id,
                        message_id=self.prompt_message_ids["acp"],
                    )
                    self.prompt_message_ids.pop("acp")
                except TelegramError as e:
                    self.logger.error(f"Error deleting previous access prompt: {e}")

            message = await self.bot.send_message(
                self.admin_user_id,
                "🚶‍♂️ Access Request: Allow or deny access?",
                reply_markup=await self._build_access_control_prompt(),
            )

            self.logger.info("Access control prompt sent.")
            self.prompt_message_ids["acp"] = message.message_id
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

    async def _handle_access_control_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            query = update.callback_query

            if query.data == Actions.ACCESS_ALLOW:
                await query.answer("✅ Access granted.")
                await query.edit_message_text("✅ Access granted.")
                await self.event_listener.enqueue_event(Event("access_granted", "tg", {}))
            elif query.data == Actions.ACCESS_DENY:
                await query.answer("❌ Access denied.")
                await query.edit_message_text("❌ Access denied.")
                await self.event_listener.enqueue_event(Event("access_denied", "tg", {}))
        except TelegramError as e:
            self.logger.error(f"Telegram error during _handle_access_control_response: {e}")
            await update.callback_query.answer("An error occurred. Please try again.")
        except Exception as e:
            self.logger.exception(f"Unexpected error during _handle_access_control_response: {e}")
            await update.callback_query.answer("An error occurred. Please try again.")
