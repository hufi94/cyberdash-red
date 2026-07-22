# Cyberdash Red — Raspberry Pi Civic Dashboard

This is the fresh Kivy dashboard package for the Raspberry Pi 5. Its structured
red/white telemetry layout adapts to 640×480, 800×480 and widescreen displays
without stretching the Civic. It includes the approved rotating Honda Civic
artwork directly in the repository, so the Pi does not need to convert or copy
any car frames.

## Approved telemetry layout

- clipped-corner four-panel frame with restrained red racing accents
- large time and date module with a technical divider
- inside/outside climate rows with thermometer icons and red segmented gauges
- rotating Civic module labelled `HONDA CIVIC EG9 // B16A2` with `360 LIVE`
- simulated segmented audio spectrum with solid red baseline segments that
  progress through coral and pale red to white at full height
- no continuous gray climate tracks and no diagonal background clutter

## Approved Civic animation

- 220 transparent PNG frames in preserved rotation order
- sharp white outline/etch artwork with windows, wheels, grille and body detail
- headlights and taillights filled at 70% white opacity
- lamp fills constrained to real housing pixels in every source angle
- smooth early fade-in and late fade-out around the visible lamp angles
- one complete rotation every 12 seconds
- one shared crop for all frames, preventing vertical or sideways movement
- clean no-red frames loaded from `assets/civic_frames_outline`
- four soft Kivy floor-frame edges projected behind the Civic
- no red strip, red body lines or separate animation timer
- the floor frame rotates through the exact same angle as the Civic

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
- `floor_glow.py` — projects the rotating soft red floor frame in code

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

A three-pixel screen inset keeps the accents clear of the physical display
edge while using more of the 3.5-inch panel. At 640×480, the interface applies
a sixteen-percent typography boost plus a twenty-four-percent boost for the
clock and temperature numbers, tighter seven-pixel panel margins, and larger
Civic and visualizer viewports. Wider HDMI displays keep the original spacing
and typography scale.

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
GLOW_OPACITY = 1.0
GLOW_FADE_EXTENSION_SECONDS = 1.0
```

A larger number rotates more slowly. The player uses elapsed time rather than
blindly advancing one frame per timer event, so temporary Pi workload cannot
permanently speed up or slow down the rotation.

The Civic remains completely hidden while its 220 frames load. Once the full
set is ready, rotation begins immediately while the vehicle fades in over
`FADE_IN_SECONDS`. Increase that value for a slower reveal, or set it to `0`
to show the rotating Civic immediately.

The dashboard loads the clean `assets/civic_frames_outline` sequence. Kivy
creates four soft red edge textures in memory and projects them as the two
sides, front and rear of a ground-plane rectangle beneath the car. At side
views the long side edge is emphasized. At front/rear views the appropriate
short edge is emphasized. At 45 degrees those edges form a slanted projected
frame instead of a horizontal bar. The player changes the Civic PNG and floor
projection together in the same `update_rotation` call, so there is no second
timer or independent motion. The glow is hidden during loading and fades in
at exactly the same time as the Civic.

Each projected side of the glow begins fading in one second earlier and
finishes fading out one second later. The overlapping light is drawn behind
the transparent Civic frames, so the longer fade remains beneath the car
instead of shining over its body. Change `GLOW_FADE_EXTENSION_SECONDS` to tune
that overlap without altering rotation speed or floor geometry.

The default effect is deliberately large and bright: its projected strip is
`52` source pixels wide, its center alpha is `250`, and its broad falloff is
`1.55`. For quick tuning, lower `GLOW_OPACITY` for less brightness. Adjust
`EDGE_GLOW_THICKNESS`, `GLOW_MAXIMUM_ALPHA`, or `GLOW_FALLOFF_POWER` in
`floor_glow.py` to change its spread, center intensity, or bloom softness.
Set `GLOW_ENABLED = False` to turn it off without changing any PNG frame.

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

## Development checks

```bash
python -m unittest discover -s tests -v
python -m py_compile \
    build_approved_civic_frames.py \
    floor_glow.py \
    civic_360_widget.py \
    civic_360_test.py \
    dashboard_theme.py \
    dashboard_v2.py \
    sensor_test.py
```

The source silver frames are not committed. The approved no-red set is
committed, and the glow is generated by Kivy, so a fresh Pi clone is complete.
