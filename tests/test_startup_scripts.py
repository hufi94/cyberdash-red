import os
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


class StartupScriptTests(unittest.TestCase):
    def test_startup_scripts_have_valid_bash_syntax(self):
        for name in (
            "start_dashboard.sh",
            "install_autostart.sh",
            "disable_autostart.sh",
            "install_kiosk_startup.sh",
            "disable_kiosk_startup.sh",
            "start_dashboard_early.sh",
            "configure_displays.sh",
            "install_early_startup.sh",
            "disable_early_startup.sh",
        ):
            with self.subTest(script=name):
                subprocess.run(
                    ["bash", "-n", str(PROJECT / name)],
                    check=True,
                    capture_output=True,
                    text=True,
                )

    def test_dashboard_launcher_has_no_default_delay(self):
        source = (PROJECT / "start_dashboard.sh").read_text(encoding="utf-8")
        self.assertIn('CYBERDASH_START_DELAY:-0', source)
        self.assertNotIn('CYBERDASH_START_DELAY:-2', source)

    def test_kiosk_installer_is_reversible(self):
        installer = (PROJECT / "install_kiosk_startup.sh").read_text(
            encoding="utf-8"
        )
        disabler = (PROJECT / "disable_kiosk_startup.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("original-session-autostart", installer)
        self.assertIn("normal-autostart.desktop", installer)
        self.assertIn("original-session-autostart", disabler)
        self.assertIn("normal-autostart.desktop", disabler)
        self.assertIn("pgrep -x openbox", installer)
        self.assertIn("lxsession/${lxde_profile}/autostart", installer)

    def _assert_kiosk_round_trip(self, session_kind, auto_detect=False):
        with tempfile.TemporaryDirectory() as temporary_home:
            home = Path(temporary_home)
            config_home = home / ".config"
            desktop_dir = home / ".config" / "autostart"
            desktop_dir.mkdir(parents=True)

            if session_kind == "labwc":
                session_autostart = config_home / "labwc" / "autostart"
            else:
                session_autostart = (
                    config_home / "lxsession" / "LXDE-pi" / "autostart"
                )
            session_autostart.parent.mkdir(parents=True)

            original_session = "original-desktop\n"
            original_desktop_entry = "[Desktop Entry]\nName=Original\n"
            session_autostart.write_text(
                original_session,
                encoding="utf-8",
            )
            (desktop_dir / "cyberdash-red.desktop").write_text(
                original_desktop_entry,
                encoding="utf-8",
            )

            environment = os.environ.copy()
            environment["HOME"] = str(home)
            environment["XDG_CONFIG_HOME"] = str(config_home)
            if auto_detect:
                environment.pop("CYBERDASH_SESSION_KIND", None)
                environment["XDG_CURRENT_DESKTOP"] = "LXDE"
            else:
                environment["CYBERDASH_SESSION_KIND"] = session_kind
            environment["CYBERDASH_LXDE_PROFILE"] = "LXDE-pi"

            subprocess.run(
                [str(PROJECT / "install_kiosk_startup.sh")],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )

            generated = session_autostart.read_text(encoding="utf-8")
            self.assertIn("run-dashboard-session.sh", generated)
            self.assertNotIn("original-desktop", generated)
            self.assertFalse((desktop_dir / "cyberdash-red.desktop").exists())

            runner = (
                config_home
                / "cyberdash-red-kiosk"
                / "run-dashboard-session.sh"
            ).read_text(encoding="utf-8")
            self.assertIn("CYBERDASH_START_DELAY=0", runner)
            self.assertIn("xsetroot -solid black", runner)

            subprocess.run(
                [str(PROJECT / "disable_kiosk_startup.sh")],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertEqual(
                session_autostart.read_text(encoding="utf-8"),
                original_session,
            )
            self.assertEqual(
                (desktop_dir / "cyberdash-red.desktop").read_text(
                    encoding="utf-8"
                ),
                original_desktop_entry,
            )

    def test_labwc_kiosk_install_and_disable_restore_original_session(self):
        self._assert_kiosk_round_trip("labwc")

    def test_lxde_kiosk_install_and_disable_restore_original_session(self):
        self._assert_kiosk_round_trip("lxde", auto_detect=True)

    def test_fullscreen_dashboard_hides_pointer(self):
        source = (PROJECT / "dashboard_v2.py").read_text(encoding="utf-8")
        self.assertIn("Window.show_cursor = WINDOWED_MODE", source)

    def test_early_launcher_waits_for_x_and_runs_v2_directly(self):
        source = (PROJECT / "start_dashboard_early.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("attempt <= 150", source)
        self.assertIn("xsetroot -solid black", source)
        self.assertIn('display_profile="${project_dir}/configure_displays.sh"', source)
        self.assertIn('if ! "${display_profile}"', source)
        self.assertIn('dashboard_v2.py"', source)
        self.assertNotIn("loader.py", source)

    def test_display_profile_separates_dashboard_and_work_monitor(self):
        source = (PROJECT / "configure_displays.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('small_mode="${CYBERDASH_SMALL_MODE:-640x480}"', source)
        self.assertIn('work_mode="${CYBERDASH_WORK_MODE:-1920x1080}"', source)
        self.assertIn("--rotate inverted", source)
        self.assertIn("--rotate normal", source)
        self.assertIn("--primary", source)
        self.assertIn('--right-of "${small_output}"', source)

    def test_display_profile_applies_expected_xrandr_arguments(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            fake_xrandr = temporary_path / "xrandr"
            argument_log = temporary_path / "arguments.txt"
            fake_xrandr.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--query" ]]; then
    printf '%s\n' \\
        'HDMI-1 connected primary 640x480+0+0 normal' \\
        '   640x480      60.00*' \\
        'HDMI-2 connected 1920x1080+640+0 normal' \\
        '   1920x1080    60.00*'
    exit 0
fi
printf '%s\n' "$*" > "${XRANDR_ARGUMENT_LOG}"
""",
                encoding="utf-8",
            )
            fake_xrandr.chmod(0o755)
            environment = os.environ.copy()
            environment["CYBERDASH_XRANDR_BIN"] = str(fake_xrandr)
            environment["XRANDR_ARGUMENT_LOG"] = str(argument_log)

            subprocess.run(
                [str(PROJECT / "configure_displays.sh")],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )

            arguments = argument_log.read_text(encoding="utf-8")
            self.assertIn(
                "--output HDMI-1 --mode 640x480 --rotate inverted "
                "--primary --pos 0x0",
                arguments,
            )
            self.assertIn(
                "--output HDMI-2 --rotate normal --mode 1920x1080 "
                "--right-of HDMI-1",
                arguments,
            )

    def test_early_service_uses_the_proven_graphical_target(self):
        source = (PROJECT / "install_early_startup.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("Environment=DISPLAY=:0", source)
        self.assertIn("WantedBy=graphical.target", source)
        self.assertIn("start_dashboard_early.sh", source)
        self.assertIn('systemctl enable "${service_name}"', source)


if __name__ == "__main__":
    unittest.main()
