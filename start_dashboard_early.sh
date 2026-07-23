#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python_path="${project_dir}/.venv/bin/python"
log_dir="${project_dir}/runtime"
log_file="${log_dir}/dashboard.log"

mkdir -p "${log_dir}"
exec >> "${log_file}" 2>&1

printf '\n[%s] Early dashboard launcher started.\n' "$(date --iso-8601=seconds)"

if [[ ! -x "${python_path}" ]]; then
    printf 'Dashboard Python environment not found: %s\n' "${python_path}"
    exit 1
fi

export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-${HOME}/.Xauthority}"
export SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-x11}"
export KIVY_NO_ARGS=1
export PYTHONUNBUFFERED=1

display_ready=0
for ((attempt = 1; attempt <= 150; attempt++)); do
    if xset q >/dev/null 2>&1; then
        display_ready=1
        break
    fi
    sleep 0.2
done

if [[ "${display_ready}" -ne 1 ]]; then
    printf 'X11 display did not become ready: %s\n' "${DISPLAY}"
    exit 1
fi

# Cover the root window before importing Kivy. The SiR overlay takes over as
# soon as the SDL window exists.
if command -v xsetroot >/dev/null 2>&1; then
    xsetroot -solid black >/dev/null 2>&1 || true
fi
xset s off >/dev/null 2>&1 || true
xset -dpms >/dev/null 2>&1 || true
xset s noblank >/dev/null 2>&1 || true

cd "${project_dir}"
exec "${python_path}" "${project_dir}/dashboard_v2.py"
