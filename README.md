# Cyberdash Red — Raspberry Pi Civic Dashboard

This is the fresh Kivy dashboard package for the Raspberry Pi 5. Its layout
adapts to 640×480, 800×480 and widescreen displays without stretching the
Civic. It includes the approved rotating Honda Civic EJ9 artwork directly in
the repository, so the Pi does not need to convert or copy any car frames.

## Approved Civic animation

- 220 transparent PNG frames in preserved rotation order
- sharp white outline/etch artwork with windows, wheels, grille and body detail
- headlights and taillights filled at 70% white opacity
- lamp fills constrained to real housing pixels in every source angle
- smooth early fade-in and late fade-out around the visible lamp angles
- one complete rotation every 12 seconds
- one shared crop for all frames, preventing vertical or sideways movement
- clean no-red frames loaded from `assets/civic_frames_outline`
- one small, soft Kivy floor reflection drawn behind the Civic
- no red strip, red body lines or separate animation timer
- the glow position and width use the exact same frame index as the Civic

![Approved Civic rotation angles](preview/approved_civic_contact.png)

The full motion preview is available here:
[approved 12-second rotation](preview/approved_civic_rotation_12s.mp4).

## Files to run

- `civic_360_test.py` — tests only the approved Civic animation
- `dashboard_v2.py` — runs the responsive fullscreen dashboard
- `sensor_test.py` — tests both BME280 sensors in the terminal
- `civic_360_widget.py` — reusable player used by both Kivy programs
- `start_dashboard.sh` — launches V2 without opening a Terminal window
- `install_autostart.sh` — enables launch after the Pi desktop starts
- `dashboard_v1_handoff_reconstructed.py` — preserved reconstructed V1 baseline
- `build_approved_civic_frames.py` — optional frame rebuilding tool
- `floor_glow.py` — creates the soft red reflection directly in code
- `build_floor_glow_tracking.py` — rebuilds its frame-locked placement data

`dashboard_v2.py` reads the inside BME280 at `0x77` and the outside BME280 at
`0x76`. Sensor connection errors are shown on screen without stopping the
dashboard. The audio visualizer is still a simulated placeholder.

## Install safely on the Raspberry Pi

These commands preserve the current dashboard as a timestamped backup, then
install this version in a fresh `~/Desktop/cyberdash_red` folder.

```bash
cd ~/Desktop

backup_stamp=$(date +%Y%m%d_%H%M%S)

if [ -d cyberdash_red ]; then
    mv cyberdash_red "cyberdash_red_backup_${backup_stamp}"
fi

git clone \
    https://github.com/hufi94/cyberdash-red.git \
    cyberdash_red

cd ~/Desktop/cyberdash_red
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Preview the Civic first

```bash
cd ~/Desktop/cyberdash_red
source .venv/bin/activate
python civic_360_test.py
```

Press **Esc** to close the preview.

## Run the full dashboard

```bash
cd ~/Desktop/cyberdash_red
source .venv/bin/activate
python dashboard_v2.py
```

Press **Esc** to close it. V2 starts fullscreen by default. It keeps the layout
480 design pixels tall and adapts its width to the detected screen:

- 640×480 uses the compact four-panel layout.
- 800×480 uses the full wide panel instead of leaving 80-pixel side bars.
- 16:9 monitors use an 853×480 layout before uniform scaling.

A six-pixel screen inset and ten-pixel panel margin keep the accents clear of
the physical display edge. Small headings are enlarged, while the time,
temperatures, Civic and visualizer retain their emphasis.

To test it in a normal resizable window instead, run:

```bash
CYBERDASH_WINDOWED=1 python dashboard_v2.py
```

## Start automatically with the Raspberry Pi

Only enable this after the fullscreen dashboard has been checked manually:

```bash
cd ~/Desktop/cyberdash_red
chmod +x start_dashboard.sh install_autostart.sh disable_autostart.sh
./install_autostart.sh
```

The installer creates a desktop autostart entry with `Terminal=false`, so no
Terminal window appears during normal startup. It preserves an existing
Cyberdash Red entry before replacing it and reports possible older dashboard
entries without changing them.

Reboot to test:

```bash
sudo reboot
```

To disable this autostart safely later:

```bash
cd ~/Desktop/cyberdash_red
./disable_autostart.sh
```

The disabled entry is renamed with a timestamp instead of being deleted.

## Test the two BME280 sensors

```bash
cd ~/Desktop/cyberdash_red
source .venv/bin/activate
i2cdetect -y 1
python sensor_test.py
```

The I²C scan should show both `76` and `77`. Stop the terminal sensor test with
**Ctrl+C**.

## Civic player settings

The default rotation speed is defined near the top of `civic_360_widget.py`:

```python
ROTATION_SECONDS = 12.0
FADE_IN_SECONDS = 1.5
GLOW_OPACITY = 0.72
```

A larger number rotates more slowly. The player uses elapsed time rather than
blindly advancing one frame per timer event, so temporary Pi workload cannot
permanently speed up or slow down the rotation.

The Civic remains completely hidden while its 220 frames load. Once the full
set is ready, rotation begins immediately while the vehicle fades in over
`FADE_IN_SECONDS`. Increase that value for a slower reveal, or set it to `0`
to show the rotating Civic immediately.

The dashboard loads the clean `assets/civic_frames_outline` sequence. Kivy
creates one soft red floor reflection in memory and places it behind the car.
It has fully transparent edges and no solid center line. A small tracking file
records the Civic silhouette center, bottom edge and projected width for all
220 frames. The player changes the PNG and glow geometry together in the same
`update_rotation` call, so there is no second timer or independent motion. The
glow is hidden during loading and fades in at exactly the same time as the
Civic.

For quick tuning, lower `GLOW_OPACITY` for less brightness. Set
`GLOW_ENABLED = False` to turn it off without changing any PNG frame.

## Optional: rebuild the transparent frames

The approved frames are already included. Rebuilding is only necessary if the
source renders change. Keep the original silver frames outside the output
folder, then run:

```bash
python build_approved_civic_frames.py \
    --source /path/to/original/silver_frames \
    --output /path/to/new/transparent_frames \
    --preview /path/to/preview.png \
    --line-thickness 1 \
    --edge-threshold 18 \
    --crop-padding 16
```

Appearance controls:

| Setting | Effect |
| --- | --- |
| `--line-thickness 1` | Approved thin, sharp technical lines |
| `--line-thickness 2` | Stronger lines for a brighter small display |
| Lower `--edge-threshold` | More windows, grille and surface detail |
| Higher `--edge-threshold` | Simpler artwork with less fine detail |
| `--crop-padding 16` | Shared transparent margin without frame-to-frame movement |

The approved settings are line thickness `1`, edge threshold `18`, crop padding
`16`, and no red underglow. The builder requires the complete ordered set of
220 source frames and writes `frame_order.txt` plus `lamp_tracking.tsv` for
verification. Headlight and taillight fills are extracted from real lamp
material in each source frame, then baked into that same transparent PNG. Kivy
does not animate a second lamp layer, so the fills cannot move independently
of the Civic.

If the transparent Civic frames are rebuilt, rebuild the matching code-glow
anchors afterward:

```bash
python build_floor_glow_tracking.py
```

## Development checks

```bash
python -m unittest discover -s tests -v
python -m py_compile \
    build_approved_civic_frames.py \
    build_floor_glow_tracking.py \
    floor_glow.py \
    civic_360_widget.py \
    civic_360_test.py \
    dashboard_v2.py \
    sensor_test.py
```

The source silver frames are not committed. The approved no-red set is
committed, and the glow is generated by Kivy, so a fresh Pi clone is complete.
