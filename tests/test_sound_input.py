import json
import math
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np

from sound_input import (
    DEFAULT_AUDIO_LATENCY,
    DEFAULT_BLOCK_SIZE,
    DEFAULT_CALLBACK_TIMEOUT_SECONDS,
    DEFAULT_GPIO_NAME,
    DEFAULT_SOUND_INPUT_MODE,
    BeatEnvelope,
    DigitalSoundInput,
    ResilientSoundInput,
    SimulatedSoundInput,
    UsbAudioInput,
    create_sound_input,
    fft_band_levels,
    frequency_band_edges,
    load_audio_settings,
    microphone_bar_targets,
    select_input_device,
)


class BeatEnvelopeTest(unittest.TestCase):
    def test_trigger_attacks_and_then_decays(self):
        envelope = BeatEnvelope(attack=0.5, release_seconds=0.25)

        self.assertEqual(envelope.sample(False, now=1.0), 0.0)
        attacked = envelope.sample(True, now=1.01)
        decayed = envelope.sample(False, now=1.51)

        self.assertGreaterEqual(attacked, 0.5)
        self.assertLess(decayed, attacked)
        self.assertGreaterEqual(decayed, 0.0)

    def test_invalid_settings_are_rejected(self):
        with self.assertRaises(ValueError):
            BeatEnvelope(attack=0.0)
        with self.assertRaises(ValueError):
            BeatEnvelope(attack=1.1)
        with self.assertRaises(ValueError):
            BeatEnvelope(release_seconds=0.0)


class MicrophoneBarTargetTest(unittest.TestCase):
    def test_default_gpio_uses_the_separate_gpio22_pin(self):
        self.assertEqual(DEFAULT_GPIO_NAME, "D22")

    def test_silence_keeps_only_the_baseline(self):
        targets = microphone_bar_targets(0.0, 17, 0.0)

        self.assertEqual(targets, [0.04] * 17)

    def test_real_gpio_energy_drives_a_bounded_decorative_profile(self):
        quiet = microphone_bar_targets(0.1, 17, 1.2)
        loud = microphone_bar_targets(0.9, 17, 1.2)

        self.assertTrue(all(0.04 <= value <= 1.0 for value in loud))
        self.assertTrue(all(high > low for low, high in zip(quiet, loud)))
        self.assertGreater(len(set(round(value, 3) for value in loud)), 4)

    def test_invalid_bar_count_is_rejected(self):
        with self.assertRaises(ValueError):
            microphone_bar_targets(0.5, 0, 0.0)


class SpectrumTest(unittest.TestCase):
    def test_frequency_edges_are_logarithmic_and_nyquist_safe(self):
        edges = frequency_band_edges(16000, 17, 55, 10000)

        self.assertEqual(len(edges), 18)
        self.assertGreaterEqual(edges[0], 55)
        self.assertLessEqual(edges[-1], 8000 * 0.96)
        ratios = edges[1:] / edges[:-1]
        self.assertTrue(np.allclose(ratios, ratios[0]))

    def test_bass_and_treble_tones_peak_in_different_bands(self):
        sample_rate = 44100
        times = np.arange(4096) / sample_rate
        bass = 0.12 * np.sin(2 * math.pi * 110 * times)
        treble = 0.12 * np.sin(2 * math.pi * 4200 * times)

        bass_levels = fft_band_levels(bass, sample_rate)
        treble_levels = fft_band_levels(treble, sample_rate)

        self.assertLess(int(np.argmax(bass_levels)), 6)
        self.assertGreater(int(np.argmax(treble_levels)), 11)
        self.assertGreater(float(np.max(bass_levels)), 0.75)
        self.assertGreater(float(np.max(treble_levels)), 0.65)

    def test_noise_gate_keeps_quiet_input_at_baseline(self):
        samples = np.full(2048, 0.0005, dtype=np.float32)

        levels = fft_band_levels(
            samples,
            44100,
            sensitivity=1.0,
            noise_gate=0.01,
        )

        self.assertTrue(np.allclose(levels, 0.04))


class FakeDefaultDevice:
    device = (0, 1)


class FakeSoundDevice:
    default = FakeDefaultDevice()

    @staticmethod
    def query_devices():
        return [
            {
                "name": "Built-in Output",
                "max_input_channels": 0,
                "default_samplerate": 48000,
            },
            {
                "name": "Built-in Microphone",
                "max_input_channels": 1,
                "default_samplerate": 48000,
            },
            {
                "name": "USB PnP Sound Device",
                "max_input_channels": 1,
                "default_samplerate": 44100,
            },
        ]


