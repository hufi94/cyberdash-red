#!/usr/bin/env python3
"""Cyberdash Red Kivy dashboard v2.

The dashboard foundation remains a conversation-derived reconstruction rather
than a byte-for-byte copy recovered from the Raspberry Pi. This revision uses
the approved structured red/white telemetry layout and transparent 220-frame
Civic player.
The 480-pixel-tall design adapts from 640 to 854 pixels wide before scaling,
so common Pi and HDMI displays are filled without stretching the artwork.
The audio visualizer remains explicitly simulated.
"""

import os

# This interface is authored as an exact 640x480 pixel canvas. Lock Kivy's
# density multiplier so Retina/high-DPI monitors do not enlarge text twice.
os.environ.setdefault("KIVY_METRICS_DENSITY", "1")
os.environ.setdefault("KIVY_METRICS_FONTSCALE", "1")

from kivy.config import Config

Config.set("graphics", "width", "640")
Config.set("graphics", "height", "480")
WINDOWED_MODE = os.environ.get("CYBERDASH_WINDOWED") == "1"
if WINDOWED_MODE:
    Config.set("graphics", "resizable", "1")
    Config.set("graphics", "fullscreen", "0")
    Config.set("graphics", "borderless", "0")
else:
    Config.set("graphics", "resizable", "0")
    Config.set("graphics", "fullscreen", "auto")
    Config.set("graphics", "borderless", "1")
Config.set("kivy", "exit_on_escape", "1")

import math
import random
from datetime import datetime

from PIL import Image as PILImage
from PIL import ImageDraw
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import (
    Color,
    Line,
    Mesh,
    PopMatrix,
    PushMatrix,
    Rectangle,
    RoundedRectangle,
    Scale,
    Translate,
)
from kivy.graphics.texture import Texture
from kivy.metrics import dp
from kivy.properties import NumericProperty
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from civic_360_widget import Civic360Player, ROTATION_SECONDS
from dashboard_theme import (
    active_temperature_segments,
    clipped_outline_points,
    dashboard_number_scale,
    dashboard_ui_scale,
    responsive_dashboard_panels,
    visualizer_row_color,
)
from display_layout import (
    DESIGN_HEIGHT,
    DESIGN_WIDTH,
    SAFE_SCREEN_INSET,
    design_width_for_window,
    fit_design_to_window,
)


BACKGROUND = (0.025, 0.025, 0.03, 1)
PANEL = (0.035, 0.035, 0.043, 1)
WHITE = (0.96, 0.96, 0.98, 1)
LIGHT_GREY = (0.65, 0.65, 0.70, 1)
RED = (0.92, 0.025, 0.045, 1)
BORDER_GREY = (0.30, 0.30, 0.33, 1)
INACTIVE_RED = (0.12, 0.012, 0.022, 1)

# Set this as soon as the Window exists so the initial buffer is black instead
# of briefly flashing white while the dashboard and Civic textures load.
Window.clearcolor = BACKGROUND
Window.show_cursor = WINDOWED_MODE


def fixed_label(
    text,
    pos,
    size,
    font_size,
    color=WHITE,
    halign="center",
    valign="middle",
    markup=False,
):
    label = Label(
        text=text,
        markup=markup,
        color=color,
        font_size=dp(font_size),
        size_hint=(None, None),
        size=size,
        pos=pos,
        halign=halign,
        valign=valign,
    )
    label.bind(size=label.setter("text_size"))
    return label


