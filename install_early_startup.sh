#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
launcher="${project_dir}/start_dashboard_early.sh"
service_name="cyberdash-red.service"
service_path="/etc/systemd/system/${service_name}"
config_home="${XDG_CONFIG_HOME:-${HOME}/.config}"
state_dir="${config_home}/cyberdash-red-early"
desktop_entry="${config_home}/autostart/cyberdash-red.desktop"

dashboard_user="${CYBERDASH_USER:-${SUDO_USER:-${USER}}}"
dashboard_group="$(id -gn "${dashboard_user}")"
if command -v getent >/dev/null 2>&1; then
    dashboard_home="$(getent passwd "${dashboard_user}" | cut -d: -f6)"
elif [[ "${dashboard_user}" == "${USER}" ]]; then
    dashboard_home="${HOME}"
else
    dashboard_home=""
fi

if [[ ! -x "${launcher}" ]]; then
    printf 'Early launcher is not executable: %s\n' "${launcher}"
    printf 'Run: chmod +x start_dashboard_early.sh install_early_startup.sh\n'
    exit 1
fi

if [[ -z "${dashboard_home}" ]]; then
    printf 'Could not determine the home folder for: %s\n' "${dashboard_user}"
    exit 1
fi

if [[ "${launcher}" =~ [[:space:]\'] ]]; then
    printf 'The project path cannot contain spaces or single quotes.\n'
    exit 1
fi

if [[ -f "${config_home}/cyberdash-red-kiosk/installed" ]]; then
    printf 'The stripped kiosk startup is still installed.\n'
    printf 'Run ./disable_kiosk_startup.sh before installing early startup.\n'
    exit 1
fi

render_service() {
    printf '%s\n' \
        '[Unit]' \
        'Description=Cyberdash Red early dashboard' \
        'After=display-manager.service' \
        'Wants=display-manager.service' \
        '' \
        '[Service]' \
        'Type=simple' \
        "User=${dashboard_user}" \
        "Group=${dashboard_group}" \
        'Environment=DISPLAY=:0' \
        "Environment=XAUTHORITY=${dashboard_home}/.Xauthority" \
        "Environment=HOME=${dashboard_home}" \
        "WorkingDirectory=${project_dir}" \
        "ExecStart=${launcher}" \
        'Restart=on-failure' \
        'RestartSec=3' \
        'KillMode=control-group' \
        '' \
        '[Install]' \
        'WantedBy=graphical.target'
}

if [[ "${1:-}" == "--print-service" ]]; then
    render_service
    exit 0
fi

mkdir -p "${state_dir}"
if [[ -f "${desktop_entry}" && ! -f "${state_dir}/desktop-autostart.backup" ]]; then
    mv "${desktop_entry}" "${state_dir}/desktop-autostart.backup"
fi

temporary_file="$(mktemp)"
trap 'rm -f "${temporary_file}"' EXIT
render_service > "${temporary_file}"

# Retire both copies of the old loader service without deleting their files.
systemctl --user disable --now civic-dashboard.service >/dev/null 2>&1 || true
sudo systemctl disable --now civic-dashboard.service >/dev/null 2>&1 || true

sudo install -m 0644 "${temporary_file}" "${service_path}"
sudo systemctl daemon-reload
sudo systemctl enable "${service_name}"
: > "${state_dir}/installed"

trap - EXIT
rm -f "${temporary_file}"

printf 'Cyberdash early startup is installed.\n'
printf 'Service: %s\n' "${service_path}"
printf 'Visible sequence after reboot: black, SiR loader, dashboard.\n'
printf 'Reboot with: sudo reboot\n'
