#!/usr/bin/env python3
"""Test and configure the Cyberdash USB microphone from the terminal."""

import argparse
import sys
import time

from sound_input import (
    DEFAULT_AUDIO_SETTINGS,
    UsbAudioInput,
    load_audio_settings,
    save_audio_settings,
)


LEVEL_CHARACTERS = " .:-=+*#%@"


def parser():
    command = argparse.ArgumentParser(
        description="Test the USB microphone and tune visualizer sensitivity."
    )
    command.add_argument(
        "--device",
        help="Audio device number or part of its displayed name.",
    )
    command.add_argument(
        "--sensitivity",
        type=float,
        help="Visualizer sensitivity from 0.1 to 8.0.",
    )
    command.add_argument(
        "--noise-gate",
        type=float,
        help="Ignore quieter input; normally 0.003 to 0.020.",
    )
    command.add_argument(
        "--save",
        action="store_true",
        help="Save these settings for dashboard startup.",
    )
    return command


def render_levels(values):
    maximum_index = len(LEVEL_CHARACTERS) - 1
    return "".join(
        LEVEL_CHARACTERS[
            max(0, min(maximum_index, round(value * maximum_index)))
        ]
        for value in values
    )


def main(argv=None):
    arguments = parser().parse_args(argv)
    settings = load_audio_settings()
    settings["mode"] = "usb"
    if arguments.device is not None:
        settings["device"] = arguments.device
    if arguments.sensitivity is not None:
        settings["sensitivity"] = arguments.sensitivity
    if arguments.noise_gate is not None:
        settings["noise_gate"] = arguments.noise_gate

    microphone = UsbAudioInput(settings=settings)
    if not microphone.is_live:
        print("USB microphone could not be opened.")
        print(f"Reason: {microphone.error}")
        print("Check the USB connection and run: arecord -l")
        return 1

    if arguments.save:
        saved_path = save_audio_settings(settings)
        print(f"Saved dashboard settings: {saved_path}")

    print(f"Microphone: {microphone.device_name}")
    print(f"Sample rate: {microphone.sample_rate:.0f} Hz")
    print(
        "Sensitivity: "
        f"{settings.get('sensitivity', DEFAULT_AUDIO_SETTINGS['sensitivity'])}"
    )
    print(f"Noise gate: {settings['noise_gate']}")
    print("Play music near the microphone. Press Ctrl+C to stop.")

    try:
        while True:
            levels = microphone.bar_targets(17)
            print(
                "\rBASS [" + render_levels(levels) + "] TREBLE",
                end="",
                flush=True,
            )
            time.sleep(0.08)
    except KeyboardInterrupt:
        print()
    finally:
        microphone.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
