#!/usr/bin/env python3
"""Reusable 220-frame Civic player for the Cyberdash Red Kivy dashboard."""

import csv
import math
import re
import time
from pathlib import Path

from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Rectangle
from kivy.graphics.texture import Texture
from kivy.metrics import dp
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label


ROTATION_SECONDS = 12.0
FADE_IN_SECONDS = 1.5
EXPECTED_FRAME_COUNT = 220
LOAD_BATCH_SIZE = 8
UNDERGLOW_ENABLED = True
UNDERGLOW_OPACITY = 0.92
UNDERGLOW_HEIGHT_RATIO = 0.09
UNDERGLOW_TRACKING_FILENAME = "underglow_tracking.tsv"
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


def build_underglow_texture(width: int = 256, height: int = 64):
    """Create one soft neon-red floor texture without an external image."""

    pixels = bytearray()
    for y in range(height):
        normalized_y = (y - (height - 1) / 2.0) / (height / 2.0)
        for x in range(width):
            normalized_x = (x - (width - 1) / 2.0) / (width / 2.0)
            outer = math.exp(
                -3.8 * (
                    normalized_x * normalized_x
                    + normalized_y * normalized_y
                )
            )
            hot_core = math.exp(
                -4.0 * normalized_x * normalized_x
                -80.0 * normalized_y * normalized_y
            )
            alpha = min(255, round(105 * outer + 190 * hot_core))
            pixels.extend((255, 0, 18, alpha))

    texture = Texture.create(size=(width, height), colorfmt="rgba")
    texture.blit_buffer(bytes(pixels), colorfmt="rgba", bufferfmt="ubyte")
    texture.min_filter = "linear"
    texture.mag_filter = "linear"
    return texture