class RacingPanel(Widget):
    """Dark clipped panel with restrained racing-red corner accents."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            Color(*PANEL)
            self.panel_background = Mesh(
                vertices=[],
                indices=list(range(8)),
                mode="triangle_fan",
            )
            Color(*BORDER_GREY)
            self.panel_border = Line(points=[], close=True, width=1.0)
            Color(*RED)
            self.corner_top = Line(points=[], width=2.0)
            self.corner_bottom = Line(points=[], width=2.0)
        self.bind(pos=self.update_canvas, size=self.update_canvas)
        self.update_canvas()

    def update_canvas(self, *_):
        cut = dp(8)
        points = clipped_outline_points(
            self.x,
            self.y,
            self.width,
            self.height,
            cut,
        )
        vertices = []
        for index in range(0, len(points), 2):
            vertices.extend((points[index], points[index + 1], 0.0, 0.0))
        self.panel_background.vertices = vertices
        self.panel_border.points = list(points)
        self.corner_top.points = [
            self.x,
            self.top - cut,
            self.x + cut,
            self.top,
            self.x + dp(26),
            self.top,
        ]
        self.corner_bottom.points = [
            self.right - dp(26),
            self.y,
            self.right - cut,
            self.y,
            self.right,
            self.y + cut,
        ]


class ThermometerGaugeIcon(Widget):
    """Anti-aliased white/red thermometer rendered from a large texture."""

    _smooth_texture = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.__class__._smooth_texture is None:
            self.__class__._smooth_texture = self.build_smooth_texture()
        with self.canvas:
            Color(1, 1, 1, 1)
            self.icon_rectangle = Rectangle(
                texture=self.__class__._smooth_texture,
                pos=self.pos,
                size=self.size,
            )
        self.bind(pos=self.update_canvas, size=self.update_canvas)
        self.update_canvas()

    @staticmethod
    def build_smooth_texture():
        drawing_scale = 8
        width = 38 * drawing_scale
        height = 44 * drawing_scale
        image = PILImage.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        def scaled_box(left, top, right, bottom):
            return tuple(
                round(value * drawing_scale)
                for value in (left, top, right, bottom)
            )

        white = (246, 246, 250, 255)
        red = (255, 8, 28, 255)
        transparent = (0, 0, 0, 0)

        # Outer white housing, then a transparent inset to create the outline.
        draw.rounded_rectangle(
            scaled_box(7, 1, 17, 32),
            radius=5 * drawing_scale,
            fill=white,
        )
        draw.ellipse(scaled_box(2, 22, 22, 42), fill=white)
        draw.rounded_rectangle(
            scaled_box(9, 3, 15, 31),
            radius=3 * drawing_scale,
            fill=transparent,
        )
        draw.ellipse(scaled_box(4, 24, 20, 40), fill=transparent)

        # Red mercury and bulb.
        draw.rounded_rectangle(
            scaled_box(10.5, 9, 13.5, 33),
            radius=1.5 * drawing_scale,
            fill=red,
        )
        draw.ellipse(scaled_box(6.5, 27, 17.5, 38), fill=red)

        # Three white temperature scale marks from the supplied reference.
        for left, top, right, bottom in (
            (23, 8, 35, 10.5),
            (23, 16, 32, 18.5),
            (23, 24, 35, 26.5),
        ):
            draw.rounded_rectangle(
                scaled_box(left, top, right, bottom),
                radius=1.25 * drawing_scale,
                fill=white,
            )

        # Pre-filter once, then let Kivy use linear filtering for final display.
        image = image.resize(
            (width // 2, height // 2),
            PILImage.Resampling.LANCZOS,
        )
        texture = Texture.create(size=image.size, colorfmt="rgba")
        texture.blit_buffer(
            image.tobytes(),
            colorfmt="rgba",
            bufferfmt="ubyte",
        )
        texture.flip_vertical()
        texture.mag_filter = "linear"
        texture.min_filter = "linear"
        return texture

    def update_canvas(self, *_):
        self.icon_rectangle.pos = self.pos
        self.icon_rectangle.size = self.size


class SegmentedTemperatureBar(Widget):
    temperature = NumericProperty(-20.0)

    def __init__(
        self,
        minimum=-20,
        maximum=50,
        segment_count=10,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.minimum = minimum
        self.maximum = maximum
        self.segment_count = segment_count
        self.temperature = minimum
        self.segment_colors = []
        self.segments = []
        with self.canvas:
            for _index in range(segment_count):
                self.segment_colors.append(Color(*INACTIVE_RED))
                self.segments.append(
                    RoundedRectangle(pos=self.pos, size=(0, 0), radius=[dp(1)])
                )
            Color(*LIGHT_GREY)
            self.tick_marks = [Line(points=[], width=0.8) for _ in range(5)]
        self.bind(
            pos=self.update_canvas,
            size=self.update_canvas,
            temperature=self.update_canvas,
        )
        self.update_canvas()

    def update_canvas(self, *_):
        gap = dp(3)
        segment_height = max(dp(5), self.height - dp(8))
        segment_width = max(
            dp(2),
            (self.width - gap * (self.segment_count - 1)) / self.segment_count,
        )
        active = active_temperature_segments(
            self.temperature,
            self.minimum,
            self.maximum,
            self.segment_count,
        )
        for index, (color, segment) in enumerate(
            zip(self.segment_colors, self.segments)
        ):
            color.rgba = RED if index < active else INACTIVE_RED
            segment.pos = (
                self.x + index * (segment_width + gap),
                self.y + dp(8),
            )
            segment.size = (segment_width, segment_height)
        for index, tick in enumerate(self.tick_marks):
            tick_x = self.x + self.width * index / 4.0
            tick.points = [tick_x, self.y, tick_x, self.y + dp(4)]


class Visualizer(Widget):
    """Segmented simulated spectrum with a red-to-white vertical colour map."""

    def __init__(self, bar_count=17, row_count=18, **kwargs):
        super().__init__(**kwargs)
        self.bar_count = bar_count
        self.row_count = row_count
        self.bar_values = [
            0.34 + 0.22 * (math.sin(index * 0.92) + 1.0) / 2.0
            for index in range(bar_count)
        ]
        self.target_values = list(self.bar_values)
        self.segment_colors = []
        self.segments = []
        with self.canvas:
            for _bar_index in range(bar_count):
                color_column = []
                segment_column = []
                for row_index in range(row_count):
                    color_column.append(
                        Color(*visualizer_row_color(row_index, row_count))
                    )
                    segment_column.append(
                        RoundedRectangle(
                            pos=self.pos,
                            size=(0, 0),
                            radius=[dp(0.8)],
                        )
                    )
                self.segment_colors.append(color_column)
                self.segments.append(segment_column)
            Color(*LIGHT_GREY)
            self.baseline = Line(points=[], width=0.8)
        self.bind(pos=self.update_canvas, size=self.update_canvas)
        Clock.schedule_interval(self.animate, 1 / 30)

    def animate(self, _dt):
        for index in range(self.bar_count):
            if random.random() < 0.12:
                wave = (math.sin(index * 0.75 + random.random() * 2) + 1) / 2
                self.target_values[index] = max(
                    0.08, min(1.0, wave * random.uniform(0.45, 1.0))
                )
            current = self.bar_values[index]
            target = self.target_values[index]
            factor = 0.32 if target > current else 0.11
            self.bar_values[index] = current + (target - current) * factor
        self.update_canvas()

    def update_canvas(self, *_):
        if not self.segments:
            return
        usable_width = self.width * 0.92
        usable_height = self.height * 0.78
        left = self.x + self.width * 0.04
        bottom = self.y + self.height * 0.08
        spacing = usable_width / self.bar_count
        bar_width = spacing * 0.56
        row_slot = usable_height / self.row_count
        segment_height = row_slot * 0.62
        self.baseline.points = [left, bottom - dp(2), left + usable_width, bottom - dp(2)]
        for bar_index in range(self.bar_count):
            active_rows = max(
                1,
                min(
                    self.row_count,
                    round(self.bar_values[bar_index] * self.row_count),
                ),
            )
            for row_index in range(self.row_count):
                color = self.segment_colors[bar_index][row_index]
                segment = self.segments[bar_index][row_index]
                if row_index < active_rows:
                    color.rgba = visualizer_row_color(row_index, self.row_count)
                else:
                    color.rgba = (0.0, 0.0, 0.0, 0.0)
                segment.pos = (
                    left + bar_index * spacing,
                    bottom + row_index * row_slot,
                )
                segment.size = (bar_width, segment_height)


class HeaderDots(Widget):
    """Three restrained red system indicators in the command header."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.dots = []
        with self.canvas:
            Color(*RED)
            for _index in range(3):
                self.dots.append(
                    RoundedRectangle(pos=self.pos, size=(0, 0), radius=[dp(4)])
                )
        self.bind(pos=self.update_canvas, size=self.update_canvas)
        self.update_canvas()

    def update_canvas(self, *_):
        diameter = dp(6)
        spacing = dp(15)
        start_x = self.center_x - spacing
        for index, dot in enumerate(self.dots):
            dot.pos = (
                start_x + index * spacing - diameter / 2.0,
                self.center_y - diameter / 2.0,
            )
            dot.size = (diameter, diameter)


