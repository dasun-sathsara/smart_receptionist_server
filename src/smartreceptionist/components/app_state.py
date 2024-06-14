import asyncio
from dataclasses import dataclass, field
from enum import Enum


class GateState(Enum):
    OPEN = "open"
    CLOSED = "closed"


class LightState(Enum):
    ON = "on"
    OFF = "off"


class ESPState(Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


@dataclass
class AppState:
    gate_state: GateState = GateState.CLOSED
    gate_state_changed_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)

    light_state: LightState = LightState.OFF
    light_state_changed_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)

    esp_s3_state: ESPState = ESPState.DISCONNECTED
    esp_s3_state_changed_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)

    esp_cam_state: ESPState = ESPState.DISCONNECTED
    esp_cam_state_changed_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)

    person_detected: bool = False
    person_detected_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)

    ap_sent: bool = False  # Action prompt sent to Telegram

    def __setattr__(self, name: str, value: any) -> None:
        """Trigger an event when an attribute is changed."""

        super().__setattr__(name, value)

        if name == "person_detected":
            event_name = name + "_event"
        else:
            event_name = name + "_changed_event"

        if event_name in self.__dict__:  # Check if it's a monitored attribute
            self.__dict__[event_name].set()
