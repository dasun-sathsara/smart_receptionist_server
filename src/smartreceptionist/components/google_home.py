import asyncio
import logging

from .events.event import Event
from .events.event_listener import EventListener


class GoogleHome:
    def __init__(self, event_listener: EventListener):
        self.logger = logging.getLogger(__name__)
        self.event_listener = event_listener

    # Gate
    def handle_set_mode(self, device_id, state, instance_id):
        asyncio.ensure_future(
            self.event_listener.enqueue_event(
                Event("change_state", "ghome", {"device": "gate", "state": "open" if state == "Open" else "closed"})
            )
        )

        return True, state, instance_id

    # Light
    def handle_power_state(self, device_id, state):
        asyncio.ensure_future(
            self.event_listener.enqueue_event(Event("change_state", "ghome", {"device": "light", "state": state.lower()}))
        )

        return True, state