class AccentDivider(Widget):
    """Thin time-panel divider with small red racing markers."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            Color(*BORDER_GREY)
            self.line = Line(points=[], width=0.8)
            Color(*RED)
            self.left_mark = Line(points=[], width=1.8)
            self.center_mark = Line(points=[], width=1.8)
            self.right_mark = Line(points=[], width=1.8)
        self.bind(pos=self.update_canvas, size=self.update_canvas)
        self.update_canvas()

    def update_canvas(self, *_):
        center_y = self.center_y
        self.line.points = [self.x, center_y, self.right, center_y]
        self.left_mark.points = [
            self.x + dp(18),
            center_y - dp(3),
            self.x + dp(18),
            center_y + dp(3),
        ]
        self.center_mark.points = [
            self.center_x - dp(5),
            center_y,
            self.center_x + dp(5),
            center_y,
        ]
        self.right_mark.points = [
            self.right - dp(18),
            center_y - dp(3),
            self.right - dp(18),
            center_y + dp(3),
        ]


class OutlinedChip(Widget):
    """Small clipped status-chip outline used by the vehicle module."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            Color(*BORDER_GREY)
            self.outline = Line(points=[], close=True, width=0.8)
        self.bind(pos=self.update_canvas, size=self.update_canvas)
        self.update_canvas()

    def update_canvas(self, *_):
        self.outline.points = list(
            clipped_outline_points(
                self.x,
                self.y,
                self.width,
                self.height,
                dp(4),
            )
        )


