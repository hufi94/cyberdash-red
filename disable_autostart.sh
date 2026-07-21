#!/usr/bin/env bash
set -euo pipefail

autostart_dir="${XDG_CONFIG_HOME:-${HOME}/.config}/autostart"
entry_path="${autostart_dir}/cyberdash-red.desktop"
disabled_path="${entry_path}.disabled_$(date +%Y%m%d_%H%M%S)"

if [[ ! -f "${entry_path}" ]]; then
    printf 'Cyberdash Red autostart is not installed.\n'
    exit 0
fi

mv "${entry_path}" "${disabled_path}"
printf 'Autostart disabled and preserved at: %s\n' "${disabled_path}"
