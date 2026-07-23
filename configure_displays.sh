#!/usr/bin/env bash
set -euo pipefail

# Per-monitor X11 profile for the Raspberry Pi 5 dashboard setup.
#
# Board HDMI0 / first micro-HDMI port: 640x480 dashboard, rotated 180 degrees.
# Board HDMI1 / second micro-HDMI port: 1920x1080 work display, upright.
#
# Raspberry Pi OS normally exposes those ports to XRandR as HDMI-1 and HDMI-2.
# The HDMI-A-* aliases are also accepted for installations that retain the DRM
# connector names.

xrandr_bin="${CYBERDASH_XRANDR_BIN:-xrandr}"
small_mode="${CYBERDASH_SMALL_MODE:-640x480}"
work_mode="${CYBERDASH_WORK_MODE:-1920x1080}"

if ! command -v "${xrandr_bin}" >/dev/null 2>&1; then
    printf 'XRandR is unavailable; display profile was not applied.\n'
    exit 1
fi

query="$(${xrandr_bin} --query)"

is_connected() {
    local output_name="$1"
    grep -Eq "^${output_name//./\\.}[[:space:]]+connected([[:space:]]|$)" \
        <<< "${query}"
}

resolve_output() {
    local explicit_name="$1"
    shift

    if [[ -n "${explicit_name}" ]]; then
        if is_connected "${explicit_name}"; then
            printf '%s\n' "${explicit_name}"
            return 0
        fi
        printf 'Configured output is not connected: %s\n' \
            "${explicit_name}" >&2
        return 1
    fi

    local candidate
    for candidate in "$@"; do
        if is_connected "${candidate}"; then
            printf '%s\n' "${candidate}"
            return 0
        fi
    done
    return 1
}

output_has_mode() {
    local output_name="$1"
    local requested_mode="$2"
    awk -v output="${output_name}" -v mode="${requested_mode}" '
        $1 == output && $2 == "connected" { inside = 1; next }
        inside && $1 !~ /^[0-9]+x[0-9]+$/ { inside = 0 }
        inside && $1 == mode { found = 1 }
        END { exit(found ? 0 : 1) }
    ' <<< "${query}"
}

small_output="$(resolve_output \
    "${CYBERDASH_SMALL_OUTPUT:-}" \
    HDMI-1 HDMI-A-1 HDMI-1-1)" || {
        printf 'The first HDMI dashboard display is not connected.\n' >&2
        exit 1
    }

if ! output_has_mode "${small_output}" "${small_mode}"; then
    printf '%s does not advertise the required dashboard mode %s.\n' \
        "${small_output}" "${small_mode}" >&2
    exit 1
fi

display_args=(
    --output "${small_output}"
    --mode "${small_mode}"
    --rotate inverted
    --primary
    --pos 0x0
)

work_output="$(resolve_output \
    "${CYBERDASH_WORK_OUTPUT:-}" \
    HDMI-2 HDMI-A-2 HDMI-1-2)" || true

if [[ -n "${work_output}" && "${work_output}" != "${small_output}" ]]; then
    display_args+=(
        --output "${work_output}"
        --rotate normal
    )

    if output_has_mode "${work_output}" "${work_mode}"; then
        display_args+=(--mode "${work_mode}")
    else
        printf '%s does not advertise %s; using its preferred mode.\n' \
            "${work_output}" "${work_mode}"
        display_args+=(--preferred)
    fi

    display_args+=(--right-of "${small_output}")
fi

"${xrandr_bin}" "${display_args[@]}"

printf 'Dashboard display: %s, %s, inverted (180 degrees), primary.\n' \
    "${small_output}" "${small_mode}"
if [[ -n "${work_output}" && "${work_output}" != "${small_output}" ]]; then
    printf 'Work display: %s, upright, positioned to the right.\n' \
        "${work_output}"
fi