class Dashboard(FloatLayout):
    inside_temperature = NumericProperty(0.0)
    outside_temperature = NumericProperty(0.0)

    def __init__(self, design_width=DESIGN_WIDTH, **kwargs):
        self.design_width = design_width
        self.ui_scale = dashboard_ui_scale(design_width)
        self.number_scale = dashboard_number_scale(design_width)
        self.compact_mode = self.ui_scale > 1.0
        self.panel_layout = responsive_dashboard_panels(
            design_width,
            DESIGN_HEIGHT,
        )
        super().__init__(**kwargs)
        Window.clearcolor = BACKGROUND
        self.inside_sensor = None
        self.outside_sensor = None
        self.sensor_status = "CONNECTING"

        self.create_background()
        self.create_panels()
        self.create_time_panel()
        self.create_temperature_panel()
        self.create_vehicle_panel()
        self.create_visualizer_panel()
        self.connect_sensors()

        Clock.schedule_interval(self.update_clock, 0.25)
        Clock.schedule_interval(self.update_sensors, 2.0)
        self.update_clock(0)
        self.update_sensors(0)

    def font_size(self, value):
        """Boost important typography only on the compact Pi display."""

        return value * self.ui_scale

    def number_font_size(self, value):
        """Scale the primary clock and climate readings independently."""

        return value * self.number_scale

    def create_background(self):
        with self.canvas.before:
            Color(*BACKGROUND)
            self.background_rectangle = Rectangle(pos=self.pos, size=self.size)
            Color(*BORDER_GREY)
            self.outer_border = Line(points=[], close=True, width=0.8)
            self.header_separator = Line(points=[], width=0.8)
            Color(*RED)
            self.outer_top_corner = Line(points=[], width=2.0)
            self.outer_bottom_corner = Line(points=[], width=2.0)
        self.bind(pos=self.update_background, size=self.update_background)

    def update_background(self, *_):
        self.background_rectangle.pos = self.pos
        self.background_rectangle.size = self.size
        inset = dp(5)
        cut = dp(10)
        self.outer_border.points = list(
            clipped_outline_points(
                self.x + inset,
                self.y + inset,
                self.width - inset * 2,
                self.height - inset * 2,
                cut,
            )
        )
        layout = self.panel_layout
        separator_y = self.y + layout.header_y - dp(3)
        self.header_separator.points = [
            self.x + dp(8),
            separator_y,
            self.right - dp(8),
            separator_y,
        ]
        self.outer_top_corner.points = [
            self.x + inset,
            self.top - inset - cut,
            self.x + inset + cut,
            self.top - inset,
            self.x + inset + dp(38),
            self.top - inset,
        ]
        self.outer_bottom_corner.points = [
            self.right - inset - dp(38),
            self.y + inset,
            self.right - inset - cut,
            self.y + inset,
            self.right - inset,
            self.y + inset + cut,
        ]

    def create_panels(self):
        layout = self.panel_layout

        self.top_left_panel = RacingPanel(
            size_hint=(None, None),
            pos=(layout.top_left.x, layout.top_left.y),
            size=(layout.top_left.width, layout.top_left.height),
        )
        self.top_right_panel = RacingPanel(
            size_hint=(None, None),
            pos=(layout.top_right.x, layout.top_right.y),
            size=(layout.top_right.width, layout.top_right.height),
        )
        self.bottom_left_panel = RacingPanel(
            size_hint=(None, None),
            pos=(layout.bottom_left.x, layout.bottom_left.y),
            size=(layout.bottom_left.width, layout.bottom_left.height),
        )
        self.bottom_right_panel = RacingPanel(
            size_hint=(None, None),
            pos=(layout.bottom_right.x, layout.bottom_right.y),
            size=(layout.bottom_right.width, layout.bottom_right.height),
        )
        for panel in (
            self.top_left_panel,
            self.top_right_panel,
            self.bottom_left_panel,
            self.bottom_right_panel,
        ):
            self.add_widget(panel)

        self.add_widget(
            fixed_label(
                "[b]CIVIC [color=ff1c2b]//[/color] DRIVER INTERFACE[/b]",
                (layout.top_left.x + dp(12), layout.header_y + dp(4)),
                (dp(300), layout.header_height - dp(8)),
                self.font_size(14),
                halign="left",
                markup=True,
            )
        )
        self.add_widget(
            HeaderDots(
                size_hint=(None, None),
                size=(dp(66), layout.header_height - dp(8)),
                pos=(
                    self.design_width / 2 - dp(33),
                    layout.header_y + dp(4),
                ),
            )
        )
        self.add_widget(
            fixed_label(
                "[color=ff1c2b]▮[/color] SYSTEM ONLINE",
                (
                    self.design_width - dp(212),
                    layout.header_y + dp(4),
                ),
                (dp(190), layout.header_height - dp(8)),
                self.font_size(12),
                color=LIGHT_GREY,
                halign="right",
                markup=True,
            )
        )

    def panel_title(self, panel, text, reserve_end=0, align_left=False):
        side_padding = dp(16 if self.compact_mode else 18)
        title = fixed_label(
            f"[b][color=ff1c2b]{text}[/color][/b]",
            (panel.x + side_padding, panel.top - dp(39)),
            (
                panel.width - side_padding * 2 - dp(reserve_end),
                dp(24),
            ),
            self.font_size(13),
            halign="left" if align_left else "center",
            markup=True,
        )
        if align_left:
            title.text_size = title.size
        self.add_widget(title)

    def create_time_panel(self):
        panel = self.top_left_panel
        self.panel_title(panel, "TIME / DATE")
        time_left = dp(18 if self.compact_mode else 22)
        time_width_padding = dp(84 if self.compact_mode else 94)
        self.time_label = fixed_label(
            "00:00",
            (
                panel.x + time_left,
                panel.y + dp(72 if self.compact_mode else 76),
            ),
            (
                panel.width - time_width_padding,
                dp(88 if self.compact_mode else 72),
            ),
            self.number_font_size(64),
        )
        self.seconds_label = fixed_label(
            "00",
            (
                panel.right - dp(61 if self.compact_mode else 64),
                panel.y + dp(89),
            ),
            (dp(48), dp(38)),
            self.number_font_size(22),
            color=RED,
        )
        divider_padding = dp(14 if self.compact_mode else 18)
        self.add_widget(
            AccentDivider(
                size_hint=(None, None),
                size=(panel.width - divider_padding * 2, dp(8)),
                pos=(panel.x + divider_padding, panel.y + dp(61)),
            )
        )
        date_padding = dp(14 if self.compact_mode else 18)
        self.date_label = fixed_label(
            "MONDAY 01 JANUARY 2026",
            (panel.x + date_padding, panel.y + dp(25)),
            (panel.width - date_padding * 2, dp(30)),
            self.font_size(15),
            color=LIGHT_GREY,
        )
        for label in (self.time_label, self.seconds_label, self.date_label):
            self.add_widget(label)

    def create_temperature_panel(self):
        panel = self.top_right_panel
        self.panel_title(panel, "CLIMATE MONITOR", reserve_end=125)
        self.temperature_status_label = fixed_label(
            "CONNECTING",
            (panel.right - dp(138), panel.top - dp(39)),
            (dp(120), dp(24)),
            self.font_size(10),
            color=LIGHT_GREY,
            halign="right",
        )
        self.add_widget(self.temperature_status_label)
        icon_width = dp(38 if self.compact_mode else 34)
        icon_height = dp(44 if self.compact_mode else 40)
        icon_x = panel.x + dp(10 if self.compact_mode else 12)
        self.add_widget(
            ThermometerGaugeIcon(
                size_hint=(None, None),
                size=(icon_width, icon_height),
                pos=(icon_x, panel.y + dp(96 if self.compact_mode else 99)),
            )
        )
        self.add_widget(
            fixed_label(
                "INSIDE",
                (panel.x + dp(53), panel.y + dp(111)),
                (dp(90), dp(24)),
                self.font_size(14),
                color=LIGHT_GREY,
                halign="left",
            )
        )
        self.inside_value_label = fixed_label(
            "--.-°",
            (panel.right - dp(110), panel.y + dp(99)),
            (dp(92), dp(48)),
            self.number_font_size(31),
            halign="right",
        )
        self.add_widget(self.inside_value_label)
        bar_left = dp(52 if self.compact_mode else 55)
        bar_right = dp(12 if self.compact_mode else 18)
        self.inside_bar = SegmentedTemperatureBar(
            minimum=-20,
            maximum=50,
            segment_count=10,
            size_hint=(None, None),
            size=(panel.width - bar_left - bar_right, dp(20)),
            pos=(panel.x + bar_left, panel.y + dp(77)),
        )
        self.add_widget(self.inside_bar)

        self.add_widget(
            ThermometerGaugeIcon(
                size_hint=(None, None),
                size=(icon_width, icon_height),
                pos=(icon_x, panel.y + dp(36 if self.compact_mode else 39)),
            )
        )
        self.add_widget(
            fixed_label(
                "OUTSIDE",
                (panel.x + dp(53), panel.y + dp(51)),
                (dp(90), dp(24)),
                self.font_size(14),
                color=LIGHT_GREY,
                halign="left",
            )
        )
        self.outside_value_label = fixed_label(
            "--.-°",
            (panel.right - dp(110), panel.y + dp(39)),
            (dp(92), dp(48)),
            self.number_font_size(31),
            halign="right",
        )
        self.add_widget(self.outside_value_label)
        self.outside_bar = SegmentedTemperatureBar(
            minimum=-20,
            maximum=50,
            segment_count=10,
            size_hint=(None, None),
            size=(panel.width - bar_left - bar_right, dp(20)),
            pos=(panel.x + bar_left, panel.y + dp(17)),
        )
        self.add_widget(self.outside_bar)

    def create_vehicle_panel(self):
        panel = self.bottom_left_panel
        self.panel_title(
            panel,
            "VEHICLE PROFILE",
            reserve_end=92,
            align_left=True,
        )
        chip_width = dp(78 if self.compact_mode else 74)
        chip_height = dp(24 if self.compact_mode else 22)
        chip_right = dp(12 if self.compact_mode else 14)
        chip_x = panel.right - chip_right - chip_width
        chip_y = panel.top - dp(40 if self.compact_mode else 39)
        self.add_widget(
            OutlinedChip(
                size_hint=(None, None),
                size=(chip_width, chip_height),
                pos=(chip_x, chip_y),
            )
        )
        self.add_widget(
            fixed_label(
                "360 [color=ff1c2b]LIVE[/color]",
                (chip_x, chip_y),
                (chip_width, chip_height),
                self.font_size(9),
                color=LIGHT_GREY,
                markup=True,
            )
        )
        self.civic_player = Civic360Player(
            rotation_seconds=ROTATION_SECONDS,
            reverse_rotation=False,
            size_hint=(None, None),
            size=(
                panel.width - dp(10 if self.compact_mode else 20),
                panel.height - dp(48 if self.compact_mode else 56),
            ),
            pos=(
                panel.x + dp(5 if self.compact_mode else 10),
                panel.y + dp(19 if self.compact_mode else 23),
            ),
        )
        self.add_widget(self.civic_player)
        self.add_widget(
            fixed_label(
                "[b]HONDA CIVIC EG9  //  [color=ff1c2b]B16A2[/color][/b]",
                (panel.x + dp(10 if self.compact_mode else 15), panel.y + dp(3)),
                (
                    panel.width - dp(20 if self.compact_mode else 30),
                    dp(24),
                ),
                self.font_size(9),
                markup=True,
            )
        )

    def create_visualizer_panel(self):
        panel = self.bottom_right_panel
        self.panel_title(panel, "AUDIO VISUALIZER", reserve_end=112)
        self.add_widget(
            fixed_label(
                "SIMULATED INPUT",
                (panel.right - dp(122), panel.top - dp(39)),
                (dp(104), dp(24)),
                self.font_size(8),
                color=LIGHT_GREY,
                halign="right",
            )
        )
        self.add_widget(
            Visualizer(
                bar_count=17,
                row_count=18,
                size_hint=(None, None),
                size=(
                    panel.width - dp(14 if self.compact_mode else 24),
                    panel.height - dp(42 if self.compact_mode else 50),
                ),
                pos=(
                    panel.x + dp(7 if self.compact_mode else 12),
                    panel.y + dp(4 if self.compact_mode else 7),
                ),
            )
        )

    def connect_sensors(self):
        try:
            import board
            from adafruit_bme280 import basic as adafruit_bme280

            i2c = board.I2C()
            self.inside_sensor = adafruit_bme280.Adafruit_BME280_I2C(
                i2c, address=0x77
            )
            self.outside_sensor = adafruit_bme280.Adafruit_BME280_I2C(
                i2c, address=0x76
            )
            self.sensor_status = "SENSORS ONLINE"
        except Exception as error:
            print(f"Sensor connection error: {error}")
            self.sensor_status = "SENSOR ERROR"

    def update_clock(self, _dt):
        now = datetime.now()
        self.time_label.text = now.strftime("%H:%M")
        self.seconds_label.text = now.strftime("%S")
        self.date_label.text = now.strftime("%A %d %B %Y").upper()

    def update_sensors(self, _dt):
        if self.inside_sensor is None or self.outside_sensor is None:
            self.inside_value_label.text = "--.-°"
            self.outside_value_label.text = "--.-°"
            self.temperature_status_label.text = self.sensor_status
            return
        try:
            inside = round(self.inside_sensor.temperature, 1)
            outside = round(self.outside_sensor.temperature, 1)
            self.inside_temperature = inside
            self.outside_temperature = outside
            self.inside_value_label.text = f"{inside:.1f}°"
            self.outside_value_label.text = f"{outside:.1f}°"
            self.inside_bar.temperature = inside
            self.outside_bar.temperature = outside
            self.temperature_status_label.text = "SENSORS ONLINE"
        except Exception as error:
            print(f"Sensor reading error: {error}")
            self.temperature_status_label.text = "READ ERROR"


