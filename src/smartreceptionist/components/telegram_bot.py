from telegram import Update
from telegram.ext import (
    ContextTypes,
)

from .interfaces.iapp_state import IAppState
from .interfaces.ievent_handler import IEventHandler
from .event import Event


class TelegramBot:
    def __init__(self, admin: int, event_listener: IEventHandler, app_state: IAppState):
        self.context = None
        self.event_listener = event_listener
        self.app_state = app_state
        self.admin = admin

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Send a welcome message
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Welcome to Smart Receptionist!")

        # Signal that the user has started the bot
        await self.event_listener.enqueue_event(Event("start", update.effective_user.id))
