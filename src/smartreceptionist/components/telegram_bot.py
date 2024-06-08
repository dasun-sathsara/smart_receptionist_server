import asyncio
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .app_state import AppState, LightState, GateState, ESPState
from .events.event import Event
from .events.event_listener import EventListener


class TelegramBot:
    def __init__(self, admin: int, event_listener: EventListener, app_state: AppState):
        self.admin = admin
        self.event_listener = event_listener
        self.app_state = app_state
        self.logger = logging.getLogger(__name__)

    async def build_action_prompt(self):
        keyboard = [
            [
                InlineKeyboardButton("Turn Light ON" if self.app_state.light_state == LightState.OFF else "Turn Light OFF",
                                     callback_data='ap_light_toggle'),
                InlineKeyboardButton("Open Gate" if self.app_state.gate_state == GateState.CLOSED else "Close Gate",
                                     callback_data='ap_gate_toggle')
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != self.admin:
            await update.message.reply_text("You are not authorized to use this bot.")
            return

        if not self.app_state.esp_s3_state == ESPState.CONNECTED or not self.app_state.esp_cam_state == ESPState.CONNECTED:
            await update.message.reply_text("Not all ESP devices are connected.")
            return

        # Delete existing prompt if there is one
        if "PROMPT_MESSAGE_ID" in context.chat_data:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id, message_id=context.chat_data["PROMPT_MESSAGE_ID"]
            )

        message = await update.message.reply_text("Select an action:", reply_markup=await self.build_action_prompt())
        context.chat_data["PROMPT_MESSAGE_ID"] = message.message_id

    async def _handle_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE, device: str, new_state: str):
        event = Event("change_state", "tg", {"device": device, "state": new_state})

        try:
            await self.event_listener.enqueue_event(event)
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(f"Changing {device} state to {new_state}...")

            event_name = f"{device}_state_changed_event"
            event_obj = getattr(self.app_state, event_name, None)
            if event_obj:  # Make sure the event exists before waiting for it.
                try:
                    await asyncio.wait_for(event_obj.wait(), timeout=5)
                    await update.callback_query.edit_message_text(f"{device.capitalize()} is now {new_state}")
                except asyncio.TimeoutError:
                    await update.callback_query.edit_message_text(f"Failed to change {device} state to {new_state}")
                    self.logger.error(f"Timeout waiting for {device} state change.")
                finally:
                    event_obj.clear()
            else:
                await update.callback_query.edit_message_text(f"Event for {device} not found.")
                self.logger.error(f"Event for {device} not found.")
        except Exception as e:
            self.logger.error(f"Error handling action: {e}")
            await update.callback_query.edit_message_text(f"An error occurred while processing the request.")

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        if query.data.startswith("ap_"):
            _, device, action = query.data.split("_")

            current_state = getattr(self.app_state, f"{device}_state")
            new_state = None

            if current_state.__class__ == LightState:
                new_state = "on" if action == "toggle" and current_state != LightState.ON else "off"
            elif current_state.__class__ == GateState:
                new_state = "open" if action == "toggle" and current_state != GateState.OPEN else "closed"

            await self._handle_action(update, context, device, new_state)
