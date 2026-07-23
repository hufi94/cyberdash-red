#!/usr/bin/env bash
set -euo pipefail

config_home="${XDG_CONFIG_HOME:-${HOME}/.config}"
state_dir="${config_home}/cyberdash-red-early"
desktop_entry="${config_home}/autostart/cyberdash-red.desktop"
service_name="cyberdash-red.service"

sudo systemctl disable --now "${service_name}" >/dev/null 2>&1 || true
sudo systemctl daemon-reload

if [[ -f "${state_dir}/desktop-autostart.backup" ]]; then
    mkdir -p "$(dirname -- "${desktop_entry}")"
    if [[ -f "${desktop_entry}" ]]; then
        mv "${desktop_entry}" \
            "${state_dir}/desktop-autostart.found-during-restore"
    fi
    mv "${state_dir}/desktop-autostart.backup" "${desktop_entry}"
fi

if [[ -f "${state_dir}/installed" ]]; then
    mv "${state_dir}/installed" \
        "${state_dir}/disabled-$(date +%Y%m%d_%H%M%S)"
fi

printf 'Cyberdash early startup is disabled.\n'
printf 'The service file was preserved at /etc/systemd/system/%s.\n' \
    "${service_name}"
