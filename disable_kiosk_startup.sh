#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
labwc_autostart="${HOME}/.config/labwc/autostart"
state_dir="${HOME}/.config/cyberdash-red-kiosk"
desktop_entry="${XDG_CONFIG_HOME:-${HOME}/.config}/autostart/cyberdash-red.desktop"
disabled_state="${state_dir}.disabled_$(date +%Y%m%d_%H%M%S)"

if [[ ! -f "${state_dir}/installed" ]]; then
    printf 'Cyberdash fast kiosk startup is not installed.\n'
    exit 0
fi

if [[ -f "${labwc_autostart}" ]]; then
    mv "${labwc_autostart}" "${state_dir}/generated-labwc-autostart"
fi

if [[ -f "${state_dir}/original-labwc-autostart" ]]; then
    mkdir -p "$(dirname -- "${labwc_autostart}")"
    cp -a "${state_dir}/original-labwc-autostart" "${labwc_autostart}"
fi

if [[ -f "${state_dir}/normal-autostart.desktop" ]]; then
    mkdir -p "$(dirname -- "${desktop_entry}")"
    if [[ -f "${desktop_entry}" ]]; then
        mv "${desktop_entry}" "${state_dir}/autostart-found-during-restore.desktop"
    fi
    cp -a "${state_dir}/normal-autostart.desktop" "${desktop_entry}"
fi

mv "${state_dir}" "${disabled_state}"

printf 'Cyberdash fast kiosk startup is disabled.\n'
printf 'The previous desktop startup configuration was restored.\n'
printf 'Recovery files were preserved at: %s\n' "${disabled_state}"
printf 'Reboot with: sudo reboot\n'
