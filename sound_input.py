#!/usr/bin/env python3
"""Real USB audio and optional GPIO sound input for Cyberdash Red.

USB mode captures mono audio through PortAudio, divides it into logarithmic
frequency bands, and supplies normalized values to the Kivy visualizer. If the
microphone or audio library is unavailable, the dashboard continues with its
original simulated animation.
"""

import json
import math
import os
from pathlib import Path
import threading
import time

import numpy as np


DEFAULT_GPIO_NAME = "D22"
DEFAULT_SAMPLE_INTERVAL = 0.002
DEFAULT_ACTIVE_LOW = True
DEFAULT_SOUND_INPUT_MODE = "usb"
DEFAULT_BAR_COUNT = 17
DEFAULT_BLOCK_SIZE = 1024
DEFAULT_AUDIO_SETTINGS = {
    "mode": DEFAULT_SOUND_INPUT_MODE,
    "device": "",
    "sensitivity": 1.8,
    "noise_gate": 0.006,
    "minimum_frequency": 55.0,
    "maximum_frequency": 10000.0,
}
AUDIO_SETTINGS_PATH = Path(__file__).resolve().with_name("audio_settings.json")


def environment_flag(name, default):
    """Read a conventional true/false environment flag."""

    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _bounded_float(value, default, minimum, maximum):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(default)
    if not math.isfinite(number):
        number = float(default)
    return max(minimum, min(maximum, number))


