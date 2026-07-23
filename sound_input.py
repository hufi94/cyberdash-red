#!/usr/bin/env python3
"""Sound-trigger input for the four-pin AO/G/+/DO microphone module.

The Raspberry Pi test setup uses only the module's digital ``DO`` output.  It
cannot provide real frequency bands, but it can make the existing visualizer
react to actual music and beat threshold crossings.  The blue potentiometer on
the module controls that threshold.
"""

import math
import os
import threading
import time


DEFAULT_GPIO_NAME = "D22"
DEFAULT_SAMPLE_INTERVAL = 0.002
DEFAULT_ACTIVE_LOW = True
DEFAULT_SOUND_INPUT_MODE = "simulate"


def environment_flag(name, default):
    """Read a conventional true/false environment flag."""

    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


class BeatEnvelope:
    """Convert digital sound triggers into a smooth attack/release level."""

    def __init__(self, attack=0.34, release_seconds=0.24):
        if not 0.0 < attack <= 1.0:
            raise ValueError("attack must be greater than zero and at most one")
        if release_seconds <= 0.0:
            raise ValueError("release_seconds must be greater than zero")
        self.attack = attack
        self.release_seconds = release_seconds
        self.level = 0.0
        self.last_sample_time = None

    def sample(self, triggered, now=None):
        """Advance the envelope and return a normalized value from 0 to 1."""

        if now is None:
            now = time.monotonic()
        if self.last_sample_time is None:
            elapsed = 0.0
        else:
            elapsed = max(0.0, now - self.last_sample_time)
        self.last_sample_time = now

        if elapsed:
            self.level *= math.exp(-elapsed / self.release_seconds)
        if triggered:
            self.level += (1.0 - self.level) * self.attack
        self.level = max(0.0, min(1.0, self.level))
        return self.level


def microphone_bar_targets(level, bar_count, phase):
    """Create a stable decorative bar profile driven by a real sound level.

    ``DO`` supplies one threshold bit rather than audio samples, so these are
    intentionally not described as frequency bins.  Their overall energy is
    real; the across-screen variation keeps the dashboard visually useful.
    """

    if bar_count <= 0:
        raise ValueError("bar_count must be greater than zero")
    energy = max(0.0, min(1.0, float(level)))
    targets = []
    for index in range(bar_count):
        position = index / max(1, bar_count - 1)
        broad_wave = (math.sin(phase + index * 0.78) + 1.0) / 2.0
        fine_wave = (math.sin(phase * 0.53 - index * 1.41) + 1.0) / 2.0
        center_weight = 1.0 - 0.24 * abs(position - 0.42)
        shape = (0.28 + broad_wave * 0.47 + fine_wave * 0.25) * center_weight
        targets.append(max(0.04, min(1.0, 0.04 + energy * shape)))
    return targets


class DigitalSoundInput:
    """Sample the module's active-low DO output on a background thread."""

    def __init__(
        self,
        gpio_name=None,
        active_low=None,
        sample_interval=DEFAULT_SAMPLE_INTERVAL,
        reader=None,
        source_mode=None,
    ):
        self.gpio_name = gpio_name or os.environ.get(
            "CYBERDASH_MIC_GPIO",
            DEFAULT_GPIO_NAME,
        )
        self.active_low = (
            environment_flag("CYBERDASH_MIC_ACTIVE_LOW", DEFAULT_ACTIVE_LOW)
            if active_low is None
            else bool(active_low)
        )
        self.sample_interval = max(0.001, float(sample_interval))
        self.envelope = BeatEnvelope()
        self._level = 0.0
        self._level_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self._digital_line = None
        self._reader = reader
        self.is_live = False
        self.error = None

        self.source_mode = (
            source_mode
            or os.environ.get(
                "CYBERDASH_SOUND_INPUT",
                DEFAULT_SOUND_INPUT_MODE,
            )
        ).strip().lower()
        if self.source_mode != "gpio":
            self.error = (
                "GPIO sound input disabled; "
                "set CYBERDASH_SOUND_INPUT=gpio to enable it"
            )
            return

        try:
            if self._reader is None:
                self._reader = self._open_gpio_reader()
            self.is_live = True
            self._thread = threading.Thread(
                target=self._sample_loop,
                name="cyberdash-sound-input",
                daemon=True,
            )
            self._thread.start()
        except Exception as error:
            self.error = str(error)
            self.is_live = False
            print(f"Microphone GPIO input unavailable: {error}")

    @property
    def level(self):
        with self._level_lock:
            return self._level

    @property
    def status_text(self):
        if self.is_live:
            return "SOUND // LIVE"
        return "SIMULATED INPUT"

    def _open_gpio_reader(self):
        import board
        import digitalio

        pin = getattr(board, self.gpio_name)
        self._digital_line = digitalio.DigitalInOut(pin)
        self._digital_line.direction = digitalio.Direction.INPUT
        # The module's LM393 comparator normally pulls DO low on a trigger.
        # Pull-up also leaves the input in a safe, quiet state if DO is removed.
        self._digital_line.pull = digitalio.Pull.UP
        return lambda: bool(self._digital_line.value)

    def _sample_loop(self):
        while not self._stop_event.is_set():
            try:
                raw_value = bool(self._reader())
                triggered = not raw_value if self.active_low else raw_value
                level = self.envelope.sample(triggered)
                with self._level_lock:
                    self._level = level
            except Exception as error:
                self.error = str(error)
                self.is_live = False
                print(f"Microphone GPIO reading stopped: {error}")
                return
            self._stop_event.wait(self.sample_interval)

    def close(self):
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=0.25)
        if self._digital_line is not None:
            self._digital_line.deinit()
            self._digital_line = None