class ResponsiveDashboard(FloatLayout):
    """Adapt the dashboard width, then scale it with a small safe inset."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*BACKGROUND)
            self.screen_background = Rectangle(pos=self.pos, size=self.size)
            PushMatrix()
            self.dashboard_translation = Translate(0, 0, 0)
            self.dashboard_scale = Scale(1, 1, 1)
        with self.canvas.after:
            PopMatrix()

        self.dashboard = None
        self.design_width = DESIGN_WIDTH
        self.bind(pos=self.update_viewport, size=self.update_viewport)
        Clock.schedule_once(self.build_dashboard, 0)

    def build_dashboard(self, _dt):
        self.design_width = design_width_for_window(
            self.width,
            self.height,
        )
        self.dashboard = Dashboard(
            design_width=self.design_width,
            size_hint=(None, None),
            size=(self.design_width, DESIGN_HEIGHT),
            pos=(0, 0),
        )
        self.add_widget(self.dashboard)
        self.update_viewport()

    def update_viewport(self, *_):
        self.screen_background.pos = self.pos
        self.screen_background.size = self.size
        scale, offset_x, offset_y = fit_design_to_window(
            self.width,
            self.height,
            design_width=self.design_width,
            safe_inset=SAFE_SCREEN_INSET,
        )
        self.dashboard_translation.x = self.x + offset_x
        self.dashboard_translation.y = self.y + offset_y
        self.dashboard_scale.x = scale
        self.dashboard_scale.y = scale


class RacingDashboardApp(App):
    title = "Civic Racing Dashboard V2"

    def build(self):
        return ResponsiveDashboard()


if __name__ == "__main__":
    RacingDashboardApp().run()
