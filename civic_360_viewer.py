#!/usr/bin/env python3
"""Kivy viewer for the processed transparent Civic outline frames."""

from kivy.config import Config

Config.set("graphics", "width", "400")
Config.set("graphics", "height", "260")
Config.set("graphics", "resizable", "0")
Config.set("graphics", "fullscreen", "0")
Config.set("kivy", "exit_on_escape", "1")

import re
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label


BACKGROUND = (0.025, 0.025, 0.03, 1)
PANEL = (0.055, 0.055, 0.065, 1)
WHITE = (0.96, 0.96, 0.98, 1)
RED = (0.92, 0.025, 0.045, 1)
GREY = (0.25, 0.25, 0.28, 1)


def natural_key(path: Path) -> list[object]:
    """Sort frame_2 before frame_10."""

    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.name)
    ]


class Civic360(FloatLayout):
    """Preloaded transparent-frame animation widget."""

    def __init__(
        self,
        frames_dir: Path | None = None,
        rotation_seconds: float = 7.0,
        reverse_rotation: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.frames_dir = frames_dir or (
            Path(__file__).resolve().parent
            / "assets"
            / "civic_frames_outline"
        )
        self.rotation_seconds = rotation_seconds
        self.reverse_rotation = reverse_rotation
        self.frame_index = 0
        self.textures = []
        self.animation_event = None

        with self.canvas.before:
            Color(*PANEL)
            self.panel_background = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[dp(9)],
            )
            Color(*GREY)
            self.panel_border = Line(
                rounded_rectangle=(
                    self.x,
                    self.y,
                    self.width,
                    self.height,
                    dp(9),
                ),
                width=1.2,
            )
            Color(*RED)
            self.red_ground_line = Line(points=[], width=1.5)

        self.car_image = Image(
            size_hint=(0.94, 0.80),
            pos_hint={"center_x": 0.5, "center_y": 0.50},
            fit_mode="contain",
            mipmap=True,
        )
        self.add_widget(self.car_image)

        self.status_label = Label(
            text="LOADING OUTLINE FRAMES",
            color=WHITE,
            font_size=dp(11),
            size_hint=(1, None),
            height=dp(28),
            pos_hint={"x": 0, "y": 0.02},
        )
        self.add_widget(self.status_label)
        self.bind(pos=self.update_canvas, size=self.update_canvas)
        Clock.schedule_once(self.load_frames, 0)

    def update_canvas(self, *_args) -> None:
        """Keep the panel artwork aligned with the widget."""

        self.panel_background.pos = self.pos
        self.panel_background.size = self.size
        self.panel_border.rounded_rectangle = (
            self.x,
            self.y,
            self.width,
            self.height,
            dp(9),
        )
        self.red_ground_line.points = [
            self.x + self.width * 0.16,
            self.y + self.height * 0.16,
            self.x + self.width * 0.84,
            self.y + self.height * 0.16,
        ]

    def load_frames(self, _dt) -> None:
        """Load the processed frames and start rotation."""

        frame_paths = (
            sorted(self.frames_dir.glob("*.png"), key=natural_key)
            if self.frames_dir.exists()
            else []
        )

        if not frame_paths:
            self.status_label.text = (
                "NO OUTLINE FRAMES FOUND\n"
                "RUN convert_civic_outline.py FIRST"
            )
            return

        try:
            self.textures = [
                CoreImage(str(frame_path), mipmap=True).texture
                for frame_path in frame_paths
            ]
        except Exception as error:
            self.status_label.text = "OUTLINE FRAME LOADING ERROR"
            print(f"Frame loading error: {error}")
            return

        if self.reverse_rotation:
            self.textures.reverse()

        self.car_image.texture = self.textures[0]
        self.status_label.text = f"CIVIC OUTLINE // {len(self.textures)} FRAMES"
        frame_interval = max(
            self.rotation_seconds / len(self.textures),
            1 / 30,
        )
        self.animation_event = Clock.schedule_interval(
            self.next_frame,
            frame_interval,
        )

    def next_frame(self, _dt) -> None:
        """Advance exactly one frame while retaining sequence order."""

        if not self.textures:
            return

        self.frame_index = (self.frame_index + 1) % len(self.textures)
        self.car_image.texture = self.textures[self.frame_index]


class CivicViewerApp(App):
    """Standalone outline animation preview."""

    title = "Civic Outline 360 Viewer"

    def build(self):
        Window.clearcolor = BACKGROUND
        return Civic360(
            rotation_seconds=7.0,
            reverse_rotation=False,
        )


if __name__ == "__main__":
    CivicViewerApp().run()
