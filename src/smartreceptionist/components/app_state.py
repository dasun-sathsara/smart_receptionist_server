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


class AppState:
    def get_light_state(self):
        pass

    def get_gate_state(self):
        pass

    def __init__(self):
        self.gate: GateState = GateState.CLOSED
        self.light: LightState = LightState.OFF
        self.esp_s3: ESPState = ESPState.DISCONNECTED
        self.esp_cam: ESPState = ESPState.DISCONNECTED

    def set_esps_state(self, esp_name: str, state: ESPState):
        if esp_name == 'esp_s3':
            self.esp_s3 = ESPState(state)
        elif esp_name == 'esp_cam':
            self.esp_cam = ESPState(state)

    def esp_s3_connected(self):
        return self.esp_s3 == ESPState.CONNECTED

    def esp_cam_connected(self):
        return self.esp_cam == ESPState.CONNECTED