class NoUsbSoundDevice:
    default = FakeDefaultDevice()

    @staticmethod
    def query_devices():
        return [
            {
                "name": "Built-in Microphone",
                "max_input_channels": 1,
                "default_samplerate": 48000,
            }
        ]


class FakeStream:
    def __init__(self, **kwargs):
        self.options = kwargs
        self.callback = kwargs["callback"]
        self.sample_rate = kwargs["samplerate"]
        self.active = True
        self.aborted = False
        self.stopped = False
        self.closed = False

    def start(self):
        times = np.arange(2048) / self.sample_rate
        samples = (0.12 * np.sin(2 * math.pi * 440 * times)).reshape(-1, 1)
        self.callback(samples, len(samples), None, None)

    def stop(self):
        self.stopped = True

    def abort(self):
        self.aborted = True
        self.active = False

    def close(self):
        self.closed = True


class ActiveStateTrapStream:
    """Fail if dashboard health checks cross into PortAudio state."""

    def __init__(self, **kwargs):
        self.callback = kwargs["callback"]
        self.sample_rate = kwargs["samplerate"]
        self.aborted = False
        self.closed = False

    @property
    def active(self):
        raise AssertionError("PortAudio active state must not be queried")

    def start(self):
        timeline = np.arange(4096, dtype=np.float32) / self.sample_rate
        signal = 0.8 * np.sin(2.0 * math.pi * 440.0 * timeline)
        self.callback(signal.reshape(-1, 1), len(signal), None, None)

    def abort(self):
        self.aborted = True

    def close(self):
        self.closed = True


class UsbInputTest(unittest.TestCase):
    def test_auto_selection_prefers_usb_microphone(self):
        index, device = select_input_device(FakeSoundDevice())

        self.assertEqual(index, 2)
        self.assertEqual(device["name"], "USB PnP Sound Device")

    def test_device_can_be_selected_by_name(self):
        index, _device = select_input_device(
            FakeSoundDevice(),
            "built-in microphone",
        )

        self.assertEqual(index, 1)

    def test_builtin_microphone_is_not_selected_as_usb_by_accident(self):
        with self.assertRaisesRegex(RuntimeError, "no USB microphone"):
            select_input_device(NoUsbSoundDevice())

    def test_usb_stream_produces_real_frequency_bars(self):
        microphone = UsbAudioInput(
            settings={"mode": "usb", "sensitivity": 1.8},
            sounddevice_module=FakeSoundDevice(),
            stream_factory=FakeStream,
        )
        try:
            deadline = time.monotonic() + 1.0
            while (
                max(microphone.bar_targets(17)) <= 0.5
                and time.monotonic() < deadline
            ):
                time.sleep(0.01)
            self.assertTrue(microphone.is_live)
            self.assertEqual(microphone.status_text, "USB MIC // LIVE")
            self.assertEqual(microphone.device_name, "USB PnP Sound Device")
            self.assertEqual(len(microphone.bar_targets(17)), 17)
            self.assertGreater(max(microphone.bar_targets(17)), 0.5)
            self.assertEqual(
                microphone._stream.options["blocksize"],
                DEFAULT_BLOCK_SIZE,
            )
            self.assertEqual(
                microphone._stream.options["latency"],
                "high",
            )
        finally:
            microphone.close()

        self.assertTrue(microphone._stream is None)
        self.assertIsNone(microphone._processing_thread)

    def test_callback_timeout_tolerates_a_busy_dashboard(self):
        microphone = UsbAudioInput(
            settings={"mode": "usb", "sensitivity": 1.8},
            sounddevice_module=FakeSoundDevice(),
            stream_factory=FakeStream,
        )
        try:
            callback_time = microphone._last_callback_time
            with patch(
                "sound_input.time.monotonic",
                return_value=(
                    callback_time + DEFAULT_CALLBACK_TIMEOUT_SECONDS - 0.1
                ),
            ):
                self.assertTrue(microphone.is_live)
            with patch(
                "sound_input.time.monotonic",
                return_value=(
                    callback_time + DEFAULT_CALLBACK_TIMEOUT_SECONDS + 0.1
                ),
            ):
                self.assertFalse(microphone.is_live)
        finally:
            microphone.close()

        self.assertEqual(DEFAULT_BLOCK_SIZE, 2048)
        self.assertEqual(DEFAULT_AUDIO_LATENCY, "high")

    def test_live_health_check_never_queries_portaudio_active_state(self):
        microphone = UsbAudioInput(
            settings={"mode": "usb", "sensitivity": 1.8},
            sounddevice_module=FakeSoundDevice(),
            stream_factory=ActiveStateTrapStream,
        )
        try:
            self.assertTrue(microphone.is_live)
            self.assertEqual(microphone.status_text, "USB MIC // LIVE")
        finally:
            microphone.close()


