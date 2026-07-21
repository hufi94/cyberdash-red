#!/usr/bin/env python3
"""Standalone test for the exact Civic player used by dashboard_v2.py."""

from kivy.config import Config

Config.set("graphics", "width", "400")
Config.set("graphics", "height", "260")
Config.set("graphics", "resizable", "0")
Config.set("graphics", "fullscreen", "0")
Config.set("kivy", "exit_on_escape", "1")

from kivy.app import App
from kivy.core.window import Window

from civic_360_widget import Civic360Player, ROTATION_SECONDS


BACKGROUND = (0.025, 0.025, 0.03, 1)


class CivicTestApp(App):
    title = "Approved Civic 360 Test"

    def build(self):
        Window.clearcolor = BACKGROUND
        return Civic360Player(rotation_seconds=ROTATION_SECONDS)


if __name__ == "__main__":
    CivicTestApp().run()
