#!/usr/bin/env bash
set -euo pipefail

config_home="${XDG_CONFIG_HOME:-${HOME}/.config}"
state_dir="${config_home}/cyberdash-red-kiosk"
desktop_entry="${config_home}/autostart/cyberdash-red.desktop"
disabled_state="${state_dir}.disabled_$(date +%Y%m%d_%H%M%S)_$$"

if [[ ! -f "${state_dir}/installed" ]]; then
    printf 'Cyberdash fast kiosk startup is not installed.\n'
    exit 0
fi

session_kind="$(<"${state_dir}/session-kind")"
session_autostart="$(<"${state_dir}/autostart-path")"

case "${session_autostart}" in
    "${config_home}"/*) ;;
    *)
        printf 'Refusing to restore an unexpected startup path: %s\n' \
            "${session_autostart}"
        exit 1
        ;;
esac

if [[ -f "${session_autostart}" ]]; then
    mv "${session_autostart}" "${state_dir}/generated-session-autostart"
fi

if [[ -f "${state_dir}/original-session-autostart" ]]; then
    mkdir -p "$(dirname -- "${session_autostart}")"
    cp -a "${state_dir}/original-session-autostart" "${session_autostart}"
fi

if [[ -f "${state_dir}/normal-autostart.desktop" ]]; then
    mkdir -p "$(dirname -- "${desktop_entry}")"
    if [[ -f "${desktop_entry}" ]]; then
        mv "${desktop_entry}" "${state_dir}/autostart-found-during-restore.desktop"
    fi
    cp -a "${state_dir}/normal-autostart.desktop" "${desktop_entry}"
fi

mv "${state_dir}" "${disabled_state}"

printf 'Cyberdash fast kiosk startup is disabled for: %s\n' "${session_kind}"
printf 'The previous desktop startup configuration was restored.\n'
printf 'Recovery files were preserved at: %s\n' "${disabled_state}"
printf 'Reboot with: sudo reboot\n'
