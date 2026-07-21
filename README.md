# Cyberdash Red — Civic Outline Converter

This project converts an existing ordered set of rotating silver Civic images into transparent white outline/etch frames for a Raspberry Pi dashboard. It can add a soft red underglow, preserves the 360-degree frame order, creates a six-angle preview, and includes a Kivy viewer that reads the processed frames directly.

The original silver frames are never modified.

## Project layout

```text
cyberdash-red/
├── convert_civic_outline.py
├── civic_360_viewer.py
├── requirements.txt
├── assets/
│   ├── civic_frames/          # Original silver frames (not committed)
│   └── civic_frames_outline/  # Generated transparent frames (not committed)
└── tests/
```

## 1. Install on the Raspberry Pi

```bash
cd ~/Desktop
git clone https://github.com/hufi94/cyberdash-red.git cyberdash_red
cd ~/Desktop/cyberdash_red

python3 -m venv .venv --system-site-packages
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If Kivy is already installed in the dashboard environment, the last command simply confirms the required versions.

## 2. Add the existing silver frames

```bash
cd ~/Desktop/cyberdash_red
mkdir -p assets/civic_frames
```

Copy the working rotating images into:

```text
~/Desktop/cyberdash_red/assets/civic_frames
```

The converter naturally sorts the filenames, so `frame_2.png` comes before `frame_10.png`.

## 3. Back up the source and viewer

```bash
cd ~/Desktop/cyberdash_red

backup_stamp=$(date +%Y%m%d_%H%M%S)

cp -a assets/civic_frames \
"assets/civic_frames_silver_backup_${backup_stamp}"

if [ -f civic_360_test.py ]; then
    cp -a civic_360_test.py \
    "civic_360_test.py.backup_${backup_stamp}"
fi

if [ -d assets/civic_frames_outline ]; then
    mv assets/civic_frames_outline \
    "assets/civic_frames_outline_backup_${backup_stamp}"
fi
```

## 4. Create a six-angle preview

Start with the recommended 640×480 dashboard settings:

```bash
cd ~/Desktop/cyberdash_red
source .venv/bin/activate

python convert_civic_outline.py preview \
    --line-thickness 2 \
    --edge-threshold 28 \
    --background-threshold 24 \
    --alpha-threshold 8 \
    --underglow on \
    --glow-opacity 135 \
    --glow-blur 12
```

Open the result:

```bash
xdg-open ~/Desktop/cyberdash_red/assets/civic_outline_preview.png
```

The preview uses a dark background so the white lines are visible. The individual animation frames remain transparent.

## Appearance settings

| Setting | Result |
| --- | --- |
| `--line-thickness 1` | Thin technical outline |
| `--line-thickness 2` | Recommended for a 640×480 display |
| `--line-thickness 3` | Stronger racing-style outline |
| Lower `--edge-threshold` | More windows, wheels, reflections, and body detail |
| Higher `--edge-threshold` | Cleaner image with less surface noise |
| Higher `--background-threshold` | Removes more opaque background and shadow noise |
| Higher `--alpha-threshold` | Removes faint transparent halos |
| `--underglow off` | White etch only |
| Higher `--glow-opacity` | Brighter red glow |
| Higher `--glow-blur` | Softer, wider glow |

More detail:

```bash
python convert_civic_outline.py preview \
    --line-thickness 2 \
    --edge-threshold 18 \
    --background-threshold 24 \
    --underglow on
```

Cleaner and simpler:

```bash
python convert_civic_outline.py preview \
    --line-thickness 2 \
    --edge-threshold 42 \
    --background-threshold 32 \
    --underglow on
```

## 5. Convert the complete rotation

Use the same settings that looked best in the preview:

```bash
python convert_civic_outline.py all \
    --line-thickness 2 \
    --edge-threshold 28 \
    --background-threshold 24 \
    --alpha-threshold 8 \
    --underglow on \
    --glow-opacity 135 \
    --glow-blur 12
```

The output is written to:

```text
assets/civic_frames_outline/frame_0000.png
assets/civic_frames_outline/frame_0001.png
assets/civic_frames_outline/frame_0002.png
...
```

`frame_order.txt` records the exact original-to-generated filename mapping. The converter refuses to overwrite a non-empty output directory; rename that directory before trying different settings.

Verify the frame count:

```bash
find assets/civic_frames_outline \
    -maxdepth 1 -type f -name 'frame_*.png' | wc -l
```

## 6. Run the outline viewer

The included Kivy viewer already points to `assets/civic_frames_outline`:

```bash
cd ~/Desktop/cyberdash_red
source .venv/bin/activate
python civic_360_viewer.py
```

Press **Esc** to close it.

Change these values near the bottom of `civic_360_viewer.py` if desired:

```python
rotation_seconds=7.0
reverse_rotation=False
```

## Updating an older viewer

If the dashboard still uses `civic_360_test.py`, back it up and switch only its frame-folder setting:

```bash
cd ~/Desktop/cyberdash_red

python - <<'PY'
from pathlib import Path

viewer = Path("civic_360_test.py")
code = viewer.read_text(encoding="utf-8")

old = '/ "civic_frames"'
new = '/ "civic_frames_outline"'

if new in code:
    print("Viewer already uses the outline frames.")
elif old not in code:
    raise SystemExit("Could not find the old Civic frame-folder setting.")
else:
    viewer.write_text(code.replace(old, new, 1), encoding="utf-8")
    print("Viewer now uses assets/civic_frames_outline.")
PY
```

Then confirm the path:

```bash
grep -n "civic_frames" civic_360_test.py
```

## Development test

The tests generate temporary synthetic car frames and confirm that source images are preserved, output images are transparent RGBA, and natural animation order is retained.

```bash
python -m unittest discover -s tests -v
```