def load_audio_settings(path=None):
    """Load local settings, then apply optional environment overrides."""

    settings = dict(DEFAULT_AUDIO_SETTINGS)
    settings_path = Path(
        path
        or os.environ.get("CYBERDASH_AUDIO_SETTINGS", AUDIO_SETTINGS_PATH)
    )
    if settings_path.exists():
        try:
            loaded = json.loads(settings_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                settings.update(loaded)
        except Exception as error:
            print(f"Audio settings ignored: {error}")

    environment_values = {
        "mode": os.environ.get("CYBERDASH_SOUND_INPUT"),
        "device": os.environ.get("CYBERDASH_MIC_DEVICE"),
        "sensitivity": os.environ.get("CYBERDASH_MIC_SENSITIVITY"),
        "noise_gate": os.environ.get("CYBERDASH_MIC_NOISE_GATE"),
        "minimum_frequency": os.environ.get("CYBERDASH_MIC_MIN_FREQUENCY"),
        "maximum_frequency": os.environ.get("CYBERDASH_MIC_MAX_FREQUENCY"),
    }
    for key, value in environment_values.items():
        if value is not None:
            settings[key] = value

    mode = str(settings.get("mode", DEFAULT_SOUND_INPUT_MODE)).strip().lower()
    if mode not in {"usb", "gpio", "simulate"}:
        mode = DEFAULT_SOUND_INPUT_MODE
    settings["mode"] = mode
    settings["device"] = str(settings.get("device", "")).strip()
    settings["sensitivity"] = _bounded_float(
        settings.get("sensitivity"),
        DEFAULT_AUDIO_SETTINGS["sensitivity"],
        0.1,
        8.0,
    )
    settings["noise_gate"] = _bounded_float(
        settings.get("noise_gate"),
        DEFAULT_AUDIO_SETTINGS["noise_gate"],
        0.0,
        0.25,
    )
    settings["minimum_frequency"] = _bounded_float(
        settings.get("minimum_frequency"),
        DEFAULT_AUDIO_SETTINGS["minimum_frequency"],
        20.0,
        1000.0,
    )
    settings["maximum_frequency"] = _bounded_float(
        settings.get("maximum_frequency"),
        DEFAULT_AUDIO_SETTINGS["maximum_frequency"],
        2000.0,
        20000.0,
    )
    if settings["maximum_frequency"] <= settings["minimum_frequency"]:
        settings["maximum_frequency"] = DEFAULT_AUDIO_SETTINGS[
            "maximum_frequency"
        ]
    return settings


def save_audio_settings(settings, path=None):
    """Write validated persistent settings used by dashboard startup."""

    merged = dict(load_audio_settings(path))
    merged.update(settings)
    validated = load_audio_settings_from_mapping(merged)
    settings_path = Path(path or AUDIO_SETTINGS_PATH)
    settings_path.write_text(
        json.dumps(validated, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return settings_path


def load_audio_settings_from_mapping(values):
    """Validate an in-memory settings mapping without reading a file."""

    settings = dict(DEFAULT_AUDIO_SETTINGS)
    settings.update(values)
    mode = str(settings.get("mode", DEFAULT_SOUND_INPUT_MODE)).strip().lower()
    settings["mode"] = mode if mode in {"usb", "gpio", "simulate"} else "usb"
    settings["device"] = str(settings.get("device", "")).strip()
    settings["sensitivity"] = _bounded_float(
        settings.get("sensitivity"), 1.8, 0.1, 8.0
    )
    settings["noise_gate"] = _bounded_float(
        settings.get("noise_gate"), 0.006, 0.0, 0.25
    )
    settings["minimum_frequency"] = _bounded_float(
        settings.get("minimum_frequency"), 55.0, 20.0, 1000.0
    )
    settings["maximum_frequency"] = _bounded_float(
        settings.get("maximum_frequency"), 10000.0, 2000.0, 20000.0
    )
    if settings["maximum_frequency"] <= settings["minimum_frequency"]:
        settings["maximum_frequency"] = 10000.0
    return settings


def frequency_band_edges(
    sample_rate,
    bar_count,
    minimum_frequency=55.0,
    maximum_frequency=10000.0,
):
    """Return logarithmic FFT band edges bounded by the Nyquist frequency."""

    if sample_rate <= 0:
        raise ValueError("sample_rate must be greater than zero")
    if bar_count <= 0:
        raise ValueError("bar_count must be greater than zero")
    nyquist = sample_rate / 2.0
    low = max(20.0, float(minimum_frequency))
    high = min(float(maximum_frequency), nyquist * 0.96)
    if high <= low:
        raise ValueError("frequency range is empty at this sample rate")
    return np.geomspace(low, high, bar_count + 1)


def fft_band_levels(
    samples,
    sample_rate,
    bar_count=DEFAULT_BAR_COUNT,
    sensitivity=1.8,
    noise_gate=0.006,
    minimum_frequency=55.0,
    maximum_frequency=10000.0,
):
    """Convert a mono audio block into normalized logarithmic spectrum bars."""

    values = np.asarray(samples, dtype=np.float32)
    if values.ndim > 1:
        values = np.mean(values, axis=1)
    values = values.reshape(-1)
    if values.size < 32:
        raise ValueError("at least 32 audio samples are required")
    values = np.nan_to_num(values, copy=False)
    values = values - float(np.mean(values))

    sensitivity = _bounded_float(sensitivity, 1.8, 0.1, 8.0)
    noise_gate = _bounded_float(noise_gate, 0.006, 0.0, 0.25)
    rms = float(np.sqrt(np.mean(np.square(values))))
    baseline = np.full(bar_count, 0.04, dtype=np.float32)
    if rms * sensitivity <= noise_gate:
        return baseline

    window = np.hanning(values.size).astype(np.float32)
    spectrum = np.abs(np.fft.rfft(values * window))
    spectrum *= sensitivity / max(float(np.sum(window)) / 2.0, 1.0)
    frequencies = np.fft.rfftfreq(values.size, d=1.0 / float(sample_rate))
    edges = frequency_band_edges(
        sample_rate,
        bar_count,
        minimum_frequency,
        maximum_frequency,
    )

    output = np.empty(bar_count, dtype=np.float32)
    for index, (lower, upper) in enumerate(zip(edges[:-1], edges[1:])):
        if index == bar_count - 1:
            mask = (frequencies >= lower) & (frequencies <= upper)
        else:
            mask = (frequencies >= lower) & (frequencies < upper)
        if not np.any(mask):
            output[index] = 0.04
            continue
        amplitude = float(np.sqrt(np.mean(np.square(spectrum[mask]))))
        decibels = 20.0 * math.log10(max(amplitude, 1e-8))
        normalized = (decibels + 68.0) / 50.0
        output[index] = max(0.04, min(1.0, normalized))
    return output


def _device_list(sounddevice_module):
    devices = sounddevice_module.query_devices()
    return [dict(device) for device in devices]


def select_input_device(sounddevice_module, requested=""):
    """Choose a requested device or the first USB microphone-like input."""

    devices = _device_list(sounddevice_module)
    input_devices = [
        (index, device)
        for index, device in enumerate(devices)
        if int(device.get("max_input_channels", 0)) > 0
    ]
    if not input_devices:
        raise RuntimeError("no audio input devices were found")

    requested = str(requested or "").strip()
    if requested:
        if requested.isdigit():
            index = int(requested)
            if any(candidate == index for candidate, _ in input_devices):
                return index, devices[index]
            raise RuntimeError(f"input device index {index} is unavailable")
        requested_lower = requested.lower()
        for index, device in input_devices:
            if requested_lower in str(device.get("name", "")).lower():
                return index, device
        raise RuntimeError(f"input device matching {requested!r} was not found")

    preferred_terms = ("millso", "usb pnp", "usb microphone", "usb audio", "usb")
    for term in preferred_terms:
        for index, device in input_devices:
            if term in str(device.get("name", "")).lower():
                return index, device

    raise RuntimeError(
        "no USB microphone was detected; set a device name explicitly "
        "if Linux uses an unusual name"
    )


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
        elapsed = (
            0.0
            if self.last_sample_time is None
            else max(0.0, now - self.last_sample_time)
        )
        self.last_sample_time = now
        if elapsed:
            self.level *= math.exp(-elapsed / self.release_seconds)
        if triggered:
            self.level += (1.0 - self.level) * self.attack
        self.level = max(0.0, min(1.0, self.level))
        return self.level


def microphone_bar_targets(level, bar_count, phase):
    """Create decorative bars from the legacy one-bit GPIO trigger."""

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


class SimulatedSoundInput:
    """Inactive input marker that leaves the Kivy simulation running."""

    def __init__(self, error=None):
        self.is_live = False
        self.error = error

    @property
    def status_text(self):
        return "SIMULATED INPUT"

    def bar_targets(self, bar_count, phase=0.0):
        return [0.04] * bar_count

    def close(self):
        return None


class UsbAudioInput:
    """Capture a USB microphone and expose real FFT frequency bands."""

    def __init__(
        self,
        bar_count=DEFAULT_BAR_COUNT,
        settings=None,
        sounddevice_module=None,
        stream_factory=None,
    ):
        self.settings = load_audio_settings_from_mapping(
            settings or load_audio_settings()
        )
        self.bar_count = int(bar_count)
        self._values = np.full(self.bar_count, 0.04, dtype=np.float32)
        self._values_lock = threading.Lock()
        self._stream = None
        self._is_live = False
        self._last_callback_time = None
        self.error = None
        self.last_stream_status = None
        self.device_index = None
        self.device_name = ""
        self.sample_rate = 0.0

        try:
            if sounddevice_module is None:
                import sounddevice as sounddevice_module
            self._sounddevice = sounddevice_module
            self.device_index, device = select_input_device(
                sounddevice_module,
                self.settings["device"],
            )
            self.device_name = str(device.get("name", self.device_index))
            self.sample_rate = float(device.get("default_samplerate") or 44100)
            factory = stream_factory or sounddevice_module.InputStream
            self._stream = factory(
                device=self.device_index,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=DEFAULT_BLOCK_SIZE,
                dtype="float32",
                latency="low",
                callback=self._audio_callback,
            )
            self._stream.start()
            self._is_live = True
            self._last_callback_time = time.monotonic()
            print(
                "USB microphone online: "
                f"{self.device_name} at {self.sample_rate:.0f} Hz"
            )
        except Exception as error:
            self.error = str(error)
            self._is_live = False
            self.close()

    @property
    def is_live(self):
        if not self._is_live or self._last_callback_time is None:
            return False
        return time.monotonic() - self._last_callback_time < 2.5

    @property
    def status_text(self):
        return "USB MIC // LIVE" if self.is_live else "SIMULATED INPUT"

    @property
    def level(self):
        with self._values_lock:
            return float(np.max(self._values))

    def bar_targets(self, bar_count, phase=0.0):
        with self._values_lock:
            values = self._values.copy()
        if bar_count == self.bar_count:
            return values.tolist()
        source_positions = np.linspace(0.0, 1.0, self.bar_count)
        target_positions = np.linspace(0.0, 1.0, bar_count)
        return np.interp(target_positions, source_positions, values).tolist()

    def _audio_callback(self, indata, _frames, _time_info, status):
        try:
            self._last_callback_time = time.monotonic()
            if status:
                self.last_stream_status = str(status)
            values = fft_band_levels(
                indata,
                self.sample_rate,
                self.bar_count,
                self.settings["sensitivity"],
                self.settings["noise_gate"],
                self.settings["minimum_frequency"],
                self.settings["maximum_frequency"],
            )
            with self._values_lock:
                self._values = values
        except Exception as error:
            self.error = str(error)

    def close(self):
        stream = self._stream
        self._stream = None
        self._is_live = False
        if stream is not None:
            try:
                stream.stop()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass


class DigitalSoundInput:
    """Sample the legacy module's active-low DO output."""

    def __init__(
        self,
        gpio_name=None,
        active_low=None,
        sample_interval=DEFAULT_SAMPLE_INTERVAL,
        reader=None,
    ):
        self.gpio_name = gpio_name or os.environ.get(
            "CYBERDASH_MIC_GPIO", DEFAULT_GPIO_NAME
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

    @property
    def level(self):
        with self._level_lock:
            return self._level

    @property
    def status_text(self):
        return "GPIO MIC // LIVE" if self.is_live else "SIMULATED INPUT"

    def bar_targets(self, bar_count, phase=0.0):
        return microphone_bar_targets(self.level, bar_count, phase)

    def _open_gpio_reader(self):
        import board
        import digitalio

        pin = getattr(board, self.gpio_name)
        self._digital_line = digitalio.DigitalInOut(pin)
        self._digital_line.direction = digitalio.Direction.INPUT
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
                return
            self._stop_event.wait(self.sample_interval)

    def close(self):
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=0.25)
        if self._digital_line is not None:
            self._digital_line.deinit()
            self._digital_line = None
        self.is_live = False


def create_sound_input(
    bar_count=DEFAULT_BAR_COUNT,
    settings=None,
    log_errors=True,
):
    """Create the configured input with a non-fatal simulation fallback."""

    resolved = load_audio_settings_from_mapping(
        settings or load_audio_settings()
    )
    mode = resolved["mode"]
    if mode == "simulate":
        return SimulatedSoundInput()
    if mode == "gpio":
        provider = DigitalSoundInput()
    else:
        provider = UsbAudioInput(bar_count=bar_count, settings=resolved)
    if provider.is_live:
        return provider
    error = provider.error or f"{mode} input did not start"
    provider.close()
    if log_errors:
        print(f"Audio input unavailable; using simulation: {error}")
    return SimulatedSoundInput(error=error)
