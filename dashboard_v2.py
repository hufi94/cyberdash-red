#!/usr/bin/env python3
"""Cyberdash Red Kivy dashboard v2.

The dashboard foundation remains a conversation-derived reconstruction rather
than a byte-for-byte copy recovered from the Raspberry Pi. V2 replaces only
the temporary Civic drawing with the approved transparent 220-frame player.
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
if os.environ.get("CYBERDASH_WINDOWED") == "1":
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

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import (
    Color,
    Line,
    PopMatrix,
    PushMatrix,
    Rectangle,
    RoundedRectangle,
    Scale,
    Translate,
)
from kivy.metrics import dp
from kivy.properties import NumericProperty
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from civic_360_widget import Civic360Player, ROTATION_SECONDS
from display_layout import (
    DESIGN_HEIGHT,
    DESIGN_WIDTH,
    SAFE_SCREEN_INSET,
    design_width_for_window,
    fit_design_to_window,
)


BACKGROUND = (0.025, 0.025, 0.03, 1)
PANEL = (0.055, 0.055, 0.065, 1)
WHITE = (0.96, 0.96, 0.98, 1)
LIGHT_GREY = (0.65, 0.65, 0.70, 1)
DARK_GREY = (0.18, 0.18, 0.21, 1)
RED = (0.92, 0.025, 0.045, 1)
DARK_RED = (0.35, 0.015, 0.025, 1)

# Set this as soon as the Window exists so the initial buffer is black instead
# of briefly flashing white while the dashboard and Civic textures load.
Window.clearcolor = BACKGROUND


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
    """Dark panel with red racing-style edge accents."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            Color(*PANEL)
            self.panel_background = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[dp(8)]
            )
            Color(*DARK_GREY)
            self.panel_border = Line(
                rounded_rectangle=(
                    self.x,
                    self.y,
                    self.width,
                    self.height,
                    dp(8),
                ),
                width=1.1,
            )
            Color(*RED)
            self.red_top_line = Line(points=[], width=1.5)
            self.corner_top = Line(points=[], width=2.2)
            self.corner_bottom = Line(points=[], width=2.2)
        self.bind(pos=self.update_canvas, size=self.update_canvas)

    def update_canvas(self, *_):
        self.panel_background.pos = self.pos
        self.panel_background.size = self.size
        self.panel_border.rounded_rectangle = (
            self.x,
            self.y,
            self.width,
            self.height,
            dp(8),
        )
        self.red_top_line.points = [
            self.x + dp(12),
            self.top - dp(10),
            self.right - dp(12),
            self.top - dp(10),
        ]
        corner = dp(17)
        self.corner_top.points = [
            self.x,
            self.top - corner,
            self.x,
            self.top,
            self.x + corner,
            self.top,
        ]
        self.corner_bottom.points = [
            self.right - corner,
            self.y,
            self.right,
            self.y,
            self.right,
            self.y + corner,
        ]


class TemperatureBar(Widget):
    temperature = NumericProperty(0.0)

    def __init__(self, minimum=-20, maximum=50, **kwargs):
        super().__init__(**kwargs)
        self.minimum = minimum
        self.maximum = maximum
        with self.canvas:
            Color(*DARK_GREY)
            self.track = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[dp(4)]
            )
            Color(*RED)
            self.fill = RoundedRectangle(
                pos=self.pos, size=(0, self.height), radius=[dp(4)]
            )
            Color(*WHITE)
            self.marker = Line(points=[], width=1.0)
        self.bind(
            pos=self.update_canvas,
            size=self.update_canvas,
            temperature=self.update_canvas,
        )

    def update_canvas(self, *_):
        self.track.pos = self.pos
        self.track.size = self.size
        value = max(self.minimum, min(self.maximum, self.temperature))
        ratio = (value - self.minimum) / (self.maximum - self.minimum)
        fill_width = self.width * ratio
        self.fill.pos = self.pos
        self.fill.size = (fill_width, self.height)
        marker_x = self.x + fill_width
        self.marker.points = [
            marker_x,
            self.y - dp(2),
            marker_x,
            self.top + dp(2),
        ]


