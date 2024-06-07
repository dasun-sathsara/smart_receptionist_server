from telegram import Update
from telegram.ext import (
    ContextTypes,
)

from .app_state import AppState
from .events.event_listener import EventListener


class TelegramBot:
    def __init__(self, admin: int, event_listener: EventListener, app_state: AppState):
        self.context = None
        self.event_listener = event_listener
        self.app_state = app_state
        self.admin = admin

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user.id == self.admin:
            await update.message.reply_text("You are not authorized to use this bot.")
            return

        if not self.app_state.esp_s3_connected():
            await update.message.reply_text("ESP S3 is not connected.")
            return

        if not self.app_state.esp_cam_connected():
            await update.message.reply_text("ESP CAM is not connected.")
            return

        await update.message.reply_text("Welcome to Smart Receptionist Bot!")
