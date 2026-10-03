"""Map button edges to cached cursor frames, keeping the hotspot stationary."""

import json
import os

PRESS_SECONDS = .06
RELEASE_SECONDS = .15
SCALES = (1.0, .975, .95, .925, .9)
ANGLES = (0, -3, -6, -9, -12)
MODES = ("tilt", "shrink")


def read_mode(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        mode = data.get("mode") if isinstance(data, dict) else None
        return mode if mode in MODES else "tilt"
    except (OSError, ValueError):
        return "tilt"


def save_mode(path, mode):
    if mode not in MODES:
        raise ValueError(mode)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps({"mode": mode}), encoding="utf-8")
    os.replace(temporary, path)


class ClickMotion:
    def __init__(self, press_ms=60, release_ms=150):
        if type(press_ms) is not int or not 40 <= press_ms <= 200:
            raise ValueError("Invalid press duration")
        if type(release_ms) is not int or not 80 <= release_ms <= 400:
            raise ValueError("Invalid release duration")
        self._press, self._release = press_ms / 1000, release_ms / 1000
        self.down = False
        self.presses = 0
        self._source = self._target = 1.0
        self._since = 0.0
        self._duration = self._press

    def _scale(self, now):
        progress = min(1.0, max(0.0, (now - self._since) / self._duration))
        # A slower release keeps the last visible step near the 150 ms endpoint.
        eased = 1 - (1 - progress) ** 3 if self.down else progress * (1 + progress) / 2
        return self._source + (self._target - self._source) * eased

    def update(self, down, now):
        scale = self._scale(now)
        if down != self.down:
            self.down = down
            self._source, self._since = scale, now
            self._target = SCALES[-1] if down else SCALES[0]
            self._duration = self._press if down else self._release
            if down:
                self.presses += 1
        return min(4, max(0, round((1 - scale) / .025)))


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)
