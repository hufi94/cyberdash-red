#!/usr/bin/env python3
"""Reusable 220-frame Civic player for the Cyberdash Red Kivy dashboard."""

import re
import time
from pathlib import Path

from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.metrics import dp
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label


ROTATION_SECONDS = 12.0
EXPECTED_FRAME_COUNT = 220
LOAD_BATCH_SIZE = 8
FRAME_DIRECTORY = (
    Path(__file__).resolve().parent
    / "assets"
    / "civic_frames_outline"
)


def natural_key(path: Path) -> list[object]:
    """Sort frame_2 before frame_10."""

    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.name)
    ]


class Civic360Player(FloatLayout):
    """Transparent Civic animation with no separate red/glow layer."""

    def __init__(
        self,
        frames_dir: Path | None = None,
        rotation_seconds: float = ROTATION_SECONDS,
        reverse_rotation: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.frames_dir = Path(frames_dir) if frames_dir else FRAME_DIRECTORY
        self.rotation_seconds = rotation_seconds
        self.reverse_rotation = reverse_rotation
        self.frame_paths: list[Path] = []
        self.textures = []
        self.frame_index = 0
        self.load_index = 0
        self.load_event = None
        self.rotation_event = None
        self.rotation_started_at = None

        self.car_image = Image(
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
            fit_mode="contain",
            mipmap=True,
        )
        self.add_widget(self.car_image)

        self.status_label = Label(
            text="LOADING CIVIC",
            color=(0.65, 0.65, 0.70, 1),
            font_size=dp(8),
            size_hint=(1, 1),
            halign="center",
            valign="middle",
        )
        self.status_label.bind(size=self.status_label.setter("text_size"))
        self.add_widget(self.status_label)

        Clock.schedule_once(self.begin_loading, 0)

    def begin_loading(self, _dt) -> None:
        """Validate the approved frame set before decoding any textures."""

        self.frame_paths = (
            sorted(self.frames_dir.glob("frame_*.png"), key=natural_key)
            if self.frames_dir.exists()
            else []
        )
        if len(self.frame_paths) != EXPECTED_FRAME_COUNT:
            self.status_label.text = (
                f"CIVIC SET INCOMPLETE\n"
                f"{len(self.frame_paths)} / {EXPECTED_FRAME_COUNT} FRAMES"
            )
            print(
                f"Expected {EXPECTED_FRAME_COUNT} Civic frames in "
                f"{self.frames_dir}; found {len(self.frame_paths)}"
            )
            return

        self.status_label.text = (
            f"LOADING CIVIC // 0 / {EXPECTED_FRAME_COUNT}"
        )
        self.load_event = Clock.schedule_interval(self.load_batch, 0)

    def load_batch(self, _dt) -> bool:
        """Decode a few textures per UI cycle to keep the dashboard responsive."""

        stop = min(self.load_index + LOAD_BATCH_SIZE, len(self.frame_paths))
        try:
            for index in range(self.load_index, stop):
                texture = CoreImage(
                    str(self.frame_paths[index]),
                    mipmap=True,
                ).texture
                texture.min_filter = "linear"
                texture.mag_filter = "linear"
                self.textures.append(texture)
        except Exception as error:
            self.status_label.text = "CIVIC FRAME ERROR"
            print(f"Civic frame loading error: {error}")
            return False

        self.load_index = stop
        self.status_label.text = (
            f"LOADING CIVIC // {self.load_index} / {EXPECTED_FRAME_COUNT}"
        )
        if self.load_index < len(self.frame_paths):
            return True

        if self.reverse_rotation:
            self.textures.reverse()
        self.car_image.texture = self.textures[0]
        self.status_label.text = ""
        self.rotation_started_at = time.perf_counter()
        self.rotation_event = Clock.schedule_interval(
            self.update_rotation,
            1 / 60,
        )
        return False

    def update_rotation(self, _dt) -> None:
        """Use elapsed time so the Civic cannot speed up or slow down."""

        if not self.textures or self.rotation_started_at is None:
            return
        elapsed = time.perf_counter() - self.rotation_started_at
        progress = (elapsed % self.rotation_seconds) / self.rotation_seconds
        index = int(progress * len(self.textures)) % len(self.textures)
        if index == self.frame_index:
            return
        self.frame_index = index
        self.car_image.texture = self.textures[index]
