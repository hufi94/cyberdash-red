#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
start_script="${project_dir}/start_dashboard.sh"
autostart_dir="${XDG_CONFIG_HOME:-${HOME}/.config}/autostart"
entry_path="${autostart_dir}/cyberdash-red.desktop"
backup_stamp="$(date +%Y%m%d_%H%M%S)"

if [[ ! -x "${start_script}" ]]; then
    printf 'Startup script is not executable: %s\n' "${start_script}"
    printf 'Run: chmod +x start_dashboard.sh install_autostart.sh\n'
    exit 1
fi

mkdir -p "${autostart_dir}"
if [[ -f "${entry_path}" ]]; then
    cp -a "${entry_path}" "${entry_path}.backup_${backup_stamp}"
fi

printf '%s\n' \
    '[Desktop Entry]' \
    'Type=Application' \
    'Name=Cyberdash Red' \
    'Comment=Fullscreen Civic dashboard' \
    "Exec=${start_script}" \
    "Path=${project_dir}" \
    'Terminal=false' \
    'Hidden=false' \
    'X-GNOME-Autostart-enabled=true' \
    > "${entry_path}"

chmod 600 "${entry_path}"
printf 'Installed dashboard autostart: %s\n' "${entry_path}"
printf 'The dashboard will start after the Raspberry Pi desktop loads.\n'

potential_conflicts="$(
    grep -lEi 'dashboard(_v|V)|civic_360|/Desktop/cd/' \
        "${autostart_dir}"/*.desktop 2>/dev/null \
        | grep -vF "${entry_path}" \
        || true
)"
if [[ -n "${potential_conflicts}" ]]; then
    printf '\nPossible older dashboard startup entries were found:\n%s\n' \
        "${potential_conflicts}"
    printf 'They were not changed. Disable them before rebooting if they launch the old dashboard.\n'
fi
