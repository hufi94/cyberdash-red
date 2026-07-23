import unittest

from sound_input import (
    DEFAULT_GPIO_NAME,
    BeatEnvelope,
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


if __name__ == "__main__":
    unittest.main()
