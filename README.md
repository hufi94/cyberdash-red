# Cyberdash Red — Raspberry Pi Civic Dashboard

This is the fresh Kivy dashboard package for the Raspberry Pi 5 and 640×480
display. It includes the approved rotating Honda Civic EJ9 artwork directly in
the repository, so the Pi does not need to convert or copy any car frames.

## Approved Civic animation

- 220 transparent PNG frames in preserved rotation order
- sharp white outline/etch artwork with windows, wheels, grille and body detail
- headlights and taillights filled at 70% white opacity
- smooth early fade-in and late fade-out around the visible lamp angles
- one complete rotation every 12 seconds
- no red pixels and no baked-in underglow
- no separate ground line that can drift away from the car

![Approved Civic rotation angles](preview/approved_civic_contact.png)

The full motion preview is available here:
[approved 12-second rotation](preview/approved_civic_rotation_12s.mp4).

## Files to run

- `civic_360_test.py` — tests only the approved Civic animation
- `dashboard_v2.py` — runs the full 640×480 dashboard
- `sensor_test.py` — tests both BME280 sensors in the terminal
- `civic_360_widget.py` — reusable player used by both Kivy programs
- `dashboard_v1_handoff_reconstructed.py` — preserved reconstructed V1 baseline
- `build_approved_civic_frames.py` — optional frame rebuilding tool

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
    --branch agent/integrate-approved-civic-dashboard-v2 \
    --single-branch \
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

Press **Esc** to close it. The existing Raspberry Pi autostart configuration is
not changed by this repository.

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
```

A larger number rotates more slowly. The player uses elapsed time rather than
blindly advancing one frame per timer event, so temporary Pi workload cannot
permanently speed up or slow down the rotation.

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
    --edge-threshold 18
```

Appearance controls:

| Setting | Effect |
| --- | --- |
| `--line-thickness 1` | Approved thin, sharp technical lines |
| `--line-thickness 2` | Stronger lines for a brighter small display |
| Lower `--edge-threshold` | More windows, grille and surface detail |
| Higher `--edge-threshold` | Simpler artwork with less fine detail |

The approved settings are line thickness `1`, edge threshold `18`, and no red
underglow. The builder requires the complete ordered set of 220 source frames
and writes `frame_order.txt` plus `lamp_tracking.tsv` for verification.

## Development checks

```bash
python -m unittest discover -s tests -v
python -m py_compile \
    build_approved_civic_frames.py \
    civic_360_widget.py \
    civic_360_test.py \
    dashboard_v2.py \
    sensor_test.py
```

The source silver frames are not committed. The approved transparent output is
committed under `assets/civic_frames_outline` so a fresh Pi clone is complete.
