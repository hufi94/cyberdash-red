#!/usr/bin/env python3
"""Animated SiR startup overlay for the Cyberdash dashboard."""

from pathlib import Path

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.properties import BooleanProperty, NumericProperty
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image


ASSET_DIRECTORY = Path(__file__).resolve().parent / "assets" / "startup"
LOGO_PATH = ASSET_DIRECTORY / "sir_loader_logo.png"

MINIMUM_VISIBLE_SECONDS = 2.4
MAXIMUM_VISIBLE_SECONDS = 12.0
FADE_IN_SECONDS = 0.75
FADE_OUT_SECONDS = 0.65
PULSE_DOWN_SECONDS = 0.70
PULSE_UP_SECONDS = 0.80
PULSE_PAUSE_SECONDS = 0.15
LOGO_ASPECT = 520.0 / 96.0


class StartupLoader(FloatLayout):
    """Fade and gently pulse until the dashboard reports that it is ready."""

    __events__ = ("on_complete",)

    logo_opacity = NumericProperty(0.0)
    logo_scale = NumericProperty(0.94)
    glow_opacity = NumericProperty(0.0)
    glow_scale = NumericProperty(1.0)
    dashboard_ready = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.minimum_time_elapsed = False
        self.finishing = False
        self.pulse_event = None

        with self.canvas.before:
            Color(0, 0, 0, 1)
            self.black_background = Rectangle(pos=self.pos, size=self.size)

        # A faint, slightly enlarged copy creates a restrained red halo. It
        # pulses with the emblem without introducing any detached scan lines.
        self.glow_logo = Image(
            source=str(LOGO_PATH),
            fit_mode="fill",
            mipmap=True,
            opacity=0,
            color=(1.0, 0.20, 0.20, 1.0),
            size_hint=(None, None),
        )
        self.add_widget(self.glow_logo)

        self.logo = Image(
            source=str(LOGO_PATH),
            fit_mode="fill",
            mipmap=True,
            opacity=0,
            size_hint=(None, None),
        )
        self.add_widget(self.logo)

        self.bind(
            pos=self.update_layout,
            size=self.update_layout,
            logo_opacity=self.update_opacity,
            logo_scale=self.update_layout,
            glow_opacity=self.update_opacity,
            glow_scale=self.update_layout,
        )
        self.update_layout()

        Clock.schedule_once(self.begin, 0)
        Clock.schedule_once(
            self.allow_finish,
            MINIMUM_VISIBLE_SECONDS,
        )
        # A damaged Civic frame set must not trap the user on the loader.
        Clock.schedule_once(
            self.mark_ready,
            MAXIMUM_VISIBLE_SECONDS,
        )

    def update_opacity(self, *_args):
        self.logo.opacity = self.logo_opacity
        self.glow_logo.opacity = self.glow_opacity

    def update_layout(self, *_args):
        self.black_background.pos = self.pos
        self.black_background.size = self.size

        base_width = min(self.width * 0.72, self.height * 1.18)
        logo_width = base_width * self.logo_scale
        logo_height = logo_width / LOGO_ASPECT
        logo_x = self.center_x - logo_width / 2.0
        logo_y = self.center_y - logo_height / 2.0
        self.logo.pos = (logo_x, logo_y)
        self.logo.size = (logo_width, logo_height)

        glow_width = base_width * self.glow_scale
        glow_height = glow_width / LOGO_ASPECT
        self.glow_logo.pos = (
            self.center_x - glow_width / 2.0,
            self.center_y - glow_height / 2.0,
        )
        self.glow_logo.size = (glow_width, glow_height)

    def begin(self, _dt):
        Animation.cancel_all(self)
        Animation(
            logo_opacity=1.0,
            logo_scale=1.0,
            glow_opacity=0.10,
            glow_scale=1.015,
            duration=FADE_IN_SECONDS,
            transition="out_cubic",
        ).start(self)
        Clock.schedule_once(self.start_pulse, FADE_IN_SECONDS)

    def start_pulse(self, _dt=0):
        if self.finishing:
            return
        pulse = Animation(
            logo_opacity=0.82,
            glow_opacity=0.25,
            glow_scale=1.045,
            duration=PULSE_DOWN_SECONDS,
            transition="in_out_sine",
        ) + Animation(
            logo_opacity=1.0,
            glow_opacity=0.10,
            glow_scale=1.015,
            duration=PULSE_UP_SECONDS,
            transition="in_out_sine",
        )
        pulse.bind(on_complete=self.schedule_next_pulse)
        pulse.start(self)

    def schedule_next_pulse(self, *_args):
        if self.finishing:
            return
        self.pulse_event = Clock.schedule_once(
            self.start_pulse,
            PULSE_PAUSE_SECONDS,
        )

    def allow_finish(self, _dt):
        self.minimum_time_elapsed = True
        self.finish_if_ready()

    def mark_ready(self, _dt=0):
        self.dashboard_ready = True
        self.finish_if_ready()

    def finish_if_ready(self):
        if (
            self.finishing
            or not self.dashboard_ready
            or not self.minimum_time_elapsed
        ):
            return
        self.finishing = True
        if self.pulse_event is not None:
            self.pulse_event.cancel()
            self.pulse_event = None
        Animation.cancel_all(self)
        fade = Animation(
            opacity=0.0,
            duration=FADE_OUT_SECONDS,
            transition="in_out_quad",
        )
        fade.bind(on_complete=lambda *_args: self.dispatch("on_complete"))
        fade.start(self)

    def on_complete(self):
        """Dispatched after the dashboard has been revealed."""


class DashboardWithStartupLoader(FloatLayout):
    """Keep the loader above the live dashboard until Civic rotation starts."""

    def __init__(self, dashboard_factory, **kwargs):
        super().__init__(**kwargs)
        self.dashboard = dashboard_factory()
        self.loader = StartupLoader()
        self.add_widget(self.dashboard)
        self.add_widget(self.loader)
        self.loader.bind(on_complete=self.remove_loader)
        Clock.schedule_interval(self.check_dashboard_ready, 0.10)

    def check_dashboard_ready(self, _dt):
        dashboard = getattr(self.dashboard, "dashboard", None)
        civic_player = getattr(dashboard, "civic_player", None)
        if (
            civic_player is not None
            and civic_player.rotation_started_at is not None
        ):
            self.loader.mark_ready()
            return False
        return True

    def remove_loader(self, *_args):
        if self.loader.parent is self:
            self.remove_widget(self.loader)
