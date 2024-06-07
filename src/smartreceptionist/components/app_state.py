from enum import Enum

from .interfaces.iapp_state import IAppState


class GateState(Enum):
    OPEN = "open"
    CLOSED = "closed"


class LightState(Enum):
    ON = "on"
    OFF = "off"


class AppState(IAppState):
    def get_light_state(self):
        pass

    def get_gate_state(self):
        pass

    def __init__(self):
        self.gate: GateState = GateState.CLOSED
        self.light: LightState = LightState.OFF