class Visualizer(Widget):
    """Simulated placeholder; it is not connected to system audio."""

    def __init__(self, bar_count=17, **kwargs):
        super().__init__(**kwargs)
        self.bar_count = bar_count
        self.bar_values = [0.25] * bar_count
        self.target_values = [0.25] * bar_count
        self.bars = []
        with self.canvas:
            for index in range(bar_count):
                Color(*(WHITE if index < bar_count * 0.68 else RED))
                self.bars.append(
                    RoundedRectangle(
                        pos=self.pos,
                        size=(dp(5), dp(10)),
                        radius=[dp(2)],
                    )
                )
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
        if not self.bars:
            return
        usable_width = self.width * 0.86
        usable_height = self.height * 0.68
        left = self.x + self.width * 0.07
        bottom = self.y + self.height * 0.15
        spacing = usable_width / self.bar_count
        bar_width = spacing * 0.53
        for index, bar in enumerate(self.bars):
            bar_height = max(dp(5), usable_height * self.bar_values[index])
            bar.pos = (left + index * spacing, bottom)
            bar.size = (bar_width, bar_height)


class Dashboard(FloatLayout):
    inside_temperature = NumericProperty(0.0)
    outside_temperature = NumericProperty(0.0)

    def __init__(self, design_width=DESIGN_WIDTH, **kwargs):
        self.design_width = design_width
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

    def create_background(self):
        with self.canvas.before:
            Color(*BACKGROUND)
            self.background_rectangle = Rectangle(pos=self.pos, size=self.size)
            Color(*DARK_RED)
            self.background_lines = [Line(points=[], width=0.65) for _ in range(9)]
        self.bind(pos=self.update_background, size=self.update_background)

    def update_background(self, *_):
        self.background_rectangle.pos = self.pos
        self.background_rectangle.size = self.size
        for index, line in enumerate(self.background_lines):
            y = self.y + index * self.height / 8
            line.points = [self.x, y, self.right, y + self.height * 0.08]

    def create_panels(self):
        margin, gap, header_height = dp(10), dp(8), dp(26)
        usable_width = self.design_width - margin * 2
        usable_height = DESIGN_HEIGHT - margin * 2 - header_height
        column_width = (usable_width - gap) / 2
        row_height = (usable_height - gap) / 2
        top_y = DESIGN_HEIGHT - margin - header_height - row_height

        self.top_left_panel = RacingPanel(
            pos=(margin, top_y), size=(column_width, row_height)
        )
        self.top_right_panel = RacingPanel(
            pos=(margin + column_width + gap, top_y),
            size=(column_width, row_height),
        )
        self.bottom_left_panel = RacingPanel(
            pos=(margin, margin), size=(column_width, row_height)
        )
        self.bottom_right_panel = RacingPanel(
            pos=(margin + column_width + gap, margin),
            size=(column_width, row_height),
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
                "[b]CIVIC // DRIVER INTERFACE[/b]",
                (margin, DESIGN_HEIGHT - margin - header_height),
                (dp(280), header_height),
                13,
                halign="left",
                markup=True,
            )
        )
        self.add_widget(
            fixed_label(
                "[color=ff0a16]●[/color] SYSTEM ONLINE",
                (
                    self.design_width - margin - dp(190),
                    DESIGN_HEIGHT - margin - header_height,
                ),
                (dp(190), header_height),
                10,
                color=LIGHT_GREY,
                halign="right",
                markup=True,
            )
        )

    def panel_title(self, panel, text, reserve_end=0):
        self.add_widget(
            fixed_label(
                f"[color=ff0a16]{text}[/color]",
                (panel.x + dp(12), panel.top - dp(39)),
                (panel.width - dp(24) - dp(reserve_end), dp(22)),
                11,
                halign="left",
                markup=True,
            )
        )

    def create_time_panel(self):
        panel = self.top_left_panel
        self.panel_title(panel, "TIME / DATE")
        self.time_label = fixed_label(
            "00:00",
            (panel.x + dp(12), panel.y + dp(60)),
            (panel.width - dp(24), dp(72)),
            54,
        )
        self.seconds_label = fixed_label(
            "00",
            (panel.right - dp(51), panel.y + dp(71)),
            (dp(38), dp(24)),
            15,
            color=RED,
        )
        self.date_label = fixed_label(
            "MONDAY 01 JANUARY 2026",
            (panel.x + dp(12), panel.y + dp(26)),
            (panel.width - dp(24), dp(30)),
            12,
            color=LIGHT_GREY,
        )
        for label in (self.time_label, self.seconds_label, self.date_label):
            self.add_widget(label)

    def create_temperature_panel(self):
        panel = self.top_right_panel
        self.panel_title(panel, "CLIMATE MONITOR", reserve_end=125)
        self.temperature_status_label = fixed_label(
            "CONNECTING",
            (panel.right - dp(132), panel.top - dp(39)),
            (dp(120), dp(22)),
            8,
            color=LIGHT_GREY,
            halign="right",
        )
        self.add_widget(self.temperature_status_label)
        self.add_widget(
            fixed_label(
                "INSIDE",
                (panel.x + dp(16), panel.y + dp(111)),
                (dp(90), dp(24)),
                11,
                color=LIGHT_GREY,
                halign="left",
            )
        )
        self.inside_value_label = fixed_label(
            "--.-°",
            (panel.right - dp(121), panel.y + dp(101)),
            (dp(105), dp(43)),
            30,
            halign="right",
        )
        self.add_widget(self.inside_value_label)
        self.inside_bar = TemperatureBar(
            minimum=-20,
            maximum=50,
            size_hint=(None, None),
            size=(panel.width - dp(32), dp(10)),
            pos=(panel.x + dp(16), panel.y + dp(92)),
        )
        self.add_widget(self.inside_bar)

        self.add_widget(
            fixed_label(
                "OUTSIDE",
                (panel.x + dp(16), panel.y + dp(51)),
                (dp(90), dp(24)),
                11,
                color=LIGHT_GREY,
                halign="left",
            )
        )
        self.outside_value_label = fixed_label(
            "--.-°",
            (panel.right - dp(121), panel.y + dp(41)),
            (dp(105), dp(43)),
            30,
            halign="right",
        )
        self.add_widget(self.outside_value_label)
        self.outside_bar = TemperatureBar(
            minimum=-20,
            maximum=50,
            size_hint=(None, None),
            size=(panel.width - dp(32), dp(10)),
            pos=(panel.x + dp(16), panel.y + dp(32)),
        )
        self.add_widget(self.outside_bar)

    def create_vehicle_panel(self):
        panel = self.bottom_left_panel
        self.panel_title(panel, "VEHICLE PROFILE")
        self.civic_player = Civic360Player(
            rotation_seconds=ROTATION_SECONDS,
            reverse_rotation=False,
            size_hint=(None, None),
            size=(panel.width - dp(24), panel.height - dp(55)),
            pos=(panel.x + dp(12), panel.y + dp(25)),
        )
        self.add_widget(self.civic_player)
        self.add_widget(
            fixed_label(
                "[b]HONDA CIVIC EJ9 // B16A2[/b]",
                (panel.x + dp(15), panel.y + dp(5)),
                (panel.width - dp(30), dp(22)),
                10,
                markup=True,
            )
        )

    def create_visualizer_panel(self):
        panel = self.bottom_right_panel
        self.panel_title(panel, "AUDIO VISUALIZER", reserve_end=90)
        self.add_widget(
            fixed_label(
                "SIMULATED",
                (panel.right - dp(92), panel.top - dp(39)),
                (dp(80), dp(22)),
                8,
                color=LIGHT_GREY,
                halign="right",
            )
        )
        self.add_widget(
            Visualizer(
                bar_count=17,
                size_hint=(None, None),
                size=(panel.width - dp(24), panel.height - dp(48)),
                pos=(panel.x + dp(12), panel.y + dp(6)),
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
