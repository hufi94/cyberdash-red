#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python_path="${project_dir}/.venv/bin/python"
log_dir="${project_dir}/runtime"
log_file="${log_dir}/dashboard.log"

mkdir -p "${log_dir}"

if [[ ! -x "${python_path}" ]]; then
    printf 'Dashboard Python environment not found: %s\n' "${python_path}" \
        >> "${log_file}"
    exit 1
fi

start_delay="${CYBERDASH_START_DELAY:-0}"
if [[ ! "${start_delay}" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    printf 'Invalid CYBERDASH_START_DELAY: %s\n' "${start_delay}" \
        >> "${log_file}"
    exit 1
fi

if [[ "${start_delay}" != "0" ]]; then
    sleep "${start_delay}"
fi

cd "${project_dir}"
export KIVY_NO_ARGS=1
export PYTHONUNBUFFERED=1

exec "${python_path}" "${project_dir}/dashboard_v2.py" \
    >> "${log_file}" 2>&1
