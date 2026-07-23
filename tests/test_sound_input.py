import os
import unittest
from unittest.mock import patch

from sound_input import (
    DEFAULT_GPIO_NAME,
    DEFAULT_SOUND_INPUT_MODE,
    BeatEnvelope,
    DigitalSoundInput,
    microphone_bar_targets,
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
    def test_default_input_uses_the_separate_gpio22_pin(self):
        self.assertEqual(DEFAULT_GPIO_NAME, "D22")

    def test_silence_keeps_only_the_baseline(self):
        targets = microphone_bar_targets(0.0, 17, 0.0)

        self.assertEqual(targets, [0.04] * 17)

    def test_real_energy_drives_a_bounded_decorative_profile(self):
        quiet = microphone_bar_targets(0.1, 17, 1.2)
        loud = microphone_bar_targets(0.9, 17, 1.2)

        self.assertTrue(all(0.04 <= value <= 1.0 for value in loud))
        self.assertTrue(all(high > low for low, high in zip(quiet, loud)))
        self.assertGreater(len(set(round(value, 3) for value in loud)), 4)

    def test_invalid_bar_count_is_rejected(self):
        with self.assertRaises(ValueError):
            microphone_bar_targets(0.5, 0, 0.0)


class SoundInputModeTest(unittest.TestCase):
    def test_simulation_is_the_safe_default(self):
        self.assertEqual(DEFAULT_SOUND_INPUT_MODE, "simulate")
        with patch.dict(os.environ, {}, clear=True):
            sound_input = DigitalSoundInput()

        self.assertFalse(sound_input.is_live)
        self.assertEqual(sound_input.status_text, "SIMULATED INPUT")

    def test_gpio_mode_can_still_be_selected_explicitly(self):
        sound_input = DigitalSoundInput(
            source_mode="gpio",
            reader=lambda: True,
        )
        try:
            self.assertTrue(sound_input.is_live)
            self.assertEqual(sound_input.status_text, "SOUND // LIVE")
        finally:
            sound_input.close()


if __name__ == "__main__":
    unittest.main()
