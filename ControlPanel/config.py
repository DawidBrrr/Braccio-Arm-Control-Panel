from __future__ import annotations

from dataclasses import dataclass

DEFAULT_PORT = "COM3"
BAUD_RATE = 115200
SLIDER_DEBOUNCE_MS = 150


@dataclass(frozen=True)
class ServoConfig:
    label: str
    minimum: int
    maximum: int
    initial: int


SERVO_CONFIG: dict[str, ServoConfig] = {
    "m1": ServoConfig("Base", 0, 270, 90),
    "m2": ServoConfig("Shoulder", 15, 165, 45),
    "m3": ServoConfig("Elbow", 0, 180, 180),
    "m4": ServoConfig("Wrist Vertical", 0, 180, 170),
    "m5": ServoConfig("Wrist Rotation", 0, 180, 90),
    "m6": ServoConfig("Gripper", 10, 110, 73),
}

ARM_LINKS_MM = {
    "shoulder": 95.0,
    "elbow": 110.0,
    "wrist": 80.0,
}


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
