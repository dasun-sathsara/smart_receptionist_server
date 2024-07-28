from dataclasses import dataclass
from enum import Enum


class EventType(Enum):
    CHANGE_STATE = "change_state"
    MOTION_DETECTED = "motion_detected"
    PERSON_DETECTED = "person_detected"
    AUDIO = "audio"
    CAMERA = "camera"
    ACCESS_CONTROL = "access_control"
    IMAGE_DATA = "image_data"
    AUDIO_DATA = "audio_data"
    INIT = "init"
    RECORDING_SENT = "recording_sent"
    CAPTURE_IMAGE = "capture_image"
    GRANT_ACCESS = "grant_access"
    DENY_ACCESS = "deny_access"
    RESET_DEVICE = "reset_device"
    ENROLL_FINGERPRINT = "enroll_fingerprint"
    FINGERPRINT_ENROLLED = "fingerprint_enrolled"
    FINGERPRINT_ENROLLMENT_FAILED = "fingerprint_enrollment_failed"
    MOTION_ENABLE = "motion_enable"
    CHANGE_SERVER = "change_server"


class Origin(Enum):
    ESP = "esp"
    TG = "tg"
    GHOME = "ghome"


@dataclass
class Event:
    event_type: EventType
    origin: Origin
    data: dict

    def __str__(self):
        return f"{self.event_type.name}"
