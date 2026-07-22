#!/usr/bin/env python3
"""Reusable 220-frame Civic player for the Cyberdash Red Kivy dashboard."""

import re
import time
from pathlib import Path

from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Mesh
from kivy.graphics.texture import Texture
from kivy.metrics import dp
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label

from floor_glow import (
    EDGE_GLOW_THICKNESS,
    Point,
    build_floor_glow_rgba,
    glow_strip_corners,
    projected_edge_strengths,
    projected_floor_corners,
)


ROTATION_SECONDS = 12.0
FADE_IN_SECONDS = 1.5
EXPECTED_FRAME_COUNT = 220
LOAD_BATCH_SIZE = 8
FRAME_DIRECTORY = (
    Path(__file__).resolve().parent
    / "assets"
    / "civic_frames_outline"
)

# The glow is one soft Kivy texture. Its placement comes from the same frame
# index as the Civic, so it cannot advance on a separate timer or path.
GLOW_ENABLED = True
GLOW_OPACITY = 1.0
GLOW_TEXTURE_SIZE = (256, 64)
FRAME_PIXEL_SIZE = (576.0, 264.0)


def natural_key(path: Path) -> list[object]:
    """Sort frame_2 before frame_10."""

    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.name)
    ]


class Civic360Player(FloatLayout):
    """Transparent Civic animation above a stable Kivy floor reflection."""

    def __init__(
        self,
        frames_dir: Path | None = None,
        rotation_seconds: float = ROTATION_SECONDS,
        fade_in_seconds: float = FADE_IN_SECONDS,
        reverse_rotation: bool = False,
        glow_enabled: bool = GLOW_ENABLED,
        glow_opacity: float = GLOW_OPACITY,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.frames_dir = Path(frames_dir) if frames_dir else FRAME_DIRECTORY
        self.rotation_seconds = rotation_seconds
        self.fade_in_seconds = max(0.0, fade_in_seconds)
        self.reverse_rotation = reverse_rotation
        self.glow_enabled = glow_enabled
        self.glow_opacity = max(0.0, min(1.0, glow_opacity))
        self.frame_paths: list[Path] = []
        self.frame_source_indices: list[int] = []
        self.textures = []
        self.frame_index = 0
        self.load_index = 0
        self.load_event = None
        self.rotation_event = None
        self.rotation_started_at = None
        self.current_reveal_opacity = 0.0
        self.glow_edge_strengths = (0.0, 0.0, 0.0, 0.0)

        glow_texture = self.create_floor_glow_texture()
        self.glow_colors = []
        self.glow_meshes = []
        with self.canvas.before:
            for _edge_index in range(4):
                self.glow_colors.append(Color(1, 1, 1, 0))
                self.glow_meshes.append(
                    Mesh(
                        texture=glow_texture,
                        vertices=[0.0] * 16,
                        indices=[0, 1, 2, 0, 2, 3],
                        mode="triangles",
                    )
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
            pos=self.update_floor_glow_geometry,
            size=self.update_floor_glow_geometry,
        )
        self.update_floor_glow_geometry()

        # Decode the first frame before Kivy paints the widget. The Image stays
        # transparent until every frame is ready, avoiding both the driver's
        # empty white texture and a stationary Civic during background loading.
        self.begin_loading(0)

    @staticmethod
    def create_floor_glow_texture():
        """Build the code-only red reflection without loading another file."""

        texture = Texture.create(
            size=GLOW_TEXTURE_SIZE,
            colorfmt="rgba",
        )
        texture.blit_buffer(
            build_floor_glow_rgba(*GLOW_TEXTURE_SIZE),
            colorfmt="rgba",
            bufferfmt="ubyte",
        )
        texture.wrap = "clamp_to_edge"
        texture.min_filter = "linear"
        texture.mag_filter = "linear"
        return texture

    def update_floor_glow_geometry(self, *_args) -> None:
        """Project and map four rotating underbody edges into the Kivy area."""

        if (
            self.width <= 0
            or self.height <= 0
            or not self.frame_source_indices
        ):
            return

        frame_width, frame_height = FRAME_PIXEL_SIZE
        frame_aspect = frame_width / frame_height
        widget_aspect = self.width / self.height
        if widget_aspect > frame_aspect:
            image_height = self.height
            image_width = image_height * frame_aspect
        else:
            image_width = self.width
            image_height = image_width / frame_aspect

        image_left = self.center_x - image_width / 2.0
        image_bottom = self.center_y - image_height / 2.0
        source_index = self.frame_source_indices[
            min(self.frame_index, len(self.frame_source_indices) - 1)
        ]
        source_corners = projected_floor_corners(source_index)
        self.glow_edge_strengths = projected_edge_strengths(
            source_index,
            source_corners,
        )
        mapped_corners = tuple(
            Point(
                image_left + point.x / frame_width * image_width,
                image_bottom
                + (frame_height - point.y) / frame_height * image_height,
            )
            for point in source_corners
        )
        thickness = EDGE_GLOW_THICKNESS / frame_height * image_height

        for index, mesh in enumerate(self.glow_meshes):
            start = mapped_corners[index]
            end = mapped_corners[(index + 1) % 4]
            strip = glow_strip_corners(start, end, thickness)
            mesh.vertices = [
                strip[0].x,
                strip[0].y,
                0.0,
                0.0,
                strip[1].x,
                strip[1].y,
                1.0,
                0.0,
                strip[2].x,
                strip[2].y,
                1.0,
                1.0,
                strip[3].x,
                strip[3].y,
                0.0,
                1.0,
            ]
        self.update_floor_glow_opacity()

    def update_floor_glow_opacity(self) -> None:
        for color, strength in zip(
            self.glow_colors,
            self.glow_edge_strengths,
        ):
            color.a = (
                self.current_reveal_opacity
                * self.glow_opacity
                * strength
                if self.glow_enabled
                else 0.0
            )

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
        self.frame_source_indices = [
            int(path.stem.rsplit("_", 1)[-1])
            for path in self.frame_paths
        ]

        try:
            first_texture = self.load_texture(self.frame_paths[0])
        except Exception as error:
            self.status_label.text = "CIVIC FRAME ERROR"
            print(f"Civic first-frame loading error: {error}")
            return

        self.textures.append(first_texture)
        self.load_index = 1
        self.car_image.texture = first_texture
        self.update_floor_glow_geometry()
        self.load_event = Clock.schedule_interval(self.load_batch, 0)

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
            reveal_opacity = 1.0
        else:
            fade_progress = min(1.0, elapsed / self.fade_in_seconds)
            # Smoothstep gives a soft start and finish without pausing rotation.
            reveal_opacity = (
                fade_progress
                * fade_progress
                * (3.0 - 2.0 * fade_progress)
            )

        self.current_reveal_opacity = reveal_opacity
        self.car_image.opacity = reveal_opacity
        self.update_floor_glow_opacity()

        progress = (elapsed % self.rotation_seconds) / self.rotation_seconds
        index = int(progress * len(self.textures)) % len(self.textures)
        if index == self.frame_index:
            return
        self.frame_index = index
        self.car_image.texture = self.textures[index]
        self.update_floor_glow_geometry()
