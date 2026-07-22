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
        self.assertIn("original-labwc-autostart", installer)
        self.assertIn("normal-autostart.desktop", installer)
        self.assertIn("original-labwc-autostart", disabler)
        self.assertIn("normal-autostart.desktop", disabler)

    def test_kiosk_install_and_disable_restore_the_original_session(self):
        with tempfile.TemporaryDirectory() as temporary_home:
            home = Path(temporary_home)
            fake_bin = home / "bin"
            labwc_dir = home / ".config" / "labwc"
            desktop_dir = home / ".config" / "autostart"
            fake_bin.mkdir()
            labwc_dir.mkdir(parents=True)
            desktop_dir.mkdir(parents=True)

            fake_labwc = fake_bin / "labwc"
            fake_labwc.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_labwc.chmod(0o700)

            original_labwc = "#!/bin/sh\noriginal-desktop &\n"
            original_desktop_entry = "[Desktop Entry]\nName=Original\n"
            (labwc_dir / "autostart").write_text(
                original_labwc,
                encoding="utf-8",
            )
            (desktop_dir / "cyberdash-red.desktop").write_text(
                original_desktop_entry,
                encoding="utf-8",
            )

            environment = os.environ.copy()
            environment["HOME"] = str(home)
            environment["XDG_CONFIG_HOME"] = str(home / ".config")
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"

            subprocess.run(
                [str(PROJECT / "install_kiosk_startup.sh")],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )

            generated = (labwc_dir / "autostart").read_text(encoding="utf-8")
            self.assertIn("CYBERDASH_START_DELAY=0", generated)
            self.assertNotIn("original-desktop", generated)
            self.assertFalse((desktop_dir / "cyberdash-red.desktop").exists())

            subprocess.run(
                [str(PROJECT / "disable_kiosk_startup.sh")],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertEqual(
                (labwc_dir / "autostart").read_text(encoding="utf-8"),
                original_labwc,
            )
            self.assertEqual(
                (desktop_dir / "cyberdash-red.desktop").read_text(
                    encoding="utf-8"
                ),
                original_desktop_entry,
            )

    def test_fullscreen_dashboard_hides_pointer(self):
        source = (PROJECT / "dashboard_v2.py").read_text(encoding="utf-8")
        self.assertIn("Window.show_cursor = WINDOWED_MODE", source)


if __name__ == "__main__":
    unittest.main()