class ControlledProvider:
    def __init__(self, name, events, live=True, error=None):
        self.name = name
        self.events = events
        self.is_live = live
        self.error = error

    @property
    def status_text(self):
        return f"{self.name} LIVE" if self.is_live else "SIMULATED INPUT"

    def bar_targets(self, bar_count, phase=0.0):
        return [0.5] * bar_count

    def close(self):
        self.events.append(f"close:{self.name}")
        self.is_live = False


class ResilientSoundInputTest(unittest.TestCase):
    def test_dead_stream_is_closed_before_replacement_is_opened(self):
        events = []
        providers = [
            ControlledProvider("first", events),
            ControlledProvider("second", events),
        ]

        def factory():
            provider = providers.pop(0)
            events.append(f"create:{provider.name}")
            return provider

        manager = ResilientSoundInput(
            settings={"mode": "usb"},
            provider_factory=factory,
            start_worker=False,
        )
        try:
            self.assertTrue(manager.attempt_reconnect())
            self.assertEqual(manager.status_text, "first LIVE")
            self.assertEqual(manager.bar_targets(17), [0.5] * 17)

            manager._provider_snapshot().is_live = False
            self.assertTrue(manager.attempt_reconnect())
            self.assertEqual(manager.status_text, "second LIVE")
            self.assertLess(
                events.index("close:first"),
                events.index("create:second"),
            )
        finally:
            manager.close()

    def test_unavailable_device_reports_reconnecting_without_blocking(self):
        events = []
        unavailable = ControlledProvider(
            "missing",
            events,
            live=False,
            error="device busy",
        )
        manager = ResilientSoundInput(
            settings={"mode": "usb"},
            provider_factory=lambda: unavailable,
            start_worker=False,
        )
        try:
            self.assertFalse(manager.attempt_reconnect())
            self.assertFalse(manager.is_live)
            self.assertEqual(manager.status_text, "USB MIC // RETRY")
            self.assertEqual(manager.bar_targets(17), [0.04] * 17)
            self.assertEqual(manager.error, "device busy")
        finally:
            manager.close()


class SoundInputModeTest(unittest.TestCase):
    def test_usb_is_the_default_with_simulation_as_fallback(self):
        self.assertEqual(DEFAULT_SOUND_INPUT_MODE, "usb")
        unavailable = type(
            "UnavailableUsb",
            (),
            {
                "is_live": False,
                "error": "not connected",
                "close": lambda self: None,
            },
        )()
        with patch("sound_input.UsbAudioInput", return_value=unavailable):
            sound_input = create_sound_input(settings={"mode": "usb"})

        self.assertIsInstance(sound_input, SimulatedSoundInput)
        self.assertEqual(sound_input.status_text, "SIMULATED INPUT")
        self.assertIn("not connected", sound_input.error)

    def test_gpio_mode_can_still_be_selected_explicitly(self):
        sound_input = DigitalSoundInput(reader=lambda: True)
        try:
            self.assertTrue(sound_input.is_live)
            self.assertEqual(sound_input.status_text, "GPIO MIC // LIVE")
        finally:
            sound_input.close()

    def test_local_settings_and_environment_override_are_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audio_settings.json"
            path.write_text(
                json.dumps(
                    {
                        "mode": "simulate",
                        "sensitivity": 2.5,
                        "noise_gate": 0.01,
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {"CYBERDASH_MIC_SENSITIVITY": "3.25"},
                clear=True,
            ):
                settings = load_audio_settings(path)

        self.assertEqual(settings["mode"], "simulate")
        self.assertEqual(settings["sensitivity"], 3.25)
        self.assertEqual(settings["noise_gate"], 0.01)


if __name__ == "__main__":
    unittest.main()
