import asyncio
import logging
from enum import Enum
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Bot
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from .app_state import AppState, LightState, GateState, ESPState
from .events.event import Event
from .events.event_listener import EventListener


class Actions(str, Enum):
    LIGHT_TOGGLE = "ap_light_toggle"
    GATE_TOGGLE = "ap_gate_toggle"
    ACCESS_ALLOW = "acp_access_allow"
    ACCESS_DENY = "acp_access_deny"


class TelegramBot:
    def __init__(
        self,
        admin_user_id: int,
        event_listener: EventListener,
        app_state: AppState,
    ):
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
                    "🚪 Gate OPEN" if self.app_state.gate_state == GateState.CLOSED else "🚪 Gate CLOSED",
                    callback_data=Actions.GATE_TOGGLE,
                ),
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Save the application instance
        self.bot = context.bot

        user_id = update.effective_user.id
        if user_id != self.admin_user_id:
            await update.message.reply_text("⛔ Unauthorized: You are not authorized to use this bot.")
            return

        if not self.app_state.esp_s3_state == ESPState.CONNECTED or not self.app_state.esp_cam_state == ESPState.CONNECTED:
            await update.message.reply_text("🔌 ESP Devices: Not all ESP devices are connected. Please check their status.")
            return

        await update.message.reply_text("🤖 Smart Receptionist Bot started.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message.text == "start":
            await self.start(update, context)
        elif update.message.text == "ap":
            await self.handle_action_prompt(update, context)

    async def handle_action_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Delete existing prompt if there is one
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

    async def _handle_action_prompt_response(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
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

        try:
            await self.event_listener.enqueue_event(event)
            await update.callback_query.answer("🔄 Processing...")
            await update.callback_query.edit_message_text(f"🔄 Changing {device} state to {new_state}...")

            event_name = f"{device}_state_changed_event"
            event_obj = getattr(self.app_state, event_name, None)
            if event_obj:
                try:
                    await asyncio.wait_for(event_obj.wait(), timeout=10)  # Wait for the event to be set
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
        query = update.callback_query
        if query.data.startswith("ap_"):
            await self._handle_action_prompt_response(update, context)
        elif query.data.startswith("acp_"):
            await self._handle_access_control_response(update, context)

    async def send_images(self, images: list[Path]):
        if not self.bot:
            self.logger.error("Bot instance not found.")
            return

        media_group = []
        for photo_path in images:
            if photo_path.exists():
                with open(photo_path, "rb") as photo_file:
                    media_group.append(InputMediaPhoto(media=photo_file))
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

    async def _build_access_control_prompt(self):
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

    async def send_message(self, message: str):
        if not self.bot:
            self.logger.error("Bot instance not found.")
            return

        await self.bot.send_message(self.admin_user_id, message)
        self.logger.info(f"Message sent: {message}")

    async def _handle_access_control_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query

        if query.data == Actions.ACCESS_ALLOW:
            await query.answer("✅ Access granted.")
            await query.edit_message_text("✅ Access granted.")
            await self.event_listener.enqueue_event(Event("access_granted", "tg", {}))
        elif query.data == Actions.ACCESS_DENY:
            await query.answer("❌ Access denied.")
            await query.edit_message_text("❌ Access denied.")
            await self.event_listener.enqueue_event(Event("access_denied", "tg", {}))
