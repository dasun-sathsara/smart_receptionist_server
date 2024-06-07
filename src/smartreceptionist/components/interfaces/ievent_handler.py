from abc import ABC, abstractmethod


class IEventHandler(ABC):
    @abstractmethod
    async def process_events(self, telegram_bot, app_state, ws_server):
        pass

    @abstractmethod
    async def enqueue_event(self, event):
        pass