class Civic360Player(FloatLayout):
    """Transparent Civic animation with frame-locked floor underglow."""

    def __init__(
        self,
        frames_dir: Path | None = None,
        rotation_seconds: float = ROTATION_SECONDS,
        fade_in_seconds: float = FADE_IN_SECONDS,
        underglow_enabled: bool = UNDERGLOW_ENABLED,
        underglow_opacity: float = UNDERGLOW_OPACITY,
        reverse_rotation: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.frames_dir = Path(frames_dir) if frames_dir else FRAME_DIRECTORY
        self.rotation_seconds = rotation_seconds
        self.fade_in_seconds = max(0.0, fade_in_seconds)
        self.underglow_enabled = underglow_enabled
        self.underglow_opacity = max(0.0, min(1.0, underglow_opacity))
        self.reverse_rotation = reverse_rotation
        self.frame_paths: list[Path] = []
        self.underglow_geometry: list[tuple[float, float, float]] = []
        self.textures = []
        self.frame_index = 0
        self.load_index = 0
        self.load_event = None
        self.rotation_event = None
        self.rotation_started_at = None

        with self.canvas.before:
            self.underglow_color = Color(1, 1, 1, 0)
            self.underglow_rectangle = Rectangle(
                texture=build_underglow_texture(),
                pos=self.pos,
                size=(0, 0),
            )

        self.car_image = Image(
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
            fit_mode="contain",
            mipmap=True,
            opacity=0,
        )
        self.add_widget(self.car_image)

        self.status_label = Label(
            text="",
            color=(0.65, 0.65, 0.70, 1),
            font_size=dp(8),
            size_hint=(1, 1),
            halign="center",
            valign="middle",
        )
        self.status_label.bind(size=self.status_label.setter("text_size"))
        self.add_widget(self.status_label)
        self.bind(
            pos=self.update_underglow_geometry,
            size=self.update_underglow_geometry,
        )

        # Decode the first frame before Kivy paints the widget. The Image stays
        # transparent until every frame is ready, avoiding both the driver's
        # empty white texture and a stationary Civic during background loading.
        self.begin_loading(0)

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

        if self.reverse_rotation:
            self.frame_paths.reverse()

        self.underglow_geometry = self.load_underglow_geometry()

        try:
            first_texture = self.load_texture(self.frame_paths[0])
        except Exception as error:
            self.status_label.text = "CIVIC FRAME ERROR"
            print(f"Civic first-frame loading error: {error}")
            return

        self.textures.append(first_texture)
        self.load_index = 1
        self.car_image.texture = first_texture
        self.update_underglow_geometry()
        self.load_event = Clock.schedule_interval(self.load_batch, 0)

    def load_underglow_geometry(self) -> list[tuple[float, float, float]]:
        """Load geometry by filename so reverse rotation stays synchronized."""

        tracking_path = self.frames_dir / UNDERGLOW_TRACKING_FILENAME
        try:
            with tracking_path.open(encoding="utf-8", newline="") as file:
                rows = csv.DictReader(file, delimiter="\t")
                geometry_by_frame = {
                    row["frame"]: (
                        float(row["center_x"]),
                        float(row["floor_y"]),
                        float(row["width"]),
                    )
                    for row in rows
                }
            geometry = [
                geometry_by_frame[frame_path.name]
                for frame_path in self.frame_paths
            ]
            if len(geometry) != EXPECTED_FRAME_COUNT:
                raise ValueError("incomplete tracking data")
            return geometry
        except (OSError, KeyError, TypeError, ValueError) as error:
            print(f"Civic underglow tracking disabled: {error}")
            self.underglow_enabled = False
            return [(0.5, 0.92, 0.56)] * len(self.frame_paths)

    def update_underglow_geometry(self, *_args) -> None:
        """Place the floor glow under the same frame shown by the Civic."""

        texture = self.car_image.texture
        if (
            texture is None
            or not self.underglow_geometry
            or self.width <= 0
            or self.height <= 0
        ):
            return

        texture_width, texture_height = texture.size
        scale = min(
            self.width / texture_width,
            self.height / texture_height,
        )
        image_width = texture_width * scale
        image_height = texture_height * scale
        image_x = self.center_x - image_width / 2.0
        image_y = self.center_y - image_height / 2.0

        center_x, floor_y, width = self.underglow_geometry[
            self.frame_index
        ]
        glow_width = image_width * width
        glow_height = image_height * UNDERGLOW_HEIGHT_RATIO
        glow_center_x = image_x + image_width * center_x
        glow_center_y = image_y + image_height * (1.0 - floor_y)
        self.underglow_rectangle.pos = (
            glow_center_x - glow_width / 2.0,
            glow_center_y - glow_height / 2.0,
        )
        self.underglow_rectangle.size = (glow_width, glow_height)

    @staticmethod
    def load_texture(frame_path: Path):
        """Decode one frame with the filtering used by the player."""

        texture = CoreImage(str(frame_path), mipmap=True).texture
        texture.min_filter = "linear"
        texture.mag_filter = "linear"
        return texture

    def load_batch(self, _dt) -> bool:
        """Decode a few textures per UI cycle to keep the dashboard responsive."""

        stop = min(self.load_index + LOAD_BATCH_SIZE, len(self.frame_paths))
        try:
            for index in range(self.load_index, stop):
                self.textures.append(
                    self.load_texture(self.frame_paths[index])
                )
        except Exception as error:
            self.status_label.text = "CIVIC FRAME ERROR"
            print(f"Civic frame loading error: {error}")
            return False

        self.load_index = stop
        if self.load_index < len(self.frame_paths):
            return True

        self.rotation_started_at = time.perf_counter()
        self.rotation_event = Clock.schedule_interval(
            self.update_rotation,
            1 / 60,
        )
        return False

    def update_rotation(self, _dt) -> None:
        """Rotate at a fixed speed while smoothly revealing the loaded Civic."""

        if not self.textures or self.rotation_started_at is None:
            return
        elapsed = time.perf_counter() - self.rotation_started_at

        if self.fade_in_seconds == 0:
            self.car_image.opacity = 1
        else:
            fade_progress = min(1.0, elapsed / self.fade_in_seconds)
            # Smoothstep gives a soft start and finish without pausing rotation.
            self.car_image.opacity = (
                fade_progress
                * fade_progress
                * (3.0 - 2.0 * fade_progress)
            )
        self.underglow_color.a = (
            self.car_image.opacity * self.underglow_opacity
            if self.underglow_enabled
            else 0
        )

        progress = (elapsed % self.rotation_seconds) / self.rotation_seconds
        index = int(progress * len(self.textures)) % len(self.textures)
        if index == self.frame_index:
            return
        self.frame_index = index
        self.car_image.texture = self.textures[index]
        self.update_underglow_geometry()
